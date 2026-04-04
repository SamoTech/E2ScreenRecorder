# -*- coding: utf-8 -*-
"""
Video recorder engine.

Strategy selection (in priority order)
---------------------------------------
1. FFmpeg fbdev live capture   best quality, lowest RAM, preferred
2. Frame-by-frame PNG + mux    fallback when ffmpeg not available
3. Frame-by-frame PNG + ZIP    last resort (no muxer at all)

Pre-flight checks (NEW)
-----------------------
* detect_framebuffer() validates device exists AND is readable BEFORE
  passing it to FFmpeg.  Raises FramebufferNotFoundError with a clear
  user-facing message if no device is accessible.
* Blank-frame detection: reads 256 bytes; skips all-zero devices
  (HiSilicon /dev/fb0 is always blank, real OSD is on /dev/fb1).

Post-recording verification (NEW)
----------------------------------
* _verify_output() is called after stop().
* 0-byte files are deleted automatically.
* FFmpeg stderr is in /tmp/ffmpeg_e2rec.log; last 20 lines are echoed
  to the plugin log on failure.

Thread communication
--------------------
  stop()      signal to finish + immediately stops ffmpeg subprocess
  is_alive()  threading.Thread builtin
  elapsed()   seconds since start (used by WebIF REC timer)
"""
from __future__ import absolute_import, print_function, division

import os
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

# Ring-buffer frame cap for low-RAM mode (<=256 MB devices)
_RING_BUFFER_MAX = 30


# ── Custom exception ─────────────────────────────────────────────────────────

class FramebufferNotFoundError(RuntimeError):
    """
    Raised when no accessible framebuffer device can be found.
    Caught by ScreenRecorderPlugin and shown as an OSD notification.
    """
    pass


# ── Pre-flight helper ─────────────────────────────────────────────────────────

def detect_framebuffer(preferred=None):
    """
    Locate a valid, non-blank framebuffer device.

    Resolution order
    ----------------
    1. preferred  (caller-supplied, e.g. from Settings)
    2. /dev/fb0   if it exists, is readable, and is not all-zero
    3. /dev/fb1   same checks (HiSilicon: real OSD is usually here)
    4. /dev/fb0   last resort even if blank (better than nothing)

    Parameters
    ----------
    preferred : str or None
        Device path explicitly chosen by the user in Settings.

    Returns
    -------
    str : path to selected device

    Raises
    ------
    FramebufferNotFoundError
        If no candidate device exists or none is readable.
    """
    candidates = []
    if preferred and preferred not in ("/dev/fb0", "/dev/fb1"):
        candidates.append(preferred)
    candidates += ["/dev/fb0", "/dev/fb1"]

    accessible = []
    for dev in candidates:
        if not os.path.exists(dev):
            log.debug("FB candidate missing: {}".format(dev))
            continue
        if not os.access(dev, os.R_OK):
            log.warning("FB candidate not readable (permission denied): {}".format(dev))
            continue
        accessible.append(dev)

    if not accessible:
        raise FramebufferNotFoundError(
            "No framebuffer device found.\n"
            "Checked: /dev/fb0, /dev/fb1\n"
            "Please check hardware or run as root."
        )

    # Prefer first device with non-zero content (i.e. the live OSD)
    for dev in accessible:
        try:
            fd     = os.open(dev, os.O_RDONLY)
            sample = os.read(fd, 256)
            os.close(fd)
            if any(b != 0 for b in bytearray(sample)):
                log.info("detect_framebuffer: selected {} (non-blank)".format(dev))
                return dev
            log.debug("detect_framebuffer: {} is blank (all zeros)".format(dev))
        except Exception as e:
            log.warning("detect_framebuffer: read test failed on {}: {}".format(dev, e))

    # All accessible devices are blank — return first one with a warning
    dev = accessible[0]
    log.warning(
        "detect_framebuffer: all devices appear blank; "
        "using {} as fallback".format(dev)
    )
    return dev


# ── Recorder thread ───────────────────────────────────────────────────────────

class FrameRecorder(threading.Thread):
    """
    Background recording thread.

    Parameters
    ----------
    output_path : str
    fps         : int    target capture rate
    fmt         : str    container format hint (mp4/mkv/avi/ts)
    fb_device   : str|None  explicit device; None = auto-detect
    on_error    : callable(str) | None   called from worker thread on failure
    low_ram     : bool   ring-buffer frame cap for <=256 MB devices
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

        self._stop_event  = threading.Event()
        self._start_time  = time.time()
        self._ffmpeg_rec  = None
        self._device_used = None   # set after preflight, readable by UI

    # ── Public API ────────────────────────────────────────────────────────

    def stop(self):
        """Signal the thread to finish and immediately stop ffmpeg."""
        self._stop_event.set()
        if self._ffmpeg_rec is not None:
            try:
                self._ffmpeg_rec.stop()
            except Exception:
                pass

    def elapsed(self):
        """Seconds since recording started (float)."""
        return time.time() - self._start_time

    @property
    def device_used(self):
        """Framebuffer device that was actually used (set after preflight)."""
        return self._device_used

    # ── Thread entry point ────────────────────────────────────────────────

    def run(self):
        self._start_time = time.time()
        try:
            # ── Pre-flight: validate FB device BEFORE starting ffmpeg ────
            try:
                device = detect_framebuffer(preferred=self.fb_device)
            except FramebufferNotFoundError as e:
                log.error("Pre-flight failed: {}".format(e))
                if callable(self.on_error):
                    self.on_error(str(e))
                return

            self._device_used = device
            log.info("FrameRecorder.run: device={} output={}".format(
                device, self.output_path))

            # ── Strategy 1: FFmpeg fbdev live capture ─────────────────────
            if self._try_ffmpeg_live(device):
                return

            # ── Strategy 2 / 3: frame-by-frame PNG fallback ───────────────
            self._run_frame_fallback(device)

        except Exception as e:
            log.error("FrameRecorder.run unhandled exception: {}".format(e))
            if callable(self.on_error):
                self.on_error("Recorder crashed: {}".format(e))

    # ── Strategy 1 ────────────────────────────────────────────────────────

    def _try_ffmpeg_live(self, device):
        """
        Attempt live capture via `ffmpeg -f fbdev`.
        Returns True on success/stop; False if ffmpeg unavailable.
        """
        try:
            from ..backends.GrabberFFmpeg import FFmpegRecorder, get_ffmpeg
        except ImportError:
            log.warning("GrabberFFmpeg import failed — frame fallback")
            return False

        if not get_ffmpeg():
            log.info("ffmpeg not found — frame fallback")
            return False

        log.info("Strategy 1: ffmpeg fbdev live -> {}".format(self.output_path))

        try:
            rec = FFmpegRecorder(
                output_path=self.output_path,
                fps=self.fps,
                fb_device=device,
            )
            rec.start()
        except Exception as e:
            # Device permission or other startup error
            log.error("Strategy 1 start failed: {}".format(e))
            if callable(self.on_error):
                self.on_error(str(e))
            return True   # claim handled so we don't retry with fallback

        self._ffmpeg_rec = rec

        # Wait until stop() is called or ffmpeg dies on its own
        while not self._stop_event.is_set():
            if not rec.is_running():
                log.warning("ffmpeg exited before stop() was called")
                break
            time.sleep(0.5)

        rec.stop()
        self._ffmpeg_rec = None

        # ── Post-recording verification ──────────────────────────────────
        ok, result = rec.verify_output()
        if ok:
            log.info("Strategy 1 success: {}".format(result))
        else:
            log.error("Strategy 1 output check failed: {}".format(result))
            if callable(self.on_error):
                self.on_error(result)

        return True

    # ── Strategy 2 / 3 ────────────────────────────────────────────────────

    def _run_frame_fallback(self, device):
        """Capture individual PNG frames, then mux (S2) or ZIP (S3)."""
        fb = FramebufferCapture(device=device)
        try:
            fb.open()
        except Exception as e:
            raise RuntimeError("Cannot open {}: {}".format(device, e))

        info    = fb.get_info()
        w, h    = info["xres"], info["yres"]
        delay   = 1.0 / max(1, self.fps)
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

                frame_paths.append(frame_path)
                if self.low_ram and len(frame_paths) > _RING_BUFFER_MAX:
                    old = frame_paths.pop(0)
                    try:
                        os.remove(old)
                    except Exception:
                        pass

                idx += 1
                time.sleep(max(0.0, delay - (time.time() - t0)))
        finally:
            fb.close()

        log.info("Frame capture done: {} frames".format(len(frame_paths)))
        self._mux_or_zip(frame_paths, tmp_dir)

        # Verify output after mux/zip as well
        if os.path.exists(self.output_path):
            if os.path.getsize(self.output_path) == 0:
                log.error("Strategy 2 produced empty file, deleting.")
                try:
                    os.remove(self.output_path)
                except Exception:
                    pass
                if callable(self.on_error):
                    self.on_error("Recording failed: output file is empty (0 bytes)")

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

        # Strategy 3: ZIP archive
        zip_path = self.output_path.rsplit(".", 1)[0] + "_frames.zip"
        log.info("Strategy 3: ZIP -> {}".format(zip_path))
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in frame_paths:
                if os.path.isfile(fp):
                    zf.write(fp, os.path.basename(fp))
        log.info("Strategy 3 done: {}".format(zip_path))
