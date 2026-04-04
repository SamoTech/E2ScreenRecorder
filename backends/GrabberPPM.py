# -*- coding: utf-8 -*-
"""
Pure Python PPM writer and PNG encoder (DEFLATE via zlib).
Guaranteed to work on ANY Python version with ZERO external deps.
"""
from __future__ import absolute_import, print_function, division

import zlib
import struct
import io
import os
import time


class PPMGrabber(object):

    @staticmethod
    def is_available():
        return True

    @staticmethod
    def save_ppm(rgb24, width, height, path):
        header = "P6\n{} {}\n255\n".format(width, height).encode("ascii")
        with io.open(path, "wb") as f:
            f.write(header)
            f.write(rgb24)
        return path

    @staticmethod
    def save_png(rgb24, width, height, path):
        def chunk(name, data):
            c = name + data
            crc = zlib.crc32(c) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

        sig  = b'\x89PNG\r\n\x1a\n'
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

        stride   = width * 3
        raw_rows = b""
        for y in range(height):
            raw_rows += b'\x00' + rgb24[y * stride:(y + 1) * stride]
        compressed = zlib.compress(raw_rows, 6)
        idat = chunk(b"IDAT", compressed)
        iend = chunk(b"IEND", b"")

        with io.open(path, "wb") as f:
            f.write(sig + ihdr + idat + iend)
        return path

    @staticmethod
    def save(rgb24, width, height, path, fmt="PNG"):
        fmt = fmt.upper()
        if fmt == "PNG":
            return PPMGrabber.save_png(rgb24, width, height, path)
        return PPMGrabber.save_ppm(rgb24, width, height, path)
