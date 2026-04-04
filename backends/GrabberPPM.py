# -*- coding: utf-8 -*-
"""
Pure Python PPM writer and minimal PNG encoder (zlib DEFLATE).
Zero external dependencies — works on any Python 2.7+ / 3.x.

Resolution fix:
  - save_png/save_ppm now clamp input to actual w*h*3 bytes
    to prevent corrupted output on virtual-fb over-reads
"""
from __future__ import absolute_import, print_function, division

import zlib
import struct
import io
import os


class PPMGrabber(object):

    @staticmethod
    def save_ppm(rgb24, width, height, path):
        """Write raw RGB24 to a .ppm file."""
        expected = width * height * 3
        rgb24    = (rgb24[:expected]
                    if len(rgb24) >= expected
                    else rgb24 + b"\x00" * (expected - len(rgb24)))
        header = "P6\n{} {}\n255\n".format(width, height).encode("ascii")
        with io.open(path, "wb") as f:
            f.write(header)
            f.write(rgb24)
        return path

    @staticmethod
    def save_png(rgb24, width, height, path):
        """
        Minimal spec-compliant PNG encoder.
        IDAT uses zlib level-6 deflate; filter byte 0x00 (None) per row.
        Produces a valid PNG readable by any viewer / ffmpeg / Pillow.
        """
        expected = width * height * 3
        rgb24    = (rgb24[:expected]
                    if len(rgb24) >= expected
                    else rgb24 + b"\x00" * (expected - len(rgb24)))

        def chunk(tag, data):
            crc_data = tag + data
            return (struct.pack(">I", len(data))
                    + crc_data
                    + struct.pack(">I", zlib.crc32(crc_data) & 0xFFFFFFFF))

        sig  = b"\x89PNG\r\n\x1a\n"
        ihdr = chunk(b"IHDR",
                     struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

        stride   = width * 3
        raw_rows = bytearray()
        for y in range(height):
            raw_rows += b"\x00"   # filter byte: None
            raw_rows += rgb24[y * stride: (y + 1) * stride]

        idat = chunk(b"IDAT", zlib.compress(bytes(raw_rows), 6))
        iend = chunk(b"IEND", b"")

        with io.open(path, "wb") as f:
            f.write(sig + ihdr + idat + iend)
        return path
