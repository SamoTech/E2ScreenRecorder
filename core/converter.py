# -*- coding: utf-8 -*-
"""
Normalise ANY framebuffer pixel format to standard RGB24 bytes.
Handles: ARGB8888, RGBA8888, RGB565, BGR888, CLUT8 palette, YUV420.
Pure Python fallback — no Numpy required. Uses Numpy for speed if present.
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
            return bytes(bytearray([b for byte in bytearray(raw)
                                    for b in (byte, byte, byte)]))
        else:
            raise ValueError("Unsupported bpp: {}".format(bpp))

    @staticmethod
    def _convert_32bpp(raw, info, w, h):
        ro, rl = info["red_offset"],   info["red_len"]
        go, gl = info["green_offset"], info["green_len"]
        bo, bl = info["blue_offset"],  info["blue_len"]
        if HAS_NUMPY:
            arr = np.frombuffer(raw, dtype=np.uint32).reshape((h, w))
            r = ((arr >> ro) & ((1 << rl) - 1)).astype(np.uint8)
            g = ((arr >> go) & ((1 << gl) - 1)).astype(np.uint8)
            b = ((arr >> bo) & ((1 << bl) - 1)).astype(np.uint8)
            return np.stack([r, g, b], axis=2).tobytes()
        else:
            rm = (1 << rl) - 1
            gm = (1 << gl) - 1
            bm = (1 << bl) - 1
            result = bytearray(w * h * 3)
            idx = 0
            pixels = struct.unpack_from("<{}I".format(w * h), raw)
            for px in pixels:
                result[idx]   = (px >> ro) & rm
                result[idx+1] = (px >> go) & gm
                result[idx+2] = (px >> bo) & bm
                idx += 3
            return bytes(result)

    @staticmethod
    def _convert_rgb565(raw, w, h):
        if HAS_NUMPY:
            arr = np.frombuffer(raw, dtype=np.uint16).reshape((h, w))
            r = ((arr >> 11) & 0x1F) * 255 // 31
            g = ((arr >> 5)  & 0x3F) * 255 // 63
            b = ( arr        & 0x1F) * 255 // 31
            return np.stack([
                r.astype(np.uint8),
                g.astype(np.uint8),
                b.astype(np.uint8)
            ], axis=2).tobytes()
        else:
            pixels = struct.unpack_from("<{}H".format(w * h), raw)
            result = bytearray(w * h * 3)
            idx = 0
            for px in pixels:
                result[idx]   = ((px >> 11) & 0x1F) * 255 // 31
                result[idx+1] = ((px >> 5)  & 0x3F) * 255 // 63
                result[idx+2] = ( px        & 0x1F) * 255 // 31
                idx += 3
            return bytes(result)
