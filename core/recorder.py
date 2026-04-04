# -*- coding: utf-8 -*-
"""
Video recorder engine — daemon thread, ring buffer (low-RAM mode),
frame mux via FFmpeg or ZIP fallback.
"""
from __future__ import absolute_import, print_function, division

import threading
import time
import os

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

RING_SIZE = 30   # max frames kept in memory in low-RAM mode


class FrameRecorder(threading.Thread):

    def __init__(self, output_path, fps=5, fmt="mp4",
                 fb_device=None, on_error=None, low_ram=False):
        super(FrameRecorder, self).__init__()
        self.daemon      = True
        self.output_path = output_path
        self.fps         = fps
        self.fmt         = fmt
        self.fb_device   = fb_device
        self.on_error    = on_error
        self.low_ram     = low_ram
        self._stop_event = threading.Event()
        self._start_time = time.time()
        self._frame_list = []

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        return time.time() - self._start_time

    def run(self):
        fb = FramebufferCapture(self.fb_device)
        try:
            fb.open()
            info  = fb.get_info()
            w, h  = info["xres"], info["yres"]
            delay = 1.0 / max(1, self.fps)
            idx   = 0
            tmp_dir = "/tmp/e2rec_{}".format(os.getpid())
            try:
                os.makedirs(tmp_dir)
            except OSError:
                pass

            while not self._stop_event.is_set():
                t0  = time.time()
                raw = fb.capture_raw()
                rgb = PixelConverter.to_rgb24(raw, info)
                frame_path = "{}/{:06d}.png".format(tmp_dir, idx)
                self._write_frame(rgb, w, h, frame_path)

                if self.low_ram:
                    # Ring buffer: keep only last RING_SIZE frames on disk
                    self._frame_list.append(frame_path)
                    if len(self._frame_list) > RING_SIZE:
                        old = self._frame_list.pop(0)
                        try:
                            os.remove(old)
                        except OSError:
                            pass
                else:
                    self._frame_list.append(frame_path)

                idx += 1
                elapsed = time.time() - t0
                sleep_t = max(0.0, delay - elapsed)
                time.sleep(sleep_t)

            self._mux_frames(tmp_dir, w, h)
        except Exception as e:
            if callable(self.on_error):
                self.on_error(str(e))
        finally:
            fb.close()

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            try:
                Image.frombytes("RGB", (w, h), rgb24).save(path)
                return
            except Exception:
                pass
        from ..backends.GrabberPPM import PPMGrabber
        PPMGrabber.save_png(rgb24, w, h, path)

    def _mux_frames(self, tmp_dir, w, h):
        from ..backends.GrabberFFmpeg import get_ffmpeg
        ffmpeg = get_ffmpeg()
        if ffmpeg and self._frame_list:
            import subprocess
            cmd = [
                ffmpeg,
                "-framerate", str(self.fps),
                "-i", "{}/{}".format(tmp_dir, "%06d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "28",
                "-preset", "ultrafast",
                "-y", self.output_path
            ]
            subprocess.call(cmd)
        else:
            # ZIP fallback
            import zipfile
            zip_path = self.output_path.rsplit(".", 1)[0] + "_frames.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for fp in self._frame_list:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))
