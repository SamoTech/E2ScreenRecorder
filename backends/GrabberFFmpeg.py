# -*- coding: utf-8 -*-
"""
Video recording via FFmpeg subprocess.
Uses -f fbdev (live framebuffer device demuxer) — NOT -f rawvideo.

Why fbdev and not rawvideo?
  -f rawvideo treats /dev/fb0 as a finite file: FFmpeg calculates
  duration = filesize / bitrate, reads exactly one frame, then exits.
  Result: empty or 1-second output file.
  -f fbdev is a proper live-device demuxer that streams until killed.

Stopping: send SIGTERM (proc.terminate()) — NOT stdin 'q'.
  Writing 'q' to stdin is unreliable; some STB ffmpeg builds ignore it.
"""
from __future__ import absolute_import, print_function, division

import os
import subprocess

from ..utils.logger import log

# Common FFmpeg install locations on Enigma2 STBs
_FFMPEG_CANDIDATES = [
    "ffmpeg",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/bin/ffmpeg",
    "/opt/usr/bin/ffmpeg",
]


def get_ffmpeg():
    """Return path to ffmpeg binary or None."""
    for candidate in _FFMPEG_CANDIDATES:
        try:
            if candidate != "ffmpeg" and not os.path.isfile(candidate):
                continue
            subprocess.check_call(
                [candidate, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return candidate
        except Exception:
            continue
    return None


class FFmpegRecorder(object):
    """
    Live framebuffer recorder using FFmpeg's fbdev input demuxer.

    Usage:
        rec = FFmpegRecorder(output_path, fps=5, fb_device="/dev/fb0")
        rec.start()          # spawns ffmpeg subprocess
        ...                  # recording runs in background
        rec.stop()           # sends SIGTERM, waits for clean exit
    """

    def __init__(self, output_path, fps=5, codec="libx264", crf=28,
                 fb_device="/dev/fb0"):
        self.output_path = output_path
        self.fps         = fps
        self.codec       = codec
        self.crf         = crf
        self.fb_device   = fb_device
        self._proc       = None
        self._binary     = get_ffmpeg()

    def is_available(self):
        return self._binary is not None

    def start(self):
        if not self._binary:
            raise RuntimeError(
                "FFmpeg not found. Install it: opkg install ffmpeg")

        # -f fbdev  → live framebuffer device demuxer (streams until killed)
        # -framerate → capture FPS (low = less CPU; 5 is fine for screen recording)
        # no -t / no -vframes → run indefinitely until proc.terminate()
        cmd = [
            self._binary,
            "-f", "fbdev",
            "-framerate", str(self.fps),
            "-i", self.fb_device,
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",   # broadest player compatibility
            "-y",
            self.output_path,
        ]

        log.info("FFmpegRecorder.start: {}".format(" ".join(cmd)))

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def stop(self):
        """Stop recording cleanly via SIGTERM and wait for ffmpeg to flush."""
        if self._proc is None:
            return
        try:
            self._proc.terminate()   # SIGTERM — ffmpeg flushes + writes MOOV
            try:
                self._proc.wait(timeout=10)
            except Exception:
                self._proc.kill()    # fallback SIGKILL if it hangs
        except Exception as e:
            log.warning("FFmpegRecorder.stop error: {}".format(e))
        finally:
            self._proc = None

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None
