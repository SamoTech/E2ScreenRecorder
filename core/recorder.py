# -*- coding: utf-8 -*-
# v1.0.1 — post-audit patch
# Fixes: FIX-005 (on_error → main thread), FIX-006 (race-safe makedirs),
#        FIX-010 (300-frame ring cap + statvfs), FIX-015 (tmp_dir cleanup),
#        FIX-016 (zip path via splitext)
from __future__ import absolute_import, print_function, division

import os
import sys
import threading
import time
import shutil

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter
from ..utils.logger import log

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_FRAME_CAP    = 300    # FIX-010: max frames kept on disk at once (60s @ 5fps)
_MIN_FREE_MB  = 20     # FIX-010: minimum /tmp free space in MB


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
        self._frame_list = []   # FIX-010: capped ring list
        self._start_time = None
        self._tmp_dir    = None

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        if self._start_time is None:
            return 0
        return time.time() - self._start_time

    # ── Main recording loop ───────────────────────────────────────────────
    def run(self):
        tmp_dir = None
        fb      = None
        try:
            # FIX-006: race-safe unique tmp dir (pid + thread id)
            tid     = id(threading.current_thread())
            tmp_dir = "/tmp/e2rec_{}_{}" .format(os.getpid(), tid)  # FIX-006
            if not os.path.exists(tmp_dir):  # FIX-006: check before create
                try:
                    os.makedirs(tmp_dir)
                except OSError:
                    pass  # FIX-006: another thread may have created it first
            self._tmp_dir = tmp_dir

            fb = FramebufferCapture(device=self.fb_device)
            fb.open()
            info  = fb.get_info()
            w     = info["xres"]
            h     = info["yres"]
            delay = 1.0 / self.fps
            idx   = 0
            self._start_time = time.time()

            while not self._stop_event.is_set():
                t0 = time.time()

                # FIX-010: check free space before writing
                if not self._has_free_space(tmp_dir):
                    log.warn("Recorder: /tmp low on space, stopping early")
                    break

                try:
                    raw = fb.capture_raw()
                    rgb = PixelConverter.to_rgb24(raw, info)
                except Exception as e:
                    log.error("Frame capture error: {}".format(e))
                    time.sleep(delay)
                    continue

                frame_path = "{}/{:06d}.png".format(tmp_dir, idx)
                try:
                    self._write_frame(rgb, w, h, frame_path)
                except Exception as e:
                    log.error("Frame write error: {}".format(e))
                    time.sleep(delay)
                    continue

                # FIX-010: rolling cap — evict oldest frame when over limit
                self._frame_list.append(frame_path)
                if len(self._frame_list) > _FRAME_CAP:  # FIX-010
                    oldest = self._frame_list.pop(0)
                    try:
                        os.remove(oldest)
                    except OSError:
                        pass

                idx    += 1
                elapsed = time.time() - t0
                time.sleep(max(0.0, delay - elapsed))

            self._mux_frames(tmp_dir, w, h)

        except Exception as e:
            log.error("FrameRecorder.run() exception: {}".format(e))
            # FIX-005: push on_error to E2 main thread via reactor
            if callable(self.on_error):
                self._call_on_error(str(e))  # FIX-005
        finally:
            if fb is not None:
                try:
                    fb.close()
                except Exception:
                    pass
            # FIX-015: always clean up tmp_dir on exit
            if tmp_dir is not None:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)  # FIX-015
                except Exception:
                    pass

    # ── FIX-005: thread-safe error callback ───────────────────────────────
    def _call_on_error(self, msg):
        """FIX-005: on_error touches E2 UI widgets — must run in main thread."""
        try:
            from twisted.internet import reactor  # Enigma2 uses Twisted
            reactor.callLater(0, self.on_error, msg)  # FIX-005
        except Exception:
            try:
                self.on_error(msg)  # fallback: call directly
            except Exception:
                pass

    # ── Frame write ───────────────────────────────────────────────────────
    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            Image.frombytes("RGB", (w, h), rgb24).save(path)
        else:
            from ..backends.GrabberPPM import PPMGrabber
            PPMGrabber.save_png(rgb24, w, h, path)

    # ── Mux frames into video ─────────────────────────────────────────────
    def _mux_frames(self, tmp_dir, w, h):
        if not self._frame_list:
            log.warn("Recorder: no frames to mux")
            return
        try:
            from ..backends.GrabberFFmpeg import FFmpegRecorder
            info = {"xres": w, "yres": h, "bpp": 24}
            ffr  = FFmpegRecorder(info, self.output_path, fps=self.fps)
            if ffr.is_available():
                import subprocess
                cmd = [
                    ffr._binary,
                    "-framerate", str(self.fps),
                    "-i",         "{}/{}".format(tmp_dir, "%06d.png"),
                    "-c:v",       "libx264",
                    "-pix_fmt",   "yuv420p",
                    "-crf",       "28",
                    "-preset",    "ultrafast",
                    "-y",         self.output_path
                ]
                subprocess.call(cmd)
                log.info("Recorder: muxed via FFmpeg → {}".format(self.output_path))
                return
        except Exception as e:
            log.warn("FFmpeg mux failed: {}".format(e))

        # FIX-016: build zip path from splitext, not .mp4 string replace
        base     = os.path.splitext(self.output_path)[0]  # FIX-016
        zip_path = base + "_frames.zip"                   # FIX-016
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in self._frame_list:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))
            log.info("Recorder: saved frame zip → {}".format(zip_path))
        except Exception as e:
            log.error("ZIP fallback failed: {}".format(e))

    # ── FIX-010: free space check ─────────────────────────────────────────
    @staticmethod
    def _has_free_space(path):
        """FIX-010: return True if path has >= _MIN_FREE_MB MB free."""
        try:
            st = os.statvfs(path)  # FIX-010
            free_mb = (st.f_bavail * st.f_frsize) // (1024 * 1024)
            return free_mb >= _MIN_FREE_MB
        except Exception:
            return True  # if statvfs fails, assume OK
