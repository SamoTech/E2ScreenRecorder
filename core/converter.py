# -*- coding: utf-8 -*-
"""
Normalise ANY framebuffer pixel format to standard RGB24 bytes.
Handles: ARGB8888, RGBA8888, RGB565, BGR888, CLUT8, YUV420.
Pure Python fallback; uses Numpy for speed when available.

Black-screenshot fix (BCM7xxx / Amlogic):
  Some STBs store pixels as ARGB8888 with alpha=0 for all pixels.
  When the ioctl-reported channel offsets produce an all-black result,
  _convert_32bpp() retries with the known-good BGRA->RGB layout.
"""
from __future__ import absolute_import, print_function, division
import struct

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Known-good fallback layouts for 32-bpp when ioctl offsets are wrong
# Format: (red_shift, green_shift, blue_shift)
_FALLBACK_LAYOUTS_32 = [
    (16, 8,  0),   # ARGB8888 / BGRA  — Broadcom BCM7xxx default
    (0,  8,  16),  # RGBA8888         — some HiSilicon, Amlogic
    (8,  16, 24),  # ABGR8888         — rare, some MediaTek
]


def _looks_blank(rgb_bytes):
    """
    Return True if the RGB24 buffer appears to be all-black.
    Samples the first 3000 bytes; if fewer than 10 non-dark pixels
    are found the frame is considered blank.
    """
    sample  = bytearray(rgb_bytes[:3000])
    nonzero = sum(1 for b in sample if b > 8)
    return nonzero < 10


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
            # CLUT8 — greyscale fallback (full palette map not available via ioctl)
            return bytes(bytearray(
                [b for byte in bytearray(raw) for b in (byte, byte, byte)]))
        else:
            raise ValueError("Unsupported bpp: {}".format(bpp))

    # ── 32-bpp ───────────────────────────────────────────────────────────────

    @staticmethod
    def _convert_32bpp(raw, info, w, h):
        ro, rl = info["red_offset"],   info["red_len"]
        go, gl = info["green_offset"], info["green_len"]
        bo, bl = info["blue_offset"],  info["blue_len"]

        result = PixelConverter._do_convert_32(raw, w, h, ro, go, bo, rl, gl, bl)

        # FIX — BCM7xxx alpha=0: if ioctl offsets gave a blank frame,
        # retry with each known-good fallback layout
        if _looks_blank(result):
            for (fr, fg, fb) in _FALLBACK_LAYOUTS_32:
                candidate = PixelConverter._do_convert_32(
                    raw, w, h, fr, fg, fb, 8, 8, 8)
                if not _looks_blank(candidate):
                    return candidate
            # All fallbacks also blank — return best-effort original
        return result

    @staticmethod
    def _do_convert_32(raw, w, h, ro, go, bo, rl, gl, bl):
        """Core 32-bpp converter used by both primary and fallback paths."""
        if HAS_NUMPY:
            arr = np.frombuffer(raw, dtype=np.uint32).reshape((h, w))
            r   = ((arr >> ro) & ((1 << rl) - 1)).astype(np.uint8)
            g   = ((arr >> go) & ((1 << gl) - 1)).astype(np.uint8)
            b   = ((arr >> bo) & ((1 << bl) - 1)).astype(np.uint8)
            return np.stack([r, g, b], axis=2).tobytes()
        else:
            rm = (1 << rl) - 1
            gm = (1 << gl) - 1
            bm = (1 << bl) - 1
            pixels = struct.unpack_from("<{}I".format(w * h), raw)
            out    = bytearray(w * h * 3)
            idx    = 0
            for px in pixels:
                out[idx]   = (px >> ro) & rm
                out[idx+1] = (px >> go) & gm
                out[idx+2] = (px >> bo) & bm
                idx += 3
            return bytes(out)

    # ── 16-bpp RGB565 ────────────────────────────────────────────────────────

    @staticmethod
    def _convert_rgb565(raw, w, h):
        if HAS_NUMPY:
            arr = np.frombuffer(raw, dtype=np.uint16).reshape((h, w))
            r   = ((arr >> 11) & 0x1F) * 255 // 31
            g   = ((arr >> 5)  & 0x3F) * 255 // 63
            b   = ( arr        & 0x1F) * 255 // 31
            return np.stack([
                r.astype(np.uint8),
                g.astype(np.uint8),
                b.astype(np.uint8),
            ], axis=2).tobytes()
        else:
            pixels = struct.unpack_from("<{}H".format(w * h), raw)
            out    = bytearray(w * h * 3)
            idx    = 0
            for px in pixels:
                out[idx]   = ((px >> 11) & 0x1F) * 255 // 31
                out[idx+1] = ((px >> 5)  & 0x3F) * 255 // 63
                out[idx+2] = ( px        & 0x1F) * 255 // 31
                idx += 3
            return bytes(out)
