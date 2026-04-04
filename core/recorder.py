# -*- coding: utf-8 -*-
"""
core/recorder.py
~~~~~~~~~~~~~~~~
Threaded video recorder engine with pre-flight framebuffer validation,
ring-buffer low-RAM mode, and post-recording output verification.

Python 2.7 – 3.12+ compatible. No f-strings. No walrus. No match.
All exceptions are routed to the on_error callback so the Enigma2 main
thread can present them in the UI without crashing.
"""
from __future__ import absolute_import, print_function, division

import os
import sys
import threading
import time
import struct

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter
from ..utils.logger import log

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Custom exception ─────────────────────────────────────────────────────────

class FramebufferError(RuntimeError):
    """Raised when no readable framebuffer device can be found."""
    pass


# ── Low-level FB validation helpers ─────────────────────────────────────────

_FB_CANDIDATES = ["/dev/fb0", "/dev/fb1"]
_BLANK_CHECK_BYTES = 512          # bytes sampled for blank-frame detection
_LOW_RAM_RING_SIZE = 30           # max frames kept in memory on low-RAM devices
_FFMPEG_LOG = "/tmp/ffmpeg_e2rec.log"


def detect_framebuffer(preferred=None):
    """
    Return the path of the first usable framebuffer device.

    Order:
      1. ``preferred``  if given and readable (config override)
      2. /dev/fb0       standard primary
      3. /dev/fb1       HiSilicon overlay / secondary OSD

    For each candidate that exists and is readable, read the first
    ``_BLANK_CHECK_BYTES`` bytes.  If they are all-zero (blank frame),
    continue to the next candidate — this is the HiSilicon /dev/fb0
    always-blank issue.  If ALL candidates produce blank frames, return
    the first readable one anyway (better than nothing).

    Raises :class:`FramebufferError` if no device is accessible at all.
    """
    candidates = list(_FB_CANDIDATES)
    if preferred and preferred not in candidates:
        candidates.insert(0, preferred)
    elif preferred:
        candidates = [preferred] + [c for c in candidates if c != preferred]

    readable   = []
    non_blank  = []

    for path in candidates:
        if not os.path.exists(path):
            log.debug("detect_framebuffer: {} not found".format(path))
            continue
        if not os.access(path, os.R_OK):
            log.debug("detect_framebuffer: {} not readable".format(path))
            continue

        readable.append(path)
        try:
            fd = os.open(path, os.O_RDONLY)
            sample = os.read(fd, _BLANK_CHECK_BYTES)
            os.close(fd)
        except OSError as exc:
            log.warning("detect_framebuffer: read sample failed on {}: {}".format(
                path, exc))
            continue

        # bytearray works identically on Py2 and Py3
        if any(b != 0 for b in bytearray(sample)):
            non_blank.append(path)
            log.info("detect_framebuffer: non-blank framebuffer at {}".format(path))
        else:
            log.warning(
                "detect_framebuffer: {} exists but produces all-zero "
                "sample (HiSilicon blank-frame?) — trying next".format(path))

    if non_blank:
        chosen = non_blank[0]
        log.info("[Recorder] Found valid framebuffer: {}".format(chosen))
        return chosen

    if readable:
        chosen = readable[0]
        log.warning(
            "[Recorder] All candidates blank; using first readable: "
            "{}".format(chosen))
        return chosen

    raise FramebufferError(
        "Video recorder failed: No framebuffer device detected "
        "({}).  Please check hardware.".format(
            ", ".join(candidates)))


# ── Ring-buffer helper ───────────────────────────────────────────────────────

class _RingBuffer(object):
    """Fixed-size list that discards the oldest entry on overflow."""

    def __init__(self, maxlen):
        self._maxlen = maxlen
        self._buf    = []

    def append(self, item):
        if len(self._buf) >= self._maxlen:
            evicted = self._buf.pop(0)
            try:
                os.remove(evicted)
            except OSError:
                pass
        self._buf.append(item)

    def __iter__(self):
        return iter(list(self._buf))

    def __len__(self):
        return len(self._buf)


# ── Main recorder thread ─────────────────────────────────────────────────────

class FrameRecorder(threading.Thread):
    """
    Daemon thread that:
      1. Validates the framebuffer with :func:`detect_framebuffer`.
      2. Captures frames at ``fps`` Hz into a temp directory.
      3. On stop, muxes the frames with FFmpeg (falls back to ZIP).

    All errors are forwarded to ``on_error(msg)`` so the Enigma2 UI
    thread can react without being blocked.
    """

    def __init__(self, output_path, fps=5, fmt="mp4",
                 fb_device=None, on_error=None, low_ram=False):
        super(FrameRecorder, self).__init__()
        self.daemon       = True
        self.output_path  = output_path
        self.fps          = fps
        self.fmt          = fmt
        self._preferred   = fb_device   # may be None → auto-detect
        self.on_error     = on_error
        self.low_ram      = low_ram
        self._stop_event  = threading.Event()
        self._start_time  = None
        self._device_path = None        # resolved at run() time

        if low_ram:
            self._frame_list = _RingBuffer(_LOW_RAM_RING_SIZE)
        else:
            self._frame_list = []

    # ── Public API ────────────────────────────────────────────────────────

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        """Return seconds elapsed since recording started (float)."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    # ── Thread body ───────────────────────────────────────────────────────

    def run(self):
        # ── 1. Pre-flight: validate framebuffer ──────────────────────────
        try:
            self._device_path = detect_framebuffer(self._preferred)
        except FramebufferError as exc:
            msg = str(exc)
            log.error(msg)
            if callable(self.on_error):
                self.on_error(msg)
            return

        # ── 2. Open framebuffer and capture frames ───────────────────────
        fb = FramebufferCapture(device=self._device_path)
        tmp_dir = "/tmp/e2rec_{}".format(os.getpid())
        try:
            fb.open()
            info  = fb.get_info()
            w, h  = info["xres"], info["yres"]
            delay = 1.0 / max(1, self.fps)
            idx   = 0

            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            self._start_time = time.time()
            log.info("[Recorder] Recording started on {} -> {}".format(
                self._device_path, self.output_path))

            while not self._stop_event.is_set():
                t0  = time.time()
                try:
                    raw = fb.capture_raw()
                    rgb = PixelConverter.to_rgb24(raw, info)
                    frame_path = "{}/{:06d}.png".format(tmp_dir, idx)
                    self._write_frame(rgb, w, h, frame_path)
                    self._frame_list.append(frame_path)
                    idx += 1
                except Exception as frame_exc:
                    log.warning("[Recorder] Frame {} capture error: {}".format(
                        idx, frame_exc))

                elapsed_frame = time.time() - t0
                sleep_t = max(0.0, delay - elapsed_frame)
                time.sleep(sleep_t)

        except Exception as exc:
            msg = "[Recorder] Fatal error during capture: {}".format(exc)
            log.error(msg)
            if callable(self.on_error):
                self.on_error(msg)
            return
        finally:
            fb.close()

        # ── 3. Mux collected frames into output file ─────────────────────
        self._mux_frames(tmp_dir, w, h)

        # ── 4. Post-recording output verification ─────────────────────────
        self._verify_output()

        # ── 5. Clean up temp frames ───────────────────────────────────────
        self._cleanup_tmp(tmp_dir)

    # ── Frame writer ──────────────────────────────────────────────────────

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            try:
                Image.frombytes("RGB", (w, h), rgb24).save(path)
                return
            except Exception as exc:
                log.debug("PIL frame write failed ({}), using PPM".format(exc))
        from ..backends.GrabberPPM import PPMGrabber
        PPMGrabber.save_png(rgb24, w, h, path)

    # ── Muxer ─────────────────────────────────────────────────────────────

    def _mux_frames(self, tmp_dir, w, h):
        from ..backends.GrabberFFmpeg import get_ffmpeg
        binary = get_ffmpeg()
        if binary:
            import subprocess
            cmd = [
                binary,
                "-framerate", str(self.fps),
                "-i",         "{}/{}.png".format(tmp_dir, "%06d"),
                "-c:v",       "libx264",
                "-pix_fmt",   "yuv420p",
                "-crf",       "28",
                "-preset",    "ultrafast",
                "-y",
                self.output_path,
            ]
            log.info("[Recorder] Muxing with FFmpeg: {}".format(
                " ".join(cmd)))
            try:
                with open(_FFMPEG_LOG, "w") as lf:
                    ret = subprocess.call(
                        cmd,
                        stdout=lf,
                        stderr=lf,
                        close_fds=True,
                    )
                if ret != 0:
                    log.error(
                        "[Recorder] FFmpeg mux exited with code {}. "
                        "See {}".format(ret, _FFMPEG_LOG))
            except Exception as exc:
                log.error("[Recorder] FFmpeg mux exception: {}".format(exc))
                self._fallback_zip()
        else:
            log.warning("[Recorder] FFmpeg not found; saving frame ZIP.")
            self._fallback_zip()

    def _fallback_zip(self):
        import zipfile
        zip_path = self.output_path.replace("." + self.fmt, "_frames.zip")
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                for fp in self._frame_list:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))
            log.info("[Recorder] Frame ZIP saved: {}".format(zip_path))
        except Exception as exc:
            log.error("[Recorder] ZIP fallback failed: {}".format(exc))

    # ── Output verification ───────────────────────────────────────────────

    def _verify_output(self):
        """
        Check that the output file exists and is non-empty.
        Delete 0-byte junk files and report the failure via on_error.
        """
        path = self.output_path
        if not os.path.exists(path):
            # FFmpeg may have written a ZIP instead — that is OK.
            zip_path = path.replace("." + self.fmt, "_frames.zip")
            if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                log.info("[Recorder] Output is ZIP fallback: {}".format(zip_path))
                return
            msg = (
                "[ERROR] Recording finished but output file not found: {}. "
                "Check {}".format(path, _FFMPEG_LOG)
            )
            log.error(msg)
            if callable(self.on_error):
                self.on_error(msg)
            return

        size = os.path.getsize(path)
        if size == 0:
            msg = (
                "[ERROR] Recording finished but file is empty (0 bytes): {}. "
                "Check {}".format(path, _FFMPEG_LOG)
            )
            log.error(msg)
            try:
                os.remove(path)
                log.info("[Recorder] Deleted empty junk file: {}".format(path))
            except OSError as exc:
                log.warning("[Recorder] Could not delete junk file: {}".format(exc))
            if callable(self.on_error):
                self.on_error(msg)
            return

        log.info("[Recorder] Output verified: {} ({} bytes)".format(path, size))

    # ── Temp cleanup ──────────────────────────────────────────────────────

    def _cleanup_tmp(self, tmp_dir):
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as exc:
            log.debug("[Recorder] Temp cleanup error: {}".format(exc))
