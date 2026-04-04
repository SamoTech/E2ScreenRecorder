# -*- coding: utf-8 -*-
"""
FFmpeg subprocess backend for video recording and screenshot fallback.

Key fixes:
  - get_ffmpeg() caches result — avoids repeated subprocess calls on
    every frame during recording
  - FFmpegRecorder.stop() sends 'q\n' (with newline) for clean exit
  - Direct /dev/fb rawvideo recording now in FrameRecorder Strategy 1
  - Pixel format detection uses red_offset from ioctl, not hardcoded
"""
from __future__ import absolute_import, print_function, division

import subprocess
import os

FFMPEG_PATHS = [
    "ffmpeg",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/bin/ffmpeg",
    "/opt/local/bin/ffmpeg",
    "/usr/bin/avconv",     # libav fallback (Debian/Ubuntu older images)
    "/usr/local/bin/avconv",
]

# Module-level cache so we only probe once per process lifetime
_FFMPEG_CACHE = None


def get_ffmpeg():
    """Return path to ffmpeg/avconv binary, or None. Result is cached."""
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE is not None:
        return _FFMPEG_CACHE if _FFMPEG_CACHE != "" else None

    for b in FFMPEG_PATHS:
        try:
            ret = subprocess.call(
                [b, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if ret == 0:
                _FFMPEG_CACHE = b
                return b
        except Exception:
            continue

    _FFMPEG_CACHE = ""   # cache negative result
    return None


class FFmpegRecorder(object):
    """
    Direct framebuffer -> ffmpeg rawvideo pipe recorder.
    Used as a standalone object when FrameRecorder Strategy 1 is
    invoked from outside the thread (e.g. tests or external tools).
    """

    def __init__(self, fb_info, output_path, fps=5, codec="libx264", crf=28):
        self.fb_info     = fb_info
        self.output_path = output_path
        self.fps         = fps
        self.codec       = codec
        self.crf         = crf
        self._proc       = None
        self._binary     = get_ffmpeg()

    def is_available(self):
        return self._binary is not None

    def start(self):
        if not self._binary:
            raise RuntimeError("FFmpeg not found on this device")
        info    = self.fb_info
        w, h    = info["xres"], info["yres"]
        bpp     = info["bpp"]
        ro      = info.get("red_offset", 16)

        if bpp == 32:
            pix_fmt = "bgra" if ro == 16 else "rgba"
        elif bpp == 16:
            pix_fmt = "rgb565le"
        else:
            raise RuntimeError("Unsupported bpp for rawvideo: {}".format(bpp))

        cmd = [
            self._binary,
            "-loglevel", "error",
            "-f", "rawvideo",
            "-pixel_format", pix_fmt,
            "-video_size", "{}x{}".format(w, h),
            "-framerate", str(self.fps),
            "-i", "/dev/fb0",
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-t", "3600",
            "-y",
            self.output_path,
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def stop(self):
        if self._proc:
            try:
                # Send 'q\n' — ffmpeg requires newline to flush stdin command
                self._proc.stdin.write(b"q\n")
                self._proc.stdin.flush()
            except Exception:
                pass
            import time
            time.sleep(0.5)   # give ffmpeg time to flush and close GOP
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
