# -*- coding: utf-8 -*-
"""
Backend dispatcher - selects the best available encoder at runtime.
"""
from __future__ import absolute_import, print_function, division


def get_image_backend():
    try:
        from ..backends.GrabberPIL import PILGrabber
        if PILGrabber.is_available():
            return PILGrabber
    except Exception:
        pass
    try:
        from ..backends.GrabberOpenCV import OpenCVGrabber
        if OpenCVGrabber.is_available():
            return OpenCVGrabber
    except Exception:
        pass
    from ..backends.GrabberPPM import PPMGrabber
    return PPMGrabber


def get_video_backend():
    try:
        from ..backends.GrabberFFmpeg import get_ffmpeg
        if get_ffmpeg():
            return "ffmpeg"
    except Exception:
        pass
    try:
        from ..backends.GrabberGstreamer import GstRecorder
        if GstRecorder.is_available():
            return "gstreamer"
    except Exception:
        pass
    return "framezip"


def save_screenshot(rgb24, width, height, path, fmt="PNG"):
    backend = get_image_backend()
    if hasattr(backend, "save_pil"):
        return backend.save_pil(rgb24, width, height, path, fmt)
    elif hasattr(backend, "save"):
        return backend.save(rgb24, width, height, path, fmt)
    else:
        from ..backends.GrabberPPM import PPMGrabber
        if fmt.upper() == "PNG":
            return PPMGrabber.save_png(rgb24, width, height, path)
        return PPMGrabber.save_ppm(rgb24, width, height, path)
