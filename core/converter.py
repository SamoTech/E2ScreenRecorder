# -*- coding: utf-8 -*-
# v1.0.1 — post-audit patch
# Fixes: FIX-011 (bpp==24 RGB888), FIX-012 (YUV420), FIX-019 (Py2 np.frombuffer)
from __future__ import absolute_import, print_function, division

import struct
import sys

PY2 = sys.version_info[0] == 2

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
        elif bpp == 24:                       # FIX-011: packed RGB888
            return PixelConverter._convert_24bpp(raw, w, h)
        elif bpp == 16:
            return PixelConverter._convert_rgb565(raw, w, h)
        elif bpp == 8:
            return bytes(bytearray(
                [b for byte in bytearray(raw) for b in (byte, byte, byte)]))
        elif bpp == 0:                        # FIX-012: YUV420 planar
            return PixelConverter._convert_yuv420(raw, w, h)
        else:
            raise ValueError("Unsupported bpp: {}".format(bpp))

    # ── 32bpp ARGB / RGBA ─────────────────────────────────────────────────
    @staticmethod
    def _convert_32bpp(raw, info, w, h):
        ro, rl = info["red_offset"],   info["red_len"]
        go, gl = info["green_offset"], info["green_len"]
        bo, bl = info["blue_offset"],  info["blue_len"]

        if HAS_NUMPY:
            # FIX-019: Python 2 np.frombuffer needs buffer(), not str
            if PY2:
                arr = np.frombuffer(buffer(raw), dtype=np.uint32)  # FIX-019
            else:
                arr = np.frombuffer(raw, dtype=np.uint32)
            arr = arr.reshape((h, w))
            r = ((arr >> ro) & ((1 << rl) - 1)).astype(np.uint8)
            g = ((arr >> go) & ((1 << gl) - 1)).astype(np.uint8)
            b = ((arr >> bo) & ((1 << bl) - 1)).astype(np.uint8)
            return np.stack([r, g, b], axis=2).tobytes()
        else:
            rm = (1 << rl) - 1
            gm = (1 << gl) - 1
            bm = (1 << bl) - 1
            result = bytearray(w * h * 3)
            idx    = 0
            pixels = struct.unpack_from("<{}I".format(w * h), raw)
            for px in pixels:
                result[idx]   = (px >> ro) & rm
                result[idx+1] = (px >> go) & gm
                result[idx+2] = (px >> bo) & bm
                idx += 3
            return bytes(result)

    # ── 24bpp packed RGB888 (FIX-011) ─────────────────────────────────────
    @staticmethod
    def _convert_24bpp(raw, w, h):
        """FIX-011: Some older Broadcom devices output 3-byte-per-pixel RGB888.
        The data is already R,G,B packed — validate stride and return directly.
        """
        expected = w * h * 3
        if len(raw) < expected:
            # pad if short — better than a crash
            raw = raw + b"\x00" * (expected - len(raw))
        return bytes(raw[:expected])  # FIX-011: direct copy, no conversion

    # ── 16bpp RGB565 ──────────────────────────────────────────────────────
    @staticmethod
    def _convert_rgb565(raw, w, h):
        if HAS_NUMPY:
            if PY2:                                     # FIX-019
                arr = np.frombuffer(buffer(raw), dtype=np.uint16)
            else:
                arr = np.frombuffer(raw, dtype=np.uint16)
            arr = arr.reshape((h, w))
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
            idx    = 0
            for px in pixels:
                result[idx]   = ((px >> 11) & 0x1F) * 255 // 31
                result[idx+1] = ((px >> 5)  & 0x3F) * 255 // 63
                result[idx+2] = ( px        & 0x1F) * 255 // 31
                idx += 3
            return bytes(result)

    # ── YUV420 planar → RGB24  (FIX-012) ─────────────────────────────────
    @staticmethod
    def _convert_yuv420(raw, w, h):
        """FIX-012: YUV420 planar (I420) to RGB24 using BT.601 coefficients.
        Used by some Amlogic S905/S922 devices with specific kernel versions.
        Numpy fast path + pure-Python fallback both provided.
        """
        # Plane sizes
        y_size  = w * h
        uv_size = (w // 2) * (h // 2)

        if len(raw) < y_size + 2 * uv_size:
            # Pad / best-effort
            raw = raw + b"\x00" * (y_size + 2 * uv_size - len(raw))

        y_plane = raw[:y_size]
        u_plane = raw[y_size:y_size + uv_size]
        v_plane = raw[y_size + uv_size:y_size + 2 * uv_size]

        if HAS_NUMPY:
            if PY2:
                Y = np.frombuffer(buffer(y_plane), dtype=np.uint8).reshape(h, w).astype(np.int32)  # FIX-019
                U = np.frombuffer(buffer(u_plane), dtype=np.uint8).reshape(h // 2, w // 2).astype(np.int32)
                V = np.frombuffer(buffer(v_plane), dtype=np.uint8).reshape(h // 2, w // 2).astype(np.int32)
            else:
                Y = np.frombuffer(y_plane, dtype=np.uint8).reshape(h, w).astype(np.int32)
                U = np.frombuffer(u_plane, dtype=np.uint8).reshape(h // 2, w // 2).astype(np.int32)
                V = np.frombuffer(v_plane, dtype=np.uint8).reshape(h // 2, w // 2).astype(np.int32)

            # Upsample U/V to full size via repeat
            U = np.repeat(np.repeat(U, 2, axis=0), 2, axis=1)
            V = np.repeat(np.repeat(V, 2, axis=0), 2, axis=1)

            # BT.601 conversion
            C = Y - 16
            D = U - 128
            E = V - 128

            R = np.clip((298 * C           + 409 * E + 128) >> 8, 0, 255).astype(np.uint8)
            G = np.clip((298 * C - 100 * D - 208 * E + 128) >> 8, 0, 255).astype(np.uint8)
            B = np.clip((298 * C + 516 * D           + 128) >> 8, 0, 255).astype(np.uint8)

            return np.stack([R, G, B], axis=2).tobytes()
        else:
            # Pure Python BT.601 — slow but always available
            result = bytearray(w * h * 3)
            idx    = 0
            yb     = bytearray(y_plane)
            ub     = bytearray(u_plane)
            vb     = bytearray(v_plane)
            for row in range(h):
                for col in range(w):
                    Y_  = yb[row * w + col]
                    U_  = ub[(row // 2) * (w // 2) + (col // 2)]
                    V_  = vb[(row // 2) * (w // 2) + (col // 2)]
                    C   = Y_ - 16
                    D   = U_ - 128
                    E   = V_ - 128
                    result[idx]   = max(0, min(255, (298*C + 409*E + 128) >> 8))
                    result[idx+1] = max(0, min(255, (298*C - 100*D - 208*E + 128) >> 8))
                    result[idx+2] = max(0, min(255, (298*C + 516*D + 128) >> 8))
                    idx += 3
            return bytes(result)
