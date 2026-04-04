# -*- coding: utf-8 -*-
"""
FFmpeg subprocess backend for video recording.
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
]


def get_ffmpeg():
    """Return path to ffmpeg binary or None."""
    for b in FFMPEG_PATHS:
        try:
            ret = subprocess.call(
                [b, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if ret == 0:
                return b
        except Exception:
            continue
    return None


class FFmpegRecorder(object):

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
            raise RuntimeError("FFmpeg not found")
        info = self.fb_info
        w, h = info["xres"], info["yres"]
        bpp  = info["bpp"]
        pix_fmt = "bgra" if bpp == 32 else "rgb565le"
        cmd = [
            self._binary,
            "-f", "rawvideo",
            "-pixel_format", pix_fmt,
            "-video_size", "{}x{}".format(w, h),
            "-framerate", str(self.fps),
            "-i", "/dev/fb0",
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-y", self.output_path
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def stop(self):
        if self._proc:
            try:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
            except Exception:
                pass
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
