# -*- coding: utf-8 -*-
"""
StorageManager - resolves best writable output path,
checks quota, writes metadata sidecar files.
"""
from __future__ import absolute_import, print_function, division

import os
import time

from .compat import makedirs_safe


class StorageManager(object):

    SEARCH_PATHS = [
        "/media/hdd/screenshots",
        "/media/usb/screenshots",
        "/media/mmc/screenshots",
        "/media/cf/screenshots",
        "/tmp/screenshots",
    ]

    MIN_FREE_BYTES = 5 * 1024 * 1024

    def _free_space(self, path):
        try:
            st = os.statvfs(path)
            return st.f_bavail * st.f_frsize
        except Exception:
            return 0

    def _get_base(self):
        for path in self.SEARCH_PATHS:
            parent = os.path.dirname(path)
            is_acceptable = (parent == "/tmp" or
                             os.path.ismount(parent) or
                             os.path.ismount(os.path.dirname(parent)))
            if not is_acceptable:
                continue
            makedirs_safe(path)
            if os.path.isdir(path) and os.access(path, os.W_OK):
                if self._free_space(path) >= self.MIN_FREE_BYTES:
                    return path
        fallback = "/tmp/screenshots"
        makedirs_safe(fallback)
        return fallback

    def _timestamp(self):
        return time.strftime("%Y%m%d_%H%M%S")

    def next_screenshot_path(self, ext="png"):
        base = self._get_base()
        return os.path.join(base, "shot_{}.{}".format(self._timestamp(), ext))

    def next_video_path(self, ext="mp4"):
        base = self._get_base()
        return os.path.join(base, "rec_{}.{}".format(self._timestamp(), ext))

    def write_metadata(self, media_path, info):
        try:
            import json
            meta_path = media_path + ".json"
            with __import__('io').open(meta_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2)
        except Exception:
            pass

    def list_captures(self):
        captures = []
        for path in self.SEARCH_PATHS + ["/tmp/screenshots"]:
            if not os.path.isdir(path):
                continue
            for fname in os.listdir(path):
                if fname.startswith(("shot_", "rec_")):
                    full = os.path.join(path, fname)
                    try:
                        size  = os.path.getsize(full)
                        mtime = os.path.getmtime(full)
                        captures.append({"path": full, "name": fname,
                                         "size": size, "mtime": mtime})
                    except OSError:
                        pass
        captures.sort(key=lambda x: x["mtime"], reverse=True)
        return captures
