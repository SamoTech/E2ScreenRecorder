# -*- coding: utf-8 -*-
"""
GStreamer Python binding backend.
"""
from __future__ import absolute_import, print_function, division

HAS_GST = False
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    HAS_GST = True
except Exception:
    try:
        import gst
        HAS_GST = True
    except Exception:
        pass


class GstRecorder(object):

    def __init__(self, fb_info, output_path, fps=5):
        self.fb_info     = fb_info
        self.output_path = output_path
        self.fps         = fps
        self._pipeline   = None

    @staticmethod
    def is_available():
        return HAS_GST

    def start(self):
        if not HAS_GST:
            raise RuntimeError("GStreamer not available")
        info = self.fb_info
        w, h = info["xres"], info["yres"]
        pipeline_str = (
            "filesrc location=/dev/fb0 "
            "! rawvideoparse width={w} height={h} format=bgra framerate={fps}/1 "
            "! videoconvert "
            "! x264enc tune=zerolatency speed-preset=ultrafast "
            "! mp4mux "
            "! filesink location={out}"
        ).format(w=w, h=h, fps=self.fps, out=self.output_path)
        try:
            self._pipeline = Gst.parse_launch(pipeline_str)
            self._pipeline.set_state(Gst.State.PLAYING)
        except Exception as e:
            raise RuntimeError("GStreamer pipeline failed: {}".format(e))

    def stop(self):
        if self._pipeline:
            try:
                self._pipeline.send_event(Gst.Event.new_eos())
                self._pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            self._pipeline = None
