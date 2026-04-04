# -*- coding: utf-8 -*-
"""
Pillow/PIL backend for screenshot capture.

Resolution fix:
  - Uses actual fb_info xres/yres, never xres_virtual/yres_virtual
  - Explicit RGB mode in frombytes() to prevent channel swap
  - Optional SD upscale: frames <=720x576 upscaled to 1280x720
    using LANCZOS resampling when upscale=True
"""
from __future__ import absolute_import, print_function, division

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


def _lanczos():
    """Return correct LANCZOS constant across Pillow versions."""
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


class PILGrabber(object):

    @staticmethod
    def is_available():
        return _PIL_OK

    @staticmethod
    def save_pil(rgb24, width, height, path, fmt="PNG", upscale=False):
        """
        Save RGB24 bytes to image file.

        Args:
            rgb24   : raw RGB24 bytes (width*height*3)
            width   : actual display width  (xres, NOT xres_virtual)
            height  : actual display height (yres, NOT yres_virtual)
            path    : output file path
            fmt     : PIL format string (PNG, JPEG, BMP ...)
            upscale : if True and frame is SD (<=720x576), upscale to 720p
        """
        if not _PIL_OK:
            raise RuntimeError("Pillow not installed")

        # Clamp buffer to actual display dimensions
        expected = width * height * 3
        if len(rgb24) > expected:
            rgb24 = rgb24[:expected]
        elif len(rgb24) < expected:
            # Pad with black to avoid frombytes crash
            rgb24 = rgb24 + b"\x00" * (expected - len(rgb24))

        img = Image.frombytes("RGB", (width, height), rgb24)

        # Optional SD -> 720p upscale
        if upscale and width <= 720 and height <= 576:
            img = img.resize((1280, 720), _lanczos())

        # JPEG needs quality kwarg
        save_kwargs = {}
        if fmt.upper() in ("JPEG", "JPG"):
            save_kwargs["quality"]  = 92
            save_kwargs["optimize"] = True
            fmt = "JPEG"
        elif fmt.upper() == "PNG":
            save_kwargs["optimize"] = True

        img.save(path, fmt, **save_kwargs)
        return path
