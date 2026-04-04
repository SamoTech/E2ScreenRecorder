# -*- coding: utf-8 -*-
"""
Video recorder engine using framebuffer + PIL or PPM backend.
Runs in a background daemon thread; communicates via threading.Event.
Supports ring-buffer mode for low-RAM devices (<= 256 MB).
"""
from __future__ import absolute_import, print_function, division

import threading
import time
import os
import io
import shutil

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

RING_BUFFER_MAX = 30  # frames kept in low-RAM mode


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
        self._frame_list = []
        self._start_time = None

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        if self._start_time is None:
            return 0
        return time.time() - self._start_time

    def run(self):
        fb = FramebufferCapture(device=self.fb_device)
        tmp_dir = "/tmp/e2rec_{}".format(os.getpid())
        try:
            fb.open()
            info  = fb.get_info()
            w, h  = info["xres"], info["yres"]
            delay = 1.0 / self.fps
            idx   = 0

            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            self._start_time = time.time()

            while not self._stop_event.is_set():
                t0  = time.time()
                raw = fb.capture_raw()
                rgb = PixelConverter.to_rgb24(raw, info)
                frame_path = "{}/{:06d}.png".format(tmp_dir, idx)
                self._write_frame(rgb, w, h, frame_path)

                # Ring buffer: drop oldest frame in low-RAM mode
                if self.low_ram and len(self._frame_list) >= RING_BUFFER_MAX:
                    oldest = self._frame_list.pop(0)
                    try:
                        os.remove(oldest)
                    except OSError:
                        pass

                self._frame_list.append(frame_path)
                idx += 1

                elapsed = time.time() - t0
                sleep_t = max(0, delay - elapsed)
                time.sleep(sleep_t)

            self._mux_frames(tmp_dir, w, h)
        except Exception as e:
            if callable(self.on_error):
                self.on_error(str(e))
        finally:
            fb.close()
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            Image.frombytes("RGB", (w, h), rgb24).save(path)
        else:
            from ..backends.GrabberPPM import PPMGrabber
            PPMGrabber.save_png(rgb24, w, h, path)

    def _mux_frames(self, tmp_dir, w, h):
        from ..backends.GrabberFFmpeg import FFmpegRecorder
        info = {"xres": w, "yres": h, "bpp": 24}
        ffr  = FFmpegRecorder(info, self.output_path, fps=self.fps)
        if ffr.is_available():
            import subprocess
            cmd = [
                ffr._binary,
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
            import zipfile
            zip_path = self.output_path.replace(".mp4", "_frames.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                for fp in self._frame_list:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))
