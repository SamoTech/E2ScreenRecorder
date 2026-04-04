# -*- coding: utf-8 -*-
"""
Pure Python PPM writer and PNG encoder (DEFLATE via zlib).
Zero external dependencies - works on ANY Python version.
"""
from __future__ import absolute_import, print_function, division

import io
import struct
import zlib


class PPMGrabber(object):

    @staticmethod
    def save_ppm(rgb24, width, height, path):
        header = "P6\n{} {}\n255\n".format(width, height).encode("ascii")
        with io.open(path, "wb") as f:
            f.write(header)
            f.write(rgb24)
        return path

    @staticmethod
    def save_png(rgb24, width, height, path):
        def _chunk(name, data):
            c = name + data
            crc = zlib.crc32(c) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

        sig       = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr      = _chunk(b"IHDR", ihdr_data)
        stride    = width * 3
        rows = []
        for y in range(height):
            rows.append(b'\x00')
            rows.append(rgb24[y * stride:(y + 1) * stride])
        compressed = zlib.compress(b"".join(rows), 6)
        idat = _chunk(b"IDAT", compressed)
        iend = _chunk(b"IEND", b"")
        with io.open(path, "wb") as f:
            f.write(sig + ihdr + idat + iend)
        return path

    @staticmethod
    def save_jpeg_approx(rgb24, width, height, path, quality=85):
        ppm_path = path.replace(".jpg", ".ppm").replace(".jpeg", ".ppm")
        return PPMGrabber.save_ppm(rgb24, width, height, ppm_path)
