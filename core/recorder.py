# -*- coding: utf-8 -*-
"""
Video recorder engine.

Strategy selection (in priority order):
  1. FFmpeg fbdev live capture  — best quality, lowest RAM, preferred
  2. Frame-by-frame PNG + mux   — fallback when ffmpeg missing
  3. Frame-by-frame PNG + ZIP   — last resort (no muxer at all)

The recorder runs in a daemon thread.  UI communicates via:
  - stop()       : signal the thread to finish
  - is_alive()   : check if still running  (threading.Thread builtin)
  - elapsed()    : seconds since start (for WebIF REC timer)
"""
from __future__ import absolute_import, print_function, division

import os
import sys
import time
import threading
import zipfile

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter
from ..utils.logger import log

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Ring-buffer limit for low-RAM mode (≤256 MB devices)
_RING_BUFFER_MAX = 30


class FrameRecorder(threading.Thread):
    """
    Background recording thread.

    Parameters
    ----------
    output_path : str   destination file path
    fps         : int   target capture rate
    fmt         : str   container format hint (mp4/mkv/avi/ts)
    fb_device   : str|None  /dev/fb0 or /dev/fb1; None = auto-detect
    on_error    : callable(str) | None
    low_ram     : bool  enable ring-buffer frame cap for <256 MB devices
    """

    def __init__(self, output_path, fps=5, fmt="mkv",
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
        self._ffmpeg_rec = None   # hold reference for stop()

    def stop(self):
        """Signal the recording thread to finish."""
        self._stop_event.set()
        # Also stop ffmpeg immediately if Strategy 1 is running
        if self._ffmpeg_rec is not None:
            try:
                self._ffmpeg_rec.stop()
            except Exception:
                pass

    def elapsed(self):
        """Return elapsed seconds since recording started (float)."""
        return time.time() - self._start_time

    # ── Main thread entry ──────────────────────────────────────────────────

    def run(self):
        self._start_time = time.time()
        try:
            if self._try_ffmpeg_live():
                return   # Strategy 1 handled everything
            self._run_frame_fallback()   # Strategy 2 / 3
        except Exception as e:
            log.error("FrameRecorder.run exception: {}".format(e))
            if callable(self.on_error):
                self.on_error(str(e))

    # ── Strategy 1: FFmpeg fbdev live capture ──────────────────────────────

    def _try_ffmpeg_live(self):
        """
        Attempt direct live capture via `ffmpeg -f fbdev`.

        Returns True if ffmpeg was found and the recording session
        completed (or was stopped).  Returns False if ffmpeg is
        unavailable so the caller can fall back to Strategy 2.
        """
        try:
            from ..backends.GrabberFFmpeg import FFmpegRecorder, get_ffmpeg
        except ImportError:
            log.warning("GrabberFFmpeg import failed — using frame fallback")
            return False

        if not get_ffmpeg():
            log.info("ffmpeg not found — using frame fallback")
            return False

        device = self.fb_device or self._auto_detect_fb()
        log.info("Strategy 1: ffmpeg fbdev live → {} (device={})".format(
            self.output_path, device))

        rec = FFmpegRecorder(
            output_path=self.output_path,
            fps=self.fps,
            fb_device=device,
        )
        self._ffmpeg_rec = rec
        rec.start()

        # Block until stop() is called or ffmpeg dies on its own
        while not self._stop_event.is_set():
            if not rec.is_running():
                log.warning("ffmpeg exited unexpectedly")
                break
            time.sleep(0.5)

        rec.stop()
        self._ffmpeg_rec = None
        log.info("Strategy 1 success: {}".format(self.output_path))
        return True

    # ── Strategy 2 / 3: frame-by-frame PNG capture ────────────────────────

    def _auto_detect_fb(self):
        """
        Try /dev/fb0 first.  If the first 256 bytes are all zero (blank),
        fall back to /dev/fb1 (HiSilicon / some BCM boxes).
        """
        for dev in ("/dev/fb0", "/dev/fb1"):
            if not os.path.exists(dev):
                continue
            try:
                fd = os.open(dev, os.O_RDONLY)
                sample = os.read(fd, 256)
                os.close(fd)
                if any(b != 0 for b in bytearray(sample)):
                    log.info("Auto-detected framebuffer: {}".format(dev))
                    return dev
            except Exception:
                continue
        log.warning("Could not auto-detect FB device, defaulting to /dev/fb0")
        return "/dev/fb0"

    def _run_frame_fallback(self):
        """Capture individual PNG frames then mux or ZIP them."""
        device  = self.fb_device or self._auto_detect_fb()
        fb      = FramebufferCapture(device=device)
        try:
            fb.open()
        except Exception as e:
            raise RuntimeError("Cannot open {}: {}".format(device, e))

        info    = fb.get_info()
        w, h    = info["xres"], info["yres"]
        delay   = 1.0 / self.fps
        idx     = 0
        tmp_dir = "/tmp/e2rec_{}".format(os.getpid())

        try:
            os.makedirs(tmp_dir)
        except OSError:
            pass

        frame_paths = []

        try:
            while not self._stop_event.is_set():
                t0  = time.time()
                raw = fb.capture_raw()
                rgb = PixelConverter.to_rgb24(raw, info)
                frame_path = os.path.join(tmp_dir, "{:06d}.png".format(idx))
                self._write_frame(rgb, w, h, frame_path)

                if self.low_ram:
                    # Ring buffer: discard oldest frame when over limit
                    frame_paths.append(frame_path)
                    if len(frame_paths) > _RING_BUFFER_MAX:
                        old = frame_paths.pop(0)
                        try:
                            os.remove(old)
                        except Exception:
                            pass
                else:
                    frame_paths.append(frame_path)

                idx += 1
                elapsed = time.time() - t0
                time.sleep(max(0.0, delay - elapsed))
        finally:
            fb.close()

        log.info("Frame capture done: {} frames".format(len(frame_paths)))
        self._mux_or_zip(frame_paths, tmp_dir)

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            Image.frombytes("RGB", (w, h), rgb24).save(path)
        else:
            from ..backends.GrabberPPM import PPMGrabber
            PPMGrabber.save_png(rgb24, w, h, path)

    def _mux_or_zip(self, frame_paths, tmp_dir):
        """Strategy 2: mux with ffmpeg.  Strategy 3: ZIP fallback."""
        try:
            from ..backends.GrabberFFmpeg import get_ffmpeg
            binary = get_ffmpeg()
        except ImportError:
            binary = None

        if binary and frame_paths:
            import subprocess
            cmd = [
                binary,
                "-framerate", str(self.fps),
                "-i", os.path.join(tmp_dir, "%06d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "28",
                "-preset", "ultrafast",
                "-y", self.output_path,
            ]
            log.info("Strategy 2 mux: {}".format(" ".join(cmd)))
            ret = subprocess.call(cmd)
            if ret == 0:
                log.info("Strategy 2 success: {}".format(self.output_path))
                return
            log.warning("Strategy 2 mux failed (exit {}), falling to ZIP".format(ret))

        # Strategy 3: ZIP archive of PNG frames
        zip_path = self.output_path.rsplit(".", 1)[0] + "_frames.zip"
        log.info("Strategy 3: saving frames as ZIP → {}".format(zip_path))
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in frame_paths:
                if os.path.isfile(fp):
                    zf.write(fp, os.path.basename(fp))
        log.info("Strategy 3 done: {}".format(zip_path))
