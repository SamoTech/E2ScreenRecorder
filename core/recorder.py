# -*- coding: utf-8 -*-
"""
FrameRecorder - threaded continuous framebuffer capture engine.
Ring-buffer (30 frames max) for devices with <256 MB RAM.
Muxes captured frames to MP4 via FFmpeg when available,
otherwise falls back to a ZIP archive of PNG frames.
"""
from __future__ import absolute_import, print_function, division

import os
import threading
import time
import shutil

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter
from .compat      import makedirs_safe

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

RING_BUFFER_MAX = 30


class FrameRecorder(threading.Thread):

    def __init__(self, output_path, fps=5, fmt="mp4",
                 fb_device=None, on_error=None, low_ram=False):
        super(FrameRecorder, self).__init__()
        self.daemon      = True
        self.output_path = output_path
        self.fps         = max(1, min(fps, 25))
        self.fmt         = fmt
        self.fb_device   = fb_device
        self.on_error    = on_error
        self.low_ram     = low_ram
        self._stop_event = threading.Event()
        self._frame_list = []
        self._tmp_dir    = None
        self._lock       = threading.Lock()
        self.frames_captured = 0
        self.start_time      = 0.0

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

    def run(self):
        fb = FramebufferCapture(device=self.fb_device)
        try:
            fb.open()
            info  = fb.get_info()
            w, h  = info["xres"], info["yres"]
            delay = 1.0 / self.fps
            idx   = 0
            tmp_dir = "/tmp/e2rec_{}_{}".format(os.getpid(), int(time.time()))
            makedirs_safe(tmp_dir)
            self._tmp_dir   = tmp_dir
            self.start_time = time.time()

            while not self._stop_event.is_set():
                t0 = time.time()
                try:
                    raw = fb.capture_raw()
                    rgb = PixelConverter.to_rgb24(raw, info)
                    frame_path = "{0}/{1:06d}.png".format(tmp_dir, idx)
                    self._write_frame(rgb, w, h, frame_path)
                    with self._lock:
                        self._frame_list.append(frame_path)
                        if self.low_ram and len(self._frame_list) > RING_BUFFER_MAX:
                            old = self._frame_list.pop(0)
                            try:
                                os.remove(old)
                            except OSError:
                                pass
                    self.frames_captured = idx
                    idx += 1
                except Exception as e:
                    if callable(self.on_error):
                        self.on_error("Frame {}: {}".format(idx, e))

                elapsed = time.time() - t0
                sleep_t = max(0.0, delay - elapsed)
                if sleep_t > 0:
                    self._stop_event.wait(sleep_t)

            self._mux_frames(tmp_dir, w, h, info)
        except Exception as e:
            if callable(self.on_error):
                self.on_error(str(e))
        finally:
            fb.close()
            if self._tmp_dir and os.path.isdir(self._tmp_dir):
                try:
                    shutil.rmtree(self._tmp_dir)
                except Exception:
                    pass

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            img = Image.frombytes("RGB", (w, h), rgb24)
            img.save(path, "PNG")
        else:
            from ..backends.GrabberPPM import PPMGrabber
            PPMGrabber.save_png(rgb24, w, h, path)

    def _mux_frames(self, tmp_dir, w, h, info):
        from ..backends.GrabberFFmpeg import FFmpegRecorder
        ffr = FFmpegRecorder(info, self.output_path, fps=self.fps)
        if ffr.is_available():
            import subprocess
            cmd = [
                ffr._binary, "-y",
                "-framerate", str(self.fps),
                "-i", "{}/{}".format(tmp_dir, "%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "28", "-preset", "ultrafast",
                self.output_path,
            ]
            try:
                subprocess.call(cmd, stdout=open(os.devnull, "w"),
                                stderr=open(os.devnull, "w"))
            except Exception:
                self._fallback_zip()
        else:
            self._fallback_zip()

    def _fallback_zip(self):
        import zipfile
        zip_path = self.output_path.replace(".mp4", "_frames.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                with self._lock:
                    for fp in self._frame_list:
                        if os.path.isfile(fp):
                            zf.write(fp, os.path.basename(fp))
        except Exception:
            pass
