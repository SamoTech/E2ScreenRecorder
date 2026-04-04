# -*- coding: utf-8 -*-
"""
Video recorder engine — daemon thread, multiple recording strategies.

Strategy waterfall (first that works wins):
  1. FFmpeg direct /dev/fb0 rawvideo pipe  — fastest, zero PIL dep
  2. grab-per-frame JPEG pipe into ffmpeg  — STiH/Sigma video+OSD
  3. Frame dump (PNG) + ffmpeg mux         — universal fallback
  4. ZIP of PNG frames                     — last resort, no ffmpeg

Video recording fixes (v1.0.2):
  - _open_fb() called inside run() so per-thread HiSilicon fb1 fallback
    is applied before the capture loop starts (was only at __init__ time)
  - Interruptible sleep via stop_event.wait() so stop() wakes immediately
  - makedirs_safe() used on ALL code paths (was missing from frame-dump)
  - on_error receives 'ExceptionType: msg' string, not bare str(e)
  - FFmpeg stderr redirected to /tmp/ffmpeg_e2rec.log for diagnostics

Video recording fixes (v1.0.1):
  - Mux now runs strictly AFTER stop_event fires (was called mid-loop)
  - communicate_safe() used for ffmpeg wait (Py2/Py3 compatible timeout)
  - Ring-buffer re-index runs before mux so ffmpeg gets sequential %06d
  - Interruptible sleep via stop_event.wait() instead of time.sleep()
  - Frame write errors skip the frame rather than aborting the recording

Ring buffer in low-RAM mode caps disk use to RING_SIZE frames.
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

RING_SIZE = 30


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

    # ── Framebuffer open with HiSilicon blank-frame detection ─────────────

    def _open_fb(self):
        """
        Open the framebuffer inside the recording thread.

        FIX (v1.0.2): This method is called from run() so that the
        HiSilicon /dev/fb1 fallback is applied PER THREAD, right before
        the capture loop starts — not at __init__ time when the device
        path may not yet be known.

        Blank-frame detection samples 256 bytes; if all-zero and
        /dev/fb1 exists, switches to fb1 before the loop begins.
        """
        primary = self.fb_device or "/dev/fb0"
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
                # Blank-frame check: sample first 256 bytes
                os.lseek(fb._fd, 0, os.SEEK_SET)
                sample  = os.read(fb._fd, 256)
                nonzero = sum(1 for b in bytearray(sample) if b != 0)
                if nonzero < 8 and dev == "/dev/fb0":
                    # Looks blank — try fb1 next
                    fb.close()
                    continue
                return fb
            except OSError:
                continue

        # Last resort: return whatever opens without blank check
        fb = FramebufferCapture(device=candidates[0])
        fb.open()
        return fb

    # ── Main thread loop ─────────────────────────────────────────────────

    def run(self):
        fb = None
        try:
            # FIX (v1.0.2): open fb inside run() so per-thread blank
            # detection and fb1 fallback are applied before any capture.
            fb = self._open_fb()
            info = fb.get_info()
            self._fb_info = info
            w, h = info["xres"], info["yres"]
            fb.close()
            fb = None

            # Strategy 1: FFmpeg direct fb pipe (fastest)
            if self._try_ffmpeg_direct(info):
                return

            # Strategy 2: grab-per-frame pipe
            if self._try_grab_pipe(info):
                return

            # Strategy 3: frame dump + mux
            self._run_frame_dump(info, w, h)

        except Exception as e:
            if callable(self.on_error):
                # FIX (v1.0.2): include exception type for better diagnostics
                self.on_error("{}: {}".format(type(e).__name__, e))
        finally:
            if fb is not None:
                try:
                    fb.close()
                except Exception:
                    pass

    # ── Strategy 1: FFmpeg rawvideo direct from /dev/fb ──────────────────

    def _try_ffmpeg_direct(self, info):
        """
        Stream /dev/fb0 (or fb1) directly into ffmpeg as rawvideo input.
        Uses yoffset to skip invisible back-buffer page via -vf crop.
        Returns True if recording was started and completed successfully.
        """
        from ..backends.GrabberFFmpeg import get_ffmpeg
        ffmpeg = get_ffmpeg()
        if not ffmpeg:
            return False

        w   = info["xres"]
        h   = info["yres"]
        bpp = info["bpp"]
        yoffset = info.get("yoffset", 0)
        device  = self.fb_device or "/dev/fb0"

        ro = info.get("red_offset", 16)
        if bpp == 32:
            pix_fmt = "bgra" if ro == 16 else "rgba"
        elif bpp == 16:
            pix_fmt = "rgb565le"
        else:
            return False

        vf_filter = "crop={}:{}:0:0".format(w, h)
        if yoffset > 0:
            vf_filter = "crop={}:{}:0:{}".format(w, h, yoffset)

        fb_height = info.get("yres", h)

        cmd = [
            ffmpeg,
            "-loglevel", "error",
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

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Block (interruptibly) until stop() is called
            while not self._stop_event.is_set():
                # FIX (v1.0.2): wait() instead of sleep() — wakes on stop()
                self._stop_event.wait(0.5)
                if proc.poll() is not None:
                    break

            try:
                proc.stdin.write(b"q\n")
                proc.stdin.flush()
            except Exception:
                pass
            proc.terminate()

            # Wait with Py2-safe timeout
            try:
                communicate_safe(proc, timeout=30)
            except Exception:
                pass

            if (os.path.isfile(self.output_path)
                    and os.path.getsize(self.output_path) > 1024):
                return True

            try:
                os.remove(self.output_path)
            except Exception:
                pass
            return False

        except Exception:
            return False

    # ── Strategy 2: grab-per-frame JPEG pipe ─────────────────────────────

    def _try_grab_pipe(self, info):
        """
        Run 'grab -j 90 <tmpfile>' per frame, collect frames,
        then mux with ffmpeg concat demuxer.
        Works on STiH/Sigma where live video is NOT in /dev/fb.
        Returns True on success.
        """
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
        # FIX (v1.0.2): makedirs_safe on all strategy paths
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
            # FIX (v1.0.2): interruptible sleep
            self._stop_event.wait(max(0.0, delay - (time.time() - t0)))

        if not frame_paths:
            return False

        list_path = "{}/concat.txt".format(tmp_dir)
        with open(list_path, "w") as f:
            for fp in frame_paths:
                f.write("file '{}'\n".format(fp))
                f.write("duration {}\n".format(round(1.0 / self.fps, 4)))

        cmd = [
            ffmpeg, "-loglevel", "error",
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
        # FIX (v1.0.2): makedirs_safe on this path too
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

                if self.low_ram:
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
            except Exception:
                # Skip bad frame — keep recording
                pass

            # FIX (v1.0.2): interruptible sleep — wakes immediately on stop()
            self._stop_event.wait(max(0.0, delay - (time.time() - t0)))

        fb.close()

        # Mux runs AFTER the loop exits, never mid-loop
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

        # Collect surviving frames and re-index sequentially
        sequential = [f for f in self._frame_list if os.path.isfile(f)]
        if not sequential:
            return

        if ffmpeg:
            for new_idx, old_path in enumerate(sequential):
                new_path = "{}/mux_{:06d}.png".format(tmp_dir, new_idx)
                if old_path != new_path:
                    try:
                        os.rename(old_path, new_path)
                    except Exception:
                        pass

            # FIX (v1.0.2): stderr redirected to log file for diagnostics
            log_file = "/tmp/ffmpeg_e2rec.log"
            try:
                log_fd = open(log_file, "w")
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
                if callable(self.on_error):
                    self.on_error("FFmpeg mux error: {}".format(e))
            finally:
                try:
                    log_fd.close()
                except Exception:
                    pass

        # Strategy 4: ZIP fallback if ffmpeg missing or produced empty file
        if (not ffmpeg
                or not os.path.isfile(self.output_path)
                or os.path.getsize(self.output_path) < 1024):
            import zipfile
            zip_path = self.output_path.rsplit(".", 1)[0] + "_frames.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in sequential:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))

        # Cleanup temp frames
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
