# -*- coding: utf-8 -*-
"""
Framebuffer capture via Linux ioctl.
Works on all known STB framebuffer implementations.

Black-screenshot root causes handled here:
  1. Double-buffering: read at yoffset*stride, not offset 0
  2. HiSilicon /dev/fb1: auto-detects blank fb0, falls back to fb1
  3. O_RDONLY rejected on old MIPS 2.6.x kernels: retry with O_RDWR
  4. STiH/Sigma video-plane: try native 'grab' binary first so the
     hardware-composited video+OSD frame is captured, not just the OSD.
No external dependencies required.
"""
from __future__ import absolute_import, print_function, division

import os
import struct
import fcntl
import array
import subprocess

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602

VSCREENINFO_FMT = (
    "II"       # xres, yres
    "II"       # xres_virtual, yres_virtual
    "II"       # xoffset, yoffset
    "I"        # bits_per_pixel
    "I"        # grayscale
    "HHH"      # red: offset, length, msb_right
    "HHH"      # green: offset, length, msb_right
    "HHH"      # blue: offset, length, msb_right
    "HHH"      # transp: offset, length, msb_right
    "I"        # nonstd
    "I"        # activate
    "II"       # height_mm, width_mm
    "I"        # accel_flags
    "IIIIIII"  # pixclock, margins, sync, vmode
    "I"        # rotate
    "I"        # colorspace
    "III"      # reserved
)

CHUNK_SIZE = 65536  # 64 KB — safe for Python 2 single-call read limits

# Enigma2 native grab binary search paths
GRAB_BINS = [
    "grab",
    "/usr/bin/grab",
    "/usr/local/bin/grab",
    "/bin/grab",
    "dreamgrab",
    "/usr/bin/dreamgrab",
]


class FramebufferCapture(object):

    def __init__(self, device=None):
        self.device  = device or "/dev/fb0"
        self._fd     = None
        self._fb_info = {}

    # ── Open / close ────────────────────────────────────────────────────────

    def open(self):
        """Open framebuffer device with automatic fallbacks."""
        self._open_device(self.device)

        # FIX #2 — HiSilicon: blank fb0 -> try fb1
        if self.device == "/dev/fb0" and self._is_blank():
            self._close_fd()
            if os.path.exists("/dev/fb1"):
                try:
                    self._open_device("/dev/fb1")
                    self.device = "/dev/fb1"
                except OSError:
                    # fb1 unreadable — reopen fb0
                    self._open_device("/dev/fb0")
                    self.device = "/dev/fb0"
            else:
                self._open_device("/dev/fb0")

    def _open_device(self, path):
        """Open a fb device; retry with O_RDWR if O_RDONLY fails (old kernels)."""
        try:
            # FIX #3 — O_RDONLY is fine on most kernels
            self._fd = os.open(path, os.O_RDONLY)
        except OSError:
            # FIX #3 — old MIPS 2.6.x kernels require O_RDWR even for reads
            self._fd = os.open(path, os.O_RDWR)
        self._read_vscreeninfo()

    def _close_fd(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None

    def close(self):
        self._close_fd()

    # ── ioctl ────────────────────────────────────────────────────────────────

    def _read_vscreeninfo(self):
        buf    = array.array('B', [0] * 160)
        fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf, True)
        raw    = buf.tobytes() if hasattr(buf, 'tobytes') else buf.tostring()
        fields = struct.unpack_from("<" + VSCREENINFO_FMT, raw)
        self._fb_info = {
            "xres":         fields[0],
            "yres":         fields[1],
            "xoffset":      fields[4],
            "yoffset":      fields[5],   # FIX #1 — double-buffer page offset
            "bpp":          fields[6],
            "red_offset":   fields[8],
            "red_len":      fields[9],
            "green_offset": fields[11],
            "green_len":    fields[12],
            "blue_offset":  fields[14],
            "blue_len":     fields[15],
            "alpha_offset": fields[17],
            "alpha_len":    fields[18],
        }

    # ── Blank detection ──────────────────────────────────────────────────────

    def _is_blank(self):
        """
        Sample 1024 bytes; if >99% are zero the framebuffer is blank.
        Uses 1024 (not 256) to reduce false positives on sparse OSD frames.
        """
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            sample   = os.read(self._fd, 1024)
            nonzero  = sum(1 for b in bytearray(sample) if b != 0)
            return nonzero < 8
        except Exception:
            return False

    # ── Hardware grab (video+OSD composite) ──────────────────────────────────

    def grab_via_tool(self, output_path, jpeg_quality=90):
        """
        FIX #4 — STiH/Sigma/Broadcom: live video lives in a hardware plane
        that is NOT in /dev/fb0. The Enigma2 'grab' binary composites all
        planes together. Try it first; return True on success.

        Tries both JPEG (-j) and PNG (-p) flags depending on binary version.
        Falls back to raw framebuffer read if no grab tool is found.
        """
        for binary in GRAB_BINS:
            # Check binary exists and is executable
            found = False
            if os.sep in binary:
                found = os.path.isfile(binary) and os.access(binary, os.X_OK)
            else:
                try:
                    subprocess.check_call(
                        [binary, "--version"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    found = True
                except Exception:
                    pass

            if not found:
                continue

            # Try JPEG grab
            for args in (
                [binary, "-j", str(jpeg_quality), output_path],
                [binary, "-p", output_path],
                [binary, output_path],
            ):
                try:
                    ret = subprocess.call(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if ret == 0 and os.path.isfile(output_path) \
                            and os.path.getsize(output_path) > 512:
                        return True
                except Exception:
                    continue

        return False  # no grab tool available — caller uses raw fb read

    # ── Raw capture ──────────────────────────────────────────────────────────

    def capture_raw(self):
        """
        Return raw framebuffer bytes.

        FIX #1 — seek to yoffset*stride so we read the VISIBLE page,
        not the invisible back-buffer (which is always black on
        double/triple-buffered STBs).

        Uses 64 KB chunked reads for Python 2 compatibility on large
        1920x1080 ARGB buffers (~8 MB).
        """
        info      = self._fb_info
        bpp_bytes = info["bpp"] // 8
        stride    = info["xres"] * bpp_bytes
        yoffset   = info.get("yoffset", 0)
        offset    = yoffset * stride          # FIX #1: double-buffer offset
        byte_size = info["yres"] * stride

        os.lseek(self._fd, offset, os.SEEK_SET)

        chunks    = []
        remaining = byte_size
        while remaining > 0:
            chunk = os.read(self._fd, min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def get_info(self):
        return dict(self._fb_info)
