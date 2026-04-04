# -*- coding: utf-8 -*-
"""
FFmpeg CLI subprocess backend - video recording from /dev/fb0.
Auto-discovers ffmpeg binary across all known STB install paths.
"""
from __future__ import absolute_import, print_function, division

import os
import subprocess

FFMPEG_SEARCH_PATHS = [
    "ffmpeg",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/bin/ffmpeg",
    "/usr/sbin/ffmpeg",
    "/bin/ffmpeg",
]


def _find_ffmpeg():
    for b in FFMPEG_SEARCH_PATHS:
        if os.path.sep in b:
            if os.path.isfile(b) and os.access(b, os.X_OK):
                return b
        else:
            try:
                subprocess.check_call(
                    [b, "-version"],
                    stdout=open(os.devnull, "w"),
                    stderr=open(os.devnull, "w"),
                )
                return b
            except Exception:
                continue
    return None


_FFMPEG_BINARY  = None
_FFMPEG_CHECKED = False


def get_ffmpeg():
    global _FFMPEG_BINARY, _FFMPEG_CHECKED
    if not _FFMPEG_CHECKED:
        _FFMPEG_BINARY  = _find_ffmpeg()
        _FFMPEG_CHECKED = True
    return _FFMPEG_BINARY


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
            raise RuntimeError("FFmpeg not found on this device")
        info  = self.fb_info
        w, h  = info["xres"], info["yres"]
        bpp   = info.get("bpp", 32)
        pix_fmt = "bgra" if bpp == 32 else "rgb565le"
        cmd = [
            self._binary, "-y",
            "-f",            "rawvideo",
            "-pixel_format", pix_fmt,
            "-video_size",   "{}x{}".format(w, h),
            "-framerate",    str(self.fps),
            "-i",            "/dev/fb0",
            "-vf",           "scale={}:{}".format(w, h),
            "-c:v",          self.codec,
            "-crf",          str(self.crf),
            "-preset",       "ultrafast",
            "-pix_fmt",      "yuv420p",
            "-movflags",     "+faststart",
            self.output_path,
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
        )

    def stop(self):
        if self._proc:
            try:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.wait()
            except Exception:
                pass
            self._proc = None

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None
