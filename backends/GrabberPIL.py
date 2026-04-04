# -*- coding: utf-8 -*-
"""
Pillow/PIL backend for screenshot saving.
"""
from __future__ import absolute_import, print_function, division

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class PILGrabber(object):

    @staticmethod
    def is_available():
        return _PIL_AVAILABLE

    @staticmethod
    def save_pil(rgb24, width, height, path, fmt="PNG"):
        if not _PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        fmt = fmt.upper()
        img = Image.frombytes("RGB", (width, height), rgb24)
        save_kwargs = {}
        if fmt in ("JPEG", "JPG"):
            save_kwargs["quality"] = 85
            save_kwargs["optimize"] = True
            fmt = "JPEG"
        img.save(path, fmt, **save_kwargs)
        return path

    @staticmethod
    def save(rgb24, width, height, path, fmt="PNG"):
        return PILGrabber.save_pil(rgb24, width, height, path, fmt)
