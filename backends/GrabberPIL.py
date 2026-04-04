# -*- coding: utf-8 -*-
"""
PIL/Pillow backend - best quality screenshots.
"""
from __future__ import absolute_import, print_function, division

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    try:
        import Image
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False


class PILGrabber(object):

    @staticmethod
    def is_available():
        return HAS_PIL

    @staticmethod
    def save_pil(rgb24, width, height, path, fmt="PNG", quality=85):
        if not HAS_PIL:
            raise ImportError("PIL/Pillow not available")
        img = Image.frombytes("RGB", (width, height), rgb24)
        fmt_upper = fmt.upper()
        if fmt_upper in ("JPEG", "JPG"):
            img.save(path, "JPEG", quality=quality, optimize=True)
        elif fmt_upper == "BMP":
            img.save(path, "BMP")
        else:
            img.save(path, "PNG", optimize=True)
        return path

    @staticmethod
    def get_thumbnail(rgb24, width, height, thumb_size=(320, 180)):
        if not HAS_PIL:
            return None
        img = Image.frombytes("RGB", (width, height), rgb24)
        img.thumbnail(thumb_size,
                      Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS)
        return img
