# -*- coding: utf-8 -*-
"""
GStreamer backend (optional — native Enigma2 integration).
"""
from __future__ import absolute_import, print_function, division

try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    _GST_AVAILABLE = True
except Exception:
    _GST_AVAILABLE = False


class GstRecorder(object):

    @staticmethod
    def is_available():
        return _GST_AVAILABLE

    def __init__(self, output_path, fps=5, width=1920, height=1080):
        self.output_path = output_path
        self.fps         = fps
        self.width       = width
        self.height      = height
        self._pipeline   = None

    def start(self):
        if not _GST_AVAILABLE:
            raise RuntimeError("GStreamer not available")
        pipeline_str = (
            "v4l2src device=/dev/fb0 ! "
            "video/x-raw,width={w},height={h},framerate={fps}/1 ! "
            "videoconvert ! x264enc speed-preset=ultrafast ! "
            "mp4mux ! filesink location={out}"
        ).format(w=self.width, h=self.height,
                 fps=self.fps, out=self.output_path)
        self._pipeline = Gst.parse_launch(pipeline_str)
        self._pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
