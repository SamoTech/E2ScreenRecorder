# -*- coding: utf-8 -*-
"""
Framebuffer capture via Linux ioctl.
Works on all known STB framebuffer implementations.
Auto-detects HiSilicon /dev/fb1 blank-frame issue.
No external dependencies required.
"""
from __future__ import absolute_import, print_function, division

import os
import sys
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

CHUNK_SIZE = 65536  # 64 KB chunks — safe for Python 2 struct limits


class FramebufferCapture(object):

    def __init__(self, device=None):
        self.device = device or "/dev/fb0"
        self._fd = None
        self._fb_info = {}

    def open(self):
        self._fd = os.open(self.device, os.O_RDONLY)
        self._read_vscreeninfo()
        # Auto-detect HiSilicon blank fb0 -> fall back to fb1
        if self.device == "/dev/fb0" and self._is_blank():
            os.close(self._fd)
            self._fd = None
            if os.path.exists("/dev/fb1"):
                self.device = "/dev/fb1"
                self._fd = os.open(self.device, os.O_RDONLY)
                self._read_vscreeninfo()

    def _is_blank(self):
        """Return True if first 256 bytes of fb are all zero (HiSilicon quirk)."""
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            sample = os.read(self._fd, 256)
            return all(b == 0 for b in bytearray(sample))
        except Exception:
            return False

    def _read_vscreeninfo(self):
        buf = array.array('B', [0] * 160)
        fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf, True)
        raw = buf.tobytes() if hasattr(buf, 'tobytes') else buf.tostring()
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
        """Return raw framebuffer bytes. Uses chunked read for Python 2 safety."""
        info = self._fb_info
        stride    = info["xres"] * (info["bpp"] // 8)
        byte_size = info["yres"] * stride
        # Account for double-buffering yoffset
        offset = info.get("yoffset", 0) * stride
        os.lseek(self._fd, offset, os.SEEK_SET)
        data = b""
        remaining = byte_size
        while remaining > 0:
            chunk = os.read(self._fd, min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)
        return data

    def get_info(self):
        return dict(self._fb_info)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
