# -*- coding: utf-8 -*-
"""
OpenCV (cv2) backend — optional enhancement.
"""
from __future__ import absolute_import, print_function, division

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class OpenCVGrabber(object):

    @staticmethod
    def is_available():
        return _CV2_AVAILABLE

    @staticmethod
    def save(rgb24, width, height, path, fmt="PNG"):
        if not _CV2_AVAILABLE:
            raise RuntimeError("OpenCV (cv2) not installed")
        import numpy as np
        arr = np.frombuffer(rgb24, dtype=np.uint8).reshape((height, width, 3))
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        ext = "." + fmt.lower()
        if fmt.upper() in ("JPEG", "JPG"):
            ext = ".jpg"
        cv2.imwrite(path, bgr)
        return path
