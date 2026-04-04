# -*- coding: utf-8 -*-
"""
Video recorder engine — daemon thread, multiple recording strategies.

Strategy waterfall (first that works wins):
  1. FFmpeg direct /dev/fb0 rawvideo pipe  — fastest, zero PIL dep
  2. grab-per-frame JPEG pipe into ffmpeg  — STiH/Sigma video+OSD
  3. Frame dump (PNG) + ffmpeg mux         — universal fallback
  4. ZIP of PNG frames                     — last resort, no ffmpeg

Video recording fixes (v1.0.3):
  - _try_ffmpeg_direct: probe ffmpeg with -version BEFORE spawning the
    capture process — rejects broken PATH entries early
  - _try_ffmpeg_direct: non-zero ffmpeg exit code now calls on_error
    with the last line of stderr so the UI shows why video failed
  - _try_ffmpeg_direct: explicit -t 3600 safety cap (was already there
    but now also logged to /tmp/ffmpeg_e2rec.log at WARNING level)
  - _mux_frames: log frame count before mux so strategy-3 failures
    are diagnosable ("0 frames captured" vs "mux failed")
  - All strategies: on_error now called on subprocess.OSError too
    (e.g. ffmpeg binary found but not executable on this arch)

Video recording fixes (v1.0.2):
  - _open_fb() called inside run() so per-thread HiSilicon fb1 fallback
    is applied before the capture loop starts
  - Interruptible sleep via stop_event.wait()
  - makedirs_safe() used on ALL code paths
  - on_error receives 'ExceptionType: msg' string
  - FFmpeg stderr redirected to /tmp/ffmpeg_e2rec.log

Video recording fixes (v1.0.1):
  - Mux runs strictly AFTER stop_event fires
  - communicate_safe() for Py2/Py3 timeout compatibility
  - Ring-buffer re-index before mux
"""
from __future__ import absolute_import, print_function, division

import threading
import time
import os
import shutil
import subprocess

from .framebuffer import FramebufferCapture
from .converter   import PixelConverter
from .compat      import communicate_safe, makedirs_safe

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

RING_SIZE   = 30
FFMPEG_LOG  = "/tmp/ffmpeg_e2rec.log"


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
        self._fb_info    = {}
        self._tmp_dir    = None

    def stop(self):
        self._stop_event.set()

    def elapsed(self):
        return time.time() - self._start_time

    def _emit_error(self, msg):
        """Send error to UI callback and write to log."""
        try:
            with open(FFMPEG_LOG, "a") as f:
                f.write("[recorder error] {}\n".format(msg))
        except Exception:
            pass
        if callable(self.on_error):
            self.on_error(msg)

    # ── Framebuffer open with HiSilicon blank-frame detection ─────────────

    def _open_fb(self):
        primary    = self.fb_device or "/dev/fb0"
        candidates = [primary]
        if primary == "/dev/fb0" and os.path.exists("/dev/fb1"):
            candidates.append("/dev/fb1")
        elif primary == "/dev/fb1" and os.path.exists("/dev/fb0"):
            candidates.append("/dev/fb0")

        for dev in candidates:
            if not os.path.exists(dev):
                continue
            try:
                fb = FramebufferCapture(device=dev)
                fb.open()
                os.lseek(fb._fd, 0, os.SEEK_SET)
                sample  = os.read(fb._fd, 256)
                nonzero = sum(1 for b in bytearray(sample) if b != 0)
                if nonzero < 8 and dev == "/dev/fb0":
                    fb.close()
                    continue
                return fb
            except OSError:
                continue

        fb = FramebufferCapture(device=candidates[0])
        fb.open()
        return fb

    # ── Main thread loop ─────────────────────────────────────────────────

    def run(self):
        fb = None
        try:
            fb = self._open_fb()
            info = fb.get_info()
            self._fb_info = info
            w, h = info["xres"], info["yres"]
            fb.close()
            fb = None

            if self._try_ffmpeg_direct(info):
                return
            if self._try_grab_pipe(info):
                return
            self._run_frame_dump(info, w, h)

        except Exception as e:
            self._emit_error("{}: {}".format(type(e).__name__, e))
        finally:
            if fb is not None:
                try:
                    fb.close()
                except Exception:
                    pass

    # ── Strategy 1: FFmpeg rawvideo direct from /dev/fb ──────────────────

    def _try_ffmpeg_direct(self, info):
        from ..backends.GrabberFFmpeg import get_ffmpeg
        ffmpeg = get_ffmpeg()
        if not ffmpeg:
            self._log("Strategy 1 skipped: ffmpeg not found in PATH")
            return False

        # FIX v1.0.3: probe the binary before trusting it
        try:
            probe = subprocess.Popen(
                [ffmpeg, "-version"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            communicate_safe(probe, timeout=5)
            if probe.returncode not in (0, 1):
                self._log("Strategy 1 skipped: ffmpeg -version returned {}".format(
                    probe.returncode))
                return False
        except Exception as probe_err:
            self._log("Strategy 1 skipped: ffmpeg probe failed: {}".format(probe_err))
            return False

        w       = info["xres"]
        h       = info["yres"]
        bpp     = info["bpp"]
        yoffset = info.get("yoffset", 0)
        device  = self.fb_device or "/dev/fb0"

        ro = info.get("red_offset", 16)
        if bpp == 32:
            pix_fmt = "bgra" if ro == 16 else "rgba"
        elif bpp == 16:
            pix_fmt = "rgb565le"
        else:
            self._log("Strategy 1 skipped: unsupported bpp={}".format(bpp))
            return False

        vf_filter = "crop={}:{}:0:{}".format(w, h, yoffset) if yoffset > 0 \
                    else "crop={}:{}:0:0".format(w, h)
        fb_height = info.get("yres", h)

        cmd = [
            ffmpeg,
            "-loglevel", "warning",
            "-f", "rawvideo",
            "-pixel_format", pix_fmt,
            "-video_size", "{}x{}".format(w, fb_height),
            "-framerate", str(self.fps),
            "-i", device,
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-t", "3600",
            "-y",
            self.output_path,
        ]

        self._log("Strategy 1 start: {}".format(" ".join(cmd)))

        try:
            log_fd = open(FFMPEG_LOG, "w")
        except Exception:
            log_fd = subprocess.PIPE

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
            )

            while not self._stop_event.is_set():
                self._stop_event.wait(0.5)
                if proc.poll() is not None:
                    break

            # Graceful shutdown
            try:
                proc.stdin.write(b"q\n")
                proc.stdin.flush()
            except Exception:
                pass
            proc.terminate()

            try:
                communicate_safe(proc, timeout=30)
            except Exception:
                pass

            # FIX v1.0.3: surface non-zero exit code to the UI
            rc = proc.returncode if proc.returncode is not None else -1
            if rc not in (0, -15, 255):  # 0=ok, -15=SIGTERM, 255=ffmpeg ctrl+c
                err_snippet = self._tail_log(FFMPEG_LOG)
                self._emit_error(
                    "ffmpeg exited {} — {}".format(rc, err_snippet))

            if (os.path.isfile(self.output_path)
                    and os.path.getsize(self.output_path) > 1024):
                self._log("Strategy 1 success: {}".format(self.output_path))
                return True

            try:
                os.remove(self.output_path)
            except Exception:
                pass
            self._log("Strategy 1 produced empty file — falling through")
            return False

        except Exception as e:
            self._emit_error("Strategy 1 exception: {}: {}".format(
                type(e).__name__, e))
            return False
        finally:
            try:
                log_fd.close()
            except Exception:
                pass

    # ── Strategy 2: grab-per-frame JPEG pipe ─────────────────────────────

    def _try_grab_pipe(self, info):
        from ..backends.GrabberFFmpeg import get_ffmpeg
        from .framebuffer import GRAB_BINS
        ffmpeg = get_ffmpeg()
        if not ffmpeg:
            return False

        grab_bin = None
        for b in GRAB_BINS:
            try:
                ret = subprocess.call(
                    [b, "--help"] if os.sep not in b else [b],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if ret in (0, 1):
                    grab_bin = b
                    break
            except Exception:
                continue
        if not grab_bin:
            return False

        tmp_dir = "/tmp/e2rec_grab_{}".format(os.getpid())
        makedirs_safe(tmp_dir)

        delay       = 1.0 / max(1, self.fps)
        idx         = 0
        frame_paths = []

        while not self._stop_event.is_set():
            t0         = time.time()
            frame_path = "{}/{:06d}.jpg".format(tmp_dir, idx)
            try:
                ret = subprocess.call(
                    [grab_bin, "-j", "85", frame_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if ret == 0 and os.path.isfile(frame_path):
                    frame_paths.append(frame_path)
            except Exception:
                pass
            idx += 1
            self._stop_event.wait(max(0.0, delay - (time.time() - t0)))

        if not frame_paths:
            return False

        list_path = "{}/concat.txt".format(tmp_dir)
        with open(list_path, "w") as f:
            for fp in frame_paths:
                f.write("file '{}'\n".format(fp))
                f.write("duration {}\n".format(round(1.0 / self.fps, 4)))

        cmd = [
            ffmpeg, "-loglevel", "warning",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "28", "-pix_fmt", "yuv420p",
            "-y", self.output_path,
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        try:
            communicate_safe(proc, timeout=120)
        except Exception:
            pass

        ok = (os.path.isfile(self.output_path)
              and os.path.getsize(self.output_path) > 1024)
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        return ok

    # ── Strategy 3: frame-dump + mux ─────────────────────────────────────

    def _run_frame_dump(self, info, w, h):
        tmp_dir = "/tmp/e2rec_{}".format(os.getpid())
        self._tmp_dir = tmp_dir
        makedirs_safe(tmp_dir)

        fb = FramebufferCapture(self.fb_device)
        fb.open()
        delay = 1.0 / max(1, self.fps)
        idx   = 0

        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                raw = fb.capture_raw()
                rgb = PixelConverter.to_rgb24(raw, info)
                frame_path = "{}/{:06d}.png".format(tmp_dir, idx)
                self._write_frame(rgb, w, h, frame_path)

                self._frame_list.append(frame_path)
                if self.low_ram and len(self._frame_list) > RING_SIZE:
                    old = self._frame_list.pop(0)
                    try:
                        os.remove(old)
                    except OSError:
                        pass

                idx += 1
            except Exception:
                pass

            self._stop_event.wait(max(0.0, delay - (time.time() - t0)))

        fb.close()
        self._mux_frames(tmp_dir, w, h)

    def _write_frame(self, rgb24, w, h, path):
        if HAS_PIL:
            try:
                Image.frombytes("RGB", (w, h), rgb24).save(
                    path, "PNG", optimize=False, compress_level=1)
                return
            except Exception:
                pass
        from ..backends.GrabberPPM import PPMGrabber
        PPMGrabber.save_png(rgb24, w, h, path)

    def _mux_frames(self, tmp_dir, w, h):
        from ..backends.GrabberFFmpeg import get_ffmpeg
        ffmpeg = get_ffmpeg()

        sequential = [f for f in self._frame_list if os.path.isfile(f)]

        # FIX v1.0.3: log frame count so "0 frames" is diagnosable
        self._log("Strategy 3 mux: {} frames captured".format(len(sequential)))

        if not sequential:
            self._emit_error("No frames captured — check /dev/fb0 permissions")
            return

        if ffmpeg:
            for new_idx, old_path in enumerate(sequential):
                new_path = "{}/mux_{:06d}.png".format(tmp_dir, new_idx)
                if old_path != new_path:
                    try:
                        os.rename(old_path, new_path)
                    except Exception:
                        pass

            try:
                log_fd = open(FFMPEG_LOG, "w")
            except Exception:
                log_fd = subprocess.PIPE

            cmd = [
                ffmpeg,
                "-loglevel", "warning",
                "-framerate", str(self.fps),
                "-i", "{}/mux_%06d.png".format(tmp_dir),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", self.output_path,
            ]
            proc = subprocess.Popen(cmd, stdout=log_fd,
                                    stderr=subprocess.STDOUT)
            try:
                communicate_safe(proc, timeout=300)
            except Exception as e:
                self._emit_error("FFmpeg mux error: {}".format(e))
            finally:
                try:
                    log_fd.close()
                except Exception:
                    pass

            # FIX v1.0.3: surface mux failure to UI
            rc = proc.returncode if proc.returncode is not None else -1
            if rc not in (0, -15, 255):
                err_snippet = self._tail_log(FFMPEG_LOG)
                self._emit_error("Mux exited {} — {}".format(rc, err_snippet))

        if (not ffmpeg
                or not os.path.isfile(self.output_path)
                or os.path.getsize(self.output_path) < 1024):
            import zipfile
            zip_path = self.output_path.rsplit(".", 1)[0] + "_frames.zip"
            self._log("Strategy 4 fallback: writing {}".format(zip_path))
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in sequential:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))

        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────

    def _log(self, msg):
        """Append a timestamped line to the ffmpeg log for diagnostics."""
        try:
            with open(FFMPEG_LOG, "a") as f:
                f.write("[{:.1f}] {}\n".format(time.time(), msg))
        except Exception:
            pass

    @staticmethod
    def _tail_log(path, lines=3):
        """Return the last N lines of a log file as a single string."""
        try:
            with open(path, "r") as f:
                tail = f.readlines()[-lines:]
            return " | ".join(l.strip() for l in tail if l.strip())
        except Exception:
            return "(no log)"
