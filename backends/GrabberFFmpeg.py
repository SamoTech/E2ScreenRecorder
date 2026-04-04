# -*- coding: utf-8 -*-
"""
backends/GrabberFFmpeg.py
~~~~~~~~~~~~~~~~~~~~~~~~~
FFmpeg-based framebuffer capture backend.

Two public classes:
  FFmpegGrabber   — streams /dev/fbX directly via ``-f fbdev`` (fast, low-latency)
  FFmpegRecorder  — reads pre-captured PNG frames from a temp dir and muxes
                    them into the final output container

Module-level helper:
  get_ffmpeg()    — returns the path to the ffmpeg binary or None

All stderr is redirected to /tmp/ffmpeg_e2rec.log so operators can diagnose
problems without attaching a debugger to the STB.

Python 2.7 - 3.12+ compatible.  No f-strings. No walrus. No match.

Fixes applied (2026-04-04, real-device test on Cortex-A15 / FFmpeg 8.0):
  - Timestamp jumps: fbdev uses wall-clock PTS causing time to go backward
    then jump forward.  Fixed with -vsync cfr + setpts=N/(fps*TB).
  - Corrupt MP4 on kill: moov atom only written at end; first 25s show
    size=0KiB then a sudden 256KiB flush.  Fixed with movflags
    +faststart+frag_keyframe+empty_moov.
  - probesize warning on every start: suppressed with -probesize 32
    -fpsprobesize 0.
  - Cortex-A15 libx264 warmup latency: explicit x264-params disables
    cabac, bframes, aq, trellis, scenecut — not useful without NEON asm
    and only add overhead on this CPU class.
"""
from __future__ import absolute_import, print_function, division

import os
import subprocess
import threading
import time

from ..utils.logger import log

# ── Constants ───────────────────────────────────────────────────────────

_FFMPEG_BINS = [
    "ffmpeg",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/bin/ffmpeg",
    "/opt/local/bin/ffmpeg",
]
_FFMPEG_LOG   = "/tmp/ffmpeg_e2rec.log"
_STOP_TIMEOUT = 5           # seconds before SIGKILL after SIGTERM

# x264 parameter string tuned for Cortex-A15 with --disable-inline-asm.
# Disables analysis features that require NEON/asm to be worthwhile.
_X264_PARAMS_FAST = (
    "ref=1:bframes=0:aq-mode=0:me=dia:subme=0"
    ":trellis=0:scenecut=0:cabac=0"
)


# ── Binary discovery ───────────────────────────────────────────────────

def get_ffmpeg():
    """
    Return the path to a working ffmpeg binary, or None.
    Tries hard-coded STB paths first, then PATH lookup.
    Result is NOT cached — call once at startup and store it yourself.
    """
    for candidate in _FFMPEG_BINS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            log.debug("get_ffmpeg: found at {}".format(candidate))
            return candidate
    # Try via PATH
    try:
        subprocess.check_call(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return "ffmpeg"
    except Exception:
        pass
    log.warning("get_ffmpeg: no ffmpeg binary found on this device")
    return None


# ── FFmpegGrabber ──────────────────────────────────────────────────────

class FFmpegGrabber(object):
    """
    Streams a framebuffer device directly to a video file using
    ``-f fbdev``.  Runs FFmpeg in a daemon thread.

    Fixes vs. original:
      * -probesize 32 -fpsprobesize 0  suppress the 'not enough frames'
        warning that appeared on every recording start.
      * -vsync cfr + setpts filter     correct PTS so timestamps never
        go backward (fbdev wall-clock drift on Cortex-A15).
      * -movflags +faststart+frag_keyframe+empty_moov
                                       write a valid moov atom from frame 1
                                       so the file is playable even if the
                                       process is killed mid-recording.
      * -x264-params _X264_PARAMS_FAST disable analysis modes that only
                                       hurt performance without NEON asm.

    Logs all FFmpeg stderr output to ``/tmp/ffmpeg_e2rec.log``.
    """

    def __init__(self, device_path, output_path, framerate=25):
        self.device_path  = device_path
        self.output_path  = output_path
        self.framerate    = framerate
        self.process      = None
        self._thread      = None
        self._binary      = get_ffmpeg()

    def is_available(self):
        return self._binary is not None

    # ─ internal -------------------------------------------------------

    def _build_cmd(self):
        fps = str(self.framerate)
        cmd = [
            self._binary,
            # ── Input ──────────────────────────────────────────────
            # Suppress 'not enough frames to estimate rate' warning.
            "-probesize",    "32",
            "-fpsprobesize", "0",
            "-f",            "fbdev",
            "-framerate",    fps,
            "-i",            self.device_path,
            # ── Timestamp fix ──────────────────────────────────────
            # fbdev stamps frames with wall-clock time; on Cortex-A15
            # scheduling jitter causes PTS to jump backward then forward.
            # -vsync cfr forces constant frame rate in the muxer;
            # setpts rebuilds PTS from the frame counter so the output
            # timeline is always monotonically increasing.
            "-vsync",        "cfr",
            "-vf",           "setpts=N/({fps}*TB)".format(fps=fps),
            # ── Encoding ───────────────────────────────────────────
            "-c:v",          "libx264",
            "-preset",       "ultrafast",
            "-profile:v",    "baseline",
            "-level",        "3.1",
            "-pix_fmt",      "yuv420p",
            # Cortex-A15 tuning: disable analysis that needs NEON asm.
            "-x264-params",  _X264_PARAMS_FAST,
            # ── Output: safe fragmented MP4 ────────────────────────
            # faststart    : move moov to front for progressive play
            # frag_keyframe: flush a fragment at every keyframe so the
            #                file is valid even after an unclean stop
            # empty_moov   : write an empty moov before any frames so
            #                players can open the file immediately
            "-movflags",     "+faststart+frag_keyframe+empty_moov",
            "-y",
            self.output_path,
        ]
        return cmd

    def _run_ffmpeg(self):
        if not self._binary:
            msg = "FFmpegGrabber: no ffmpeg binary available"
            log.error(msg)
            self._append_log("FATAL: " + msg + "\n")
            return

        cmd = self._build_cmd()
        log.info("[FFmpegGrabber] {}".format(" ".join(cmd)))

        try:
            with open(_FFMPEG_LOG, "w") as log_fd:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=log_fd,
                    close_fds=True,
                )
                self.process.wait()
        except Exception as exc:
            self._append_log("FATAL ERROR starting FFmpeg: {}\n".format(exc))
            log.error("[FFmpegGrabber] Popen failed: {}".format(exc))
            raise

    def _append_log(self, text):
        try:
            with open(_FFMPEG_LOG, "a") as lf:
                lf.write(text)
        except Exception:
            pass

    # ─ public ---------------------------------------------------------

    def start(self):
        if not self._binary:
            raise RuntimeError(
                "FFmpegGrabber.start(): ffmpeg binary not found. "
                "Install ffmpeg or check PATH.")
        self._thread = threading.Thread(target=self._run_ffmpeg)
        self._thread.daemon = True
        self._thread.start()
        log.info("[FFmpegGrabber] Recording thread started ({} -> {})".format(
            self.device_path, self.output_path))

    def stop(self):
        """Send SIGTERM; escalate to SIGKILL after _STOP_TIMEOUT seconds."""
        if self.process and self.process.poll() is None:
            log.info("[FFmpegGrabber] Sending SIGTERM to FFmpeg (pid {})".format(
                self.process.pid))
            self.process.terminate()
            try:
                self.process.wait(timeout=_STOP_TIMEOUT)
            except Exception:
                # subprocess.TimeoutExpired on Py3; on Py2 wait() has no timeout
                # - handle both gracefully.
                try:
                    self.process.kill()
                    log.warning(
                        "[FFmpegGrabber] FFmpeg did not stop in {}s; "
                        "sent SIGKILL".format(_STOP_TIMEOUT))
                except Exception:
                    pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=_STOP_TIMEOUT)


# ── FFmpegRecorder ────────────────────────────────────────────────────

class FFmpegRecorder(object):
    """
    Muxes a sequence of PNG frames from a temp directory into an output
    video file.  Used by FrameRecorder._mux_frames() as a synchronous
    one-shot call (blocking until mux is done).

    Applies the same movflags fix as FFmpegGrabber so the muxed file is
    safe against unclean process termination.
    """

    def __init__(self, fb_info, output_path, fps=5, codec="libx264", crf=28):
        self.fb_info     = fb_info
        self.output_path = output_path
        self.fps         = fps
        self.codec       = codec
        self.crf         = crf
        self._binary     = get_ffmpeg()

    def is_available(self):
        return self._binary is not None

    def mux_frames(self, frame_pattern):
        """
        Mux PNG frames matching ``frame_pattern``
        (e.g. ``/tmp/e2rec_123/%06d.png``) into ``self.output_path``.

        Returns True on success, False on failure.
        All FFmpeg output is appended to ``_FFMPEG_LOG``.
        """
        if not self._binary:
            log.warning("[FFmpegRecorder] ffmpeg not available; skipping mux")
            return False

        fps_str = str(self.fps)
        cmd = [
            self._binary,
            "-framerate", fps_str,
            "-i",         frame_pattern,
            "-c:v",       self.codec,
            "-pix_fmt",   "yuv420p",
            "-crf",       str(self.crf),
            "-preset",    "ultrafast",
            "-profile:v", "baseline",
            "-level",     "3.1",
            "-x264-params", _X264_PARAMS_FAST,
            # Safe fragmented MP4 — same fix as FFmpegGrabber
            "-movflags",  "+faststart+frag_keyframe+empty_moov",
            "-y",
            self.output_path,
        ]
        log.info("[FFmpegRecorder] Mux: {}".format(" ".join(cmd)))

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
                    "[FFmpegRecorder] ffmpeg exited {} - see {}".format(
                        ret, _FFMPEG_LOG))
                return False
            return True
        except Exception as exc:
            log.error("[FFmpegRecorder] mux exception: {}".format(exc))
            return False

    # Legacy compatibility: kept so older callers still work
    def start(self):
        """Deprecated: use mux_frames() instead. No-op."""
        pass

    def stop(self):
        """Deprecated: use mux_frames() instead. No-op."""
        pass
