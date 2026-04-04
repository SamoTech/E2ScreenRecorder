# -*- coding: utf-8 -*-
# v1.0.1 — post-audit patch
# Fixes: FIX-001 (chunked read + yoffset), FIX-002 (184-byte ioctl buf),
#        FIX-003 (fd leak + context manager)
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
    "IIIIIII"  # timings
    "I"        # rotate
    "I"        # colorspace
    "III"      # reserved
)

_CHUNK = 65536  # FIX-001: read in 64KB chunks for slow MIPS kernels


class FramebufferCapture(object):
    """
    Framebuffer capture via Linux ioctl.
    Supports context-manager usage::

        with FramebufferCapture() as fb:
            raw = fb.capture_raw()
    """

    def __init__(self, device=None):
        self.device  = device  # None triggers auto-detect in open()
        self._fd     = None
        self._fb_info = {}

    # ── Context manager (FIX-003) ──────────────────────────────────────────
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    # ── Open / close ───────────────────────────────────────────────────────
    def open(self):
        if self.device is None:
            self.device = self._auto_detect_device()
        # FIX-003: wrap in try/finally so fd is never leaked on error
        try:
            self._fd = os.open(self.device, os.O_RDONLY)
            self._read_vscreeninfo()
        except Exception:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            raise

    def close(self):  # FIX-003
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    # ── Auto-detect device (HiSilicon /dev/fb1 workaround) ────────────────
    def _auto_detect_device(self):
        for dev in ("/dev/fb0", "/dev/fb1"):
            if not os.path.exists(dev):
                continue
            try:
                fd = os.open(dev, os.O_RDONLY)
                sample = os.read(fd, 256)
                os.close(fd)
                if sample and sample != b"\x00" * len(sample):
                    return dev
            except OSError:
                pass
        # default — let the OS produce the error message
        return "/dev/fb0"

    # ── VSCREENINFO ioctl (FIX-002) ────────────────────────────────────────
    def _read_vscreeninfo(self):
        # FIX-002: ARM64 kernels use 184-byte struct; was 160 — caused
        #          garbage pixel offsets on VU+ Duo4K / Octagon SF8008
        buf = array.array('B', [0] * 184)  # FIX-002: 184 bytes
        try:
            fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf, True)
        except IOError as e:
            raise IOError("FBIOGET_VSCREENINFO failed on {}: {}".format(
                self.device, e))
        raw = buf.tobytes()
        try:
            fields = struct.unpack_from("<" + VSCREENINFO_FMT, raw)
        except struct.error as e:
            # FIX-002: struct mismatch — parse minimal safe subset
            fields = struct.unpack_from("<IIIIIIII", raw) + (0,) * 30
        self._fb_info = {
            "xres":         fields[0],
            "yres":         fields[1],
            "xoffset":      fields[4],
            "yoffset":      fields[5],   # FIX-001: needed for double-buffer
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

    # ── Capture (FIX-001) ──────────────────────────────────────────────────
    def capture_raw(self):
        """Return raw framebuffer bytes for the visible page."""
        info      = self._fb_info
        w         = info["xres"]
        h         = info["yres"]
        bpp       = info["bpp"]
        yoffset   = info.get("yoffset", 0)   # FIX-001: double-buffer offset
        stride    = w * (bpp // 8)
        byte_size = stride * h
        seek_pos  = yoffset * stride           # FIX-001: seek to visible page

        os.lseek(self._fd, seek_pos, os.SEEK_SET)

        # FIX-001: chunked read — single os.read() returns partial data on
        #          slow MIPS kernels with limited pipe/device buffer sizes
        data   = bytearray()
        remain = byte_size
        while remain > 0:
            chunk = os.read(self._fd, min(_CHUNK, remain))
            if not chunk:
                break
            data  += chunk
            remain -= len(chunk)

        if len(data) < byte_size:  # FIX-001: raise on short read
            raise IOError(
                "Short framebuffer read: got {} expected {} bytes".format(
                    len(data), byte_size))
        return bytes(data)

    def get_info(self):
        return dict(self._fb_info)
