# -*- coding: utf-8 -*-
"""
Video recording via FFmpeg subprocess.

Key design decisions
--------------------
* Input format : -f fbdev   (live device demuxer, NOT -f rawvideo)
  -f rawvideo treats /dev/fb0 as a finite file -> reads 1 frame -> exits.
  -f fbdev streams indefinitely until the process receives SIGTERM.

* Stop method  : proc.terminate() (SIGTERM), then wait(10s), then kill().
  Writing 'q' to stdin is unreliable on embedded ffmpeg builds.

* Logging      : FFmpeg stderr is redirected to /tmp/ffmpeg_e2rec.log so
  every failure is fully debuggable without a serial console.
  The log is rotated at 1 MB to avoid filling /tmp on 128 MB devices.

* Output check : After stop(), the caller MUST call verify_output() to
  detect 0-byte files produced by early FFmpeg exit.
"""
from __future__ import absolute_import, print_function, division

import os
import subprocess
import threading

from ..utils.logger import log

# ── Constants ────────────────────────────────────────────────────────────────

_FFMPEG_CANDIDATES = [
    "ffmpeg",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/bin/ffmpeg",
    "/opt/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
]

FFMPEG_LOG_PATH  = "/tmp/ffmpeg_e2rec.log"
FFMPEG_LOG_MAXB  = 1 * 1024 * 1024   # 1 MB — rotate before this threshold


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_ffmpeg():
    """Return path to a working ffmpeg binary, or None."""
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


def _rotate_log():
    """Rotate ffmpeg log if it exceeds FFMPEG_LOG_MAXB."""
    try:
        if os.path.isfile(FFMPEG_LOG_PATH):
            if os.path.getsize(FFMPEG_LOG_PATH) >= FFMPEG_LOG_MAXB:
                bak = FFMPEG_LOG_PATH + ".bak"
                if os.path.isfile(bak):
                    os.remove(bak)
                os.rename(FFMPEG_LOG_PATH, bak)
    except Exception:
        pass


def _tail_log(n=20):
    """Return last n lines of ffmpeg log as a single string."""
    try:
        with open(FFMPEG_LOG_PATH, "r") as f:
            lines = f.read().splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return "(log unavailable)"


# ── Main class ───────────────────────────────────────────────────────────────

class FFmpegRecorder(object):
    """
    Live framebuffer recorder.

    Usage::

        rec = FFmpegRecorder(output_path="/media/hdd/screenshots/rec_001.mkv",
                             fps=5, fb_device="/dev/fb0")
        rec.start()     # non-blocking: spawns ffmpeg in a daemon thread
        ...             # recording runs in background
        rec.stop()      # SIGTERM -> wait -> SIGKILL fallback
        ok, msg = rec.verify_output()   # True/False + human message
    """

    def __init__(self, output_path, fps=5, codec="libx264", crf=28,
                 fb_device="/dev/fb0"):
        self.output_path = output_path
        self.fps         = int(fps)
        self.codec       = codec
        self.crf         = int(crf)
        self.fb_device   = fb_device
        self._proc       = None
        self._thread     = None
        self._binary     = get_ffmpeg()
        self._lock       = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────────

    def is_available(self):
        """True if a working ffmpeg binary was found."""
        return self._binary is not None

    def start(self):
        """
        Spawn ffmpeg in a daemon thread.  Raises RuntimeError if ffmpeg
        is not found or the device cannot be opened.
        """
        if not self._binary:
            raise RuntimeError(
                "FFmpeg not found on this device. "
                "Install it with: opkg install ffmpeg")

        if not os.path.exists(self.fb_device):
            raise RuntimeError(
                "Framebuffer device not found: {}".format(self.fb_device))

        if not os.access(self.fb_device, os.R_OK):
            raise RuntimeError(
                "Framebuffer device not readable (permission denied): {}"
                .format(self.fb_device))

        _rotate_log()

        self._thread = threading.Thread(target=self._run_ffmpeg)
        self._thread.daemon = True
        self._thread.start()
        log.info("FFmpegRecorder.start: device={} output={}".format(
            self.fb_device, self.output_path))

    def stop(self):
        """Stop recording.  Sends SIGTERM, waits 10 s, then SIGKILL."""
        with self._lock:
            proc = self._proc

        if proc is None:
            return

        try:
            if proc.poll() is None:
                log.info("FFmpegRecorder.stop: sending SIGTERM")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    log.warning("FFmpegRecorder.stop: timeout, sending SIGKILL")
                    proc.kill()
                    proc.wait()
        except Exception as e:
            log.warning("FFmpegRecorder.stop error: {}".format(e))
        finally:
            with self._lock:
                self._proc = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6)

    def is_running(self):
        """True while the ffmpeg subprocess is alive."""
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def verify_output(self):
        """
        Check the output file after stop().

        Returns
        -------
        (True,  path)           recording OK, file has data
        (False, error_message)  recording failed; 0-byte file deleted
        """
        path = self.output_path

        if not os.path.exists(path):
            msg = ("Recording failed: output file was never created.\n"
                   "Check FFmpeg log: {}".format(FFMPEG_LOG_PATH))
            log.error(msg)
            return False, msg

        size = os.path.getsize(path)
        if size == 0:
            log.error("Recording finished but file is 0 bytes: {}".format(path))
            log.error("Last FFmpeg output:\n{}".format(_tail_log()))
            try:
                os.remove(path)
                log.info("Deleted empty output file: {}".format(path))
            except Exception as rm_err:
                log.warning("Could not delete empty file: {}".format(rm_err))
            msg = ("Recording failed: output file is empty (0 bytes).\n"
                   "FFmpeg log saved to: {}".format(FFMPEG_LOG_PATH))
            return False, msg

        log.info("Output verified OK: {} ({} bytes)".format(path, size))
        return True, path

    # ── Private ──────────────────────────────────────────────────────────

    def _run_ffmpeg(self):
        """
        Worker thread: build and run the ffmpeg command.
        stderr is redirected to FFMPEG_LOG_PATH for full debug output.
        """
        cmd = [
            self._binary,
            "-f", "fbdev",
            "-framerate", str(self.fps),
            "-i", self.fb_device,
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-y",
            self.output_path,
        ]

        log.info("FFmpeg cmd: {}".format(" ".join(cmd)))

        try:
            with open(FFMPEG_LOG_PATH, "w") as log_fd:
                proc = subprocess.Popen(
                    cmd,
                    stdin  =subprocess.PIPE,
                    stdout =subprocess.PIPE,
                    stderr =log_fd,
                    close_fds=True,
                )
                with self._lock:
                    self._proc = proc
                proc.wait()    # blocks until SIGTERM flushes and exits

            rc = proc.returncode
            if rc not in (0, -15, 255):   # 0=ok  -15=SIGTERM  255=some STB builds
                log.warning("FFmpeg exited with code {}. "
                            "See: {}".format(rc, FFMPEG_LOG_PATH))
                log.warning("Last lines:\n{}".format(_tail_log(10)))

        except Exception as e:
            log.error("FFmpeg fatal error: {}".format(e))
            try:
                with open(FFMPEG_LOG_PATH, "a") as f:
                    f.write("FATAL: {}\n".format(e))
            except Exception:
                pass
        finally:
            with self._lock:
                self._proc = None
