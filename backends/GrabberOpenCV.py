# -*- coding: utf-8 -*-
"""
OpenCV (cv2) backend - optional enhancement.
"""
from __future__ import absolute_import, print_function, division

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class OpenCVGrabber(object):

    @staticmethod
    def is_available():
        return HAS_CV2

    @staticmethod
    def save(rgb24, width, height, path, fmt="PNG", quality=85):
        if not HAS_CV2:
            raise ImportError("OpenCV not available")
        arr = np.frombuffer(rgb24, dtype=np.uint8).reshape((height, width, 3))
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        params = []
        if fmt.upper() in ("JPG", "JPEG"):
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        elif fmt.upper() == "PNG":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 6]
        cv2.imwrite(path, bgr, params)
        return path
