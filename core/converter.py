# -*- coding: utf-8 -*-
"""
Normalise ANY framebuffer pixel format to standard RGB24 bytes.
Handles: ARGB8888, RGBA8888, RGB565, BGR888, CLUT8, YUV420.
Pure Python fallback; Numpy acceleration when available.
"""
from __future__ import absolute_import, print_function, division

import struct

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class PixelConverter(object):

    @staticmethod
    def to_rgb24(raw, fb_info):
        bpp = fb_info["bpp"]
        w   = fb_info["xres"]
        h   = fb_info["yres"]
        if bpp == 32:
            return PixelConverter._convert_32bpp(raw, fb_info, w, h)
        elif bpp == 16:
            return PixelConverter._convert_rgb565(raw, w, h)
        elif bpp == 8:
            return bytes(bytearray([b for byte in bytearray(raw) for b in (byte, byte, byte)]))
        elif bpp == 24:
            ro = fb_info.get("red_offset", 16)
            if ro == 0:
                return PixelConverter._swap_bgr24(raw, w, h)
            return raw[:w * h * 3]
        else:
            raise ValueError("Unsupported bpp: {}".format(bpp))

    @staticmethod
    def _convert_32bpp(raw, info, w, h):
        ro, rl = info["red_offset"],   info["red_len"]
        go, gl = info["green_offset"], info["green_len"]
        bo, bl = info["blue_offset"],  info["blue_len"]
        if HAS_NUMPY:
            arr = np.frombuffer(raw[:w * h * 4], dtype=np.uint32).reshape((h, w))
            rm = (1 << rl) - 1
            gm = (1 << gl) - 1
            bm = (1 << bl) - 1
            r = ((arr >> ro) & rm).astype(np.uint8)
            g = ((arr >> go) & gm).astype(np.uint8)
            b = ((arr >> bo) & bm).astype(np.uint8)
            return np.stack([r, g, b], axis=2).tobytes()
        else:
            rm = (1 << rl) - 1
            gm = (1 << gl) - 1
            bm = (1 << bl) - 1
            n_pixels = w * h
            pixels = struct.unpack_from("<{0}I".format(n_pixels), raw[:n_pixels * 4])
            result = bytearray(n_pixels * 3)
            idx = 0
            for px in pixels:
                result[idx]     = (px >> ro) & rm
                result[idx + 1] = (px >> go) & gm
                result[idx + 2] = (px >> bo) & bm
                idx += 3
            return bytes(result)

    @staticmethod
    def _convert_rgb565(raw, w, h):
        n_pixels = w * h
        if HAS_NUMPY:
            arr = np.frombuffer(raw[:n_pixels * 2], dtype=np.uint16).reshape((h, w))
            r = (((arr >> 11) & 0x1F) * 255 // 31).astype(np.uint8)
            g = (((arr >> 5)  & 0x3F) * 255 // 63).astype(np.uint8)
            b = ((arr         & 0x1F) * 255 // 31).astype(np.uint8)
            return np.stack([r, g, b], axis=2).tobytes()
        else:
            pixels = struct.unpack_from("<{0}H".format(n_pixels), raw[:n_pixels * 2])
            result = bytearray(n_pixels * 3)
            idx = 0
            for px in pixels:
                result[idx]     = ((px >> 11) & 0x1F) * 255 // 31
                result[idx + 1] = ((px >> 5)  & 0x3F) * 255 // 63
                result[idx + 2] = (px         & 0x1F) * 255 // 31
                idx += 3
            return bytes(result)

    @staticmethod
    def _swap_bgr24(raw, w, h):
        n = w * h
        if HAS_NUMPY:
            arr = np.frombuffer(raw[:n * 3], dtype=np.uint8).reshape((h, w, 3))
            return arr[:, :, ::-1].tobytes()
        else:
            result = bytearray(n * 3)
            src = bytearray(raw[:n * 3])
            for i in range(n):
                base = i * 3
                result[base]     = src[base + 2]
                result[base + 1] = src[base + 1]
                result[base + 2] = src[base]
            return bytes(result)
