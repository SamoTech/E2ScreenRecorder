# -*- coding: utf-8 -*-
"""
Framebuffer capture via Linux ioctl.
Works on all known STB framebuffer implementations.
Auto-detects blank /dev/fb0 (HiSilicon) and falls back to /dev/fb1.
Handles yoffset double-buffering and chunked reads for Python 2 safety.
"""
from __future__ import absolute_import, print_function, division

import os
import struct
import fcntl
import array

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602

VSCREENINFO_FMT = (
    "II"       # xres, yres
    "II"       # xres_virtual, yres_virtual
    "II"       # xoffset, yoffset
    "I"        # bits_per_pixel
    "I"        # grayscale
    "HHH"      # red: offset, length, msb_right
    "HHH"      # green: offset, length, msb_right
    "HHH"      # blue: offset, length, msb_right
    "HHH"      # transp: offset, length, msb_right
    "I"        # nonstd
    "I"        # activate
    "II"       # height_mm, width_mm
    "I"        # accel_flags
    "IIIIIII"  # pixclock, margins, sync, vmode
    "I"        # rotate
    "I"        # colorspace
    "III"      # reserved
)

CHUNK_SIZE = 64 * 1024  # 64 KB — avoids Python 2 single-read limit


class FramebufferCapture(object):

    FALLBACK_DEVICES = ["/dev/fb0", "/dev/fb1"]

    def __init__(self, device=None):
        self.device   = device  # None = auto-detect
        self._fd      = None
        self._fb_info = {}

    def open(self):
        if self.device:
            self._open_device(self.device)
        else:
            self._auto_open()

    def _auto_open(self):
        """Try /dev/fb0 first; fall back to /dev/fb1 if blank (HiSilicon)."""
        last_exc = None
        for dev in self.FALLBACK_DEVICES:
            if not os.path.exists(dev):
                continue
            try:
                self._open_device(dev)
                # Check if framebuffer is blank
                info = self._fb_info
                probe_size = min(256, info["xres"] * (info["bpp"] // 8))
                os.lseek(self._fd, 0, os.SEEK_SET)
                sample = os.read(self._fd, probe_size)
                if any(b != 0 for b in bytearray(sample)):
                    return  # non-blank — use this device
                # blank frame — close and try next
                os.close(self._fd)
                self._fd = None
            except Exception as e:
                last_exc = e
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except Exception:
                        pass
                    self._fd = None
        # All blank or failed — fall back to /dev/fb0
        try:
            self._open_device("/dev/fb0")
        except Exception:
            if last_exc:
                raise last_exc
            raise IOError("No framebuffer device available")

    def _open_device(self, dev):
        self.device = dev
        self._fd = os.open(dev, os.O_RDONLY)
        self._read_vscreeninfo()

    def _read_vscreeninfo(self):
        buf = array.array('B', [0] * 160)
        fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf, True)
        raw    = buf.tobytes()
        fields = struct.unpack_from("<" + VSCREENINFO_FMT, raw)
        self._fb_info = {
            "xres":         fields[0],
            "yres":         fields[1],
            "xoffset":      fields[4],
            "yoffset":      fields[5],
            "bpp":          fields[6],
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
        """Return raw framebuffer bytes for the visible page (handles yoffset)."""
        info      = self._fb_info
        stride    = info["xres"] * (info["bpp"] // 8)
        byte_size = info["xres"] * info["yres"] * (info["bpp"] // 8)
        offset    = info.get("yoffset", 0) * stride

        os.lseek(self._fd, offset, os.SEEK_SET)

        # Chunked read — safe on Python 2 with large buffers
        chunks = []
        remaining = byte_size
        while remaining > 0:
            to_read = min(CHUNK_SIZE, remaining)
            chunk   = os.read(self._fd, to_read)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def get_info(self):
        return dict(self._fb_info)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
