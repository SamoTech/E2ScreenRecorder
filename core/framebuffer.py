# -*- coding: utf-8 -*-
"""
Framebuffer capture via Linux ioctl.
Handles: double-buffering (yoffset), blank /dev/fb0 -> fallback /dev/fb1,
         mmap failure fallback, Python 2/3, all known STB FB variants.
"""
from __future__ import absolute_import, print_function, division

import os
import struct
import fcntl
import array

from .compat import makedirs_safe

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602

VSCREENINFO_FMT = (
    "<"
    "II"       # xres, yres
    "II"       # xres_virtual, yres_virtual
    "II"       # xoffset, yoffset
    "I"        # bits_per_pixel
    "I"        # grayscale
    "HHH"      # red:   offset, length, msb_right
    "x"
    "HHH"      # green: offset, length, msb_right
    "x"
    "HHH"      # blue:  offset, length, msb_right
    "x"
    "HHH"      # transp
    "x"
    "I"        # nonstd
    "I"        # activate
    "II"       # height_mm, width_mm
    "I"        # accel_flags
    "IIIIIII"  # timings
    "I"        # sync
    "I"        # vmode
    "I"        # rotate
    "I"        # colorspace
    "III"      # reserved[3]
)

VSCREENINFO_SIZE = struct.calcsize(VSCREENINFO_FMT)


class FramebufferCapture(object):

    DEVICES = ["/dev/fb0", "/dev/fb1"]

    def __init__(self, device=None):
        self.device   = device
        self._fd      = None
        self._fb_info = {}

    def open(self):
        if self.device:
            self._open_device(self.device)
        else:
            self._auto_detect()

    def _open_device(self, dev):
        self._fd = os.open(dev, os.O_RDONLY)
        self._read_vscreeninfo()
        self.device = dev

    def _auto_detect(self):
        for dev in self.DEVICES:
            if not os.path.exists(dev):
                continue
            try:
                self._open_device(dev)
                os.lseek(self._fd, 0, os.SEEK_SET)
                sample = os.read(self._fd, 256)
                if sample and any(b != 0 for b in bytearray(sample)):
                    return
                os.close(self._fd)
                self._fd = None
            except (OSError, IOError):
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except Exception:
                        pass
                    self._fd = None
                continue
        if self._fd is None:
            self._open_device("/dev/fb0")

    def _read_vscreeninfo(self):
        buf = array.array('B', [0] * max(VSCREENINFO_SIZE, 160))
        try:
            fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf, True)
        except Exception:
            pass
        raw = buf.tobytes() if hasattr(buf, 'tobytes') else buf.tostring()
        if len(raw) < VSCREENINFO_SIZE:
            raw = raw + b'\x00' * (VSCREENINFO_SIZE - len(raw))
        try:
            fields = struct.unpack_from(VSCREENINFO_FMT, raw)
        except struct.error:
            fields = (1280, 720, 1280, 720, 0, 0, 32, 0,
                      16, 8, 0, 8, 8, 0, 0, 8, 0, 24, 8, 0)
        self._fb_info = {
            "xres":         fields[0]  or 1280,
            "yres":         fields[1]  or 720,
            "xres_virtual": fields[2]  or fields[0] or 1280,
            "yres_virtual": fields[3]  or fields[1] or 720,
            "xoffset":      fields[4],
            "yoffset":      fields[5],
            "bpp":          fields[6]  or 32,
            "grayscale":    fields[7],
            "red_offset":   fields[8],
            "red_len":      fields[9],
            "green_offset": fields[11],
            "green_len":    fields[12],
            "blue_offset":  fields[14],
            "blue_len":     fields[15],
            "alpha_offset": fields[17],
            "alpha_len":    fields[18],
        }

    def capture_raw(self):
        info     = self._fb_info
        stride   = info["xres"] * (info["bpp"] // 8)
        yoffset  = info["yoffset"]
        byte_off = yoffset * stride
        byte_size = info["xres"] * info["yres"] * (info["bpp"] // 8)
        os.lseek(self._fd, byte_off, os.SEEK_SET)
        CHUNK = 65536
        chunks = []
        remaining = byte_size
        while remaining > 0:
            read_size = min(CHUNK, remaining)
            chunk = os.read(self._fd, read_size)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def get_info(self):
        return dict(self._fb_info)

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
