# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division

import os
import time
import json


class StorageManager(object):

    SEARCH_PATHS = [
        "/media/hdd/screenshots",
        "/media/usb/screenshots",
        "/media/mmc/screenshots",
        "/tmp/screenshots",
    ]

    def _get_base(self):
        for path in self.SEARCH_PATHS:
            parent = os.path.dirname(path)
            if os.path.ismount(parent) or parent == "/tmp":
                if not os.path.exists(path):
                    try:
                        os.makedirs(path)
                    except OSError:
                        continue
                if os.access(path, os.W_OK):
                    return path
        fallback = "/tmp/screenshots"
        if not os.path.exists(fallback):
            os.makedirs(fallback)
        return fallback

    def _timestamp(self):
        return time.strftime("%Y%m%d_%H%M%S")

    def next_screenshot_path(self, ext="png"):
        base = self._get_base()
        return os.path.join(base, "shot_{}.{}".format(self._timestamp(), ext))

    def next_video_path(self, ext="mp4"):
        base = self._get_base()
        return os.path.join(base, "rec_{}.{}".format(self._timestamp(), ext))

    def write_metadata(self, capture_path, meta):
        """Write a sidecar .json next to the capture file."""
        try:
            meta_path = capture_path + ".json"
            meta["timestamp"] = self._timestamp()
            with open(meta_path, "w") as f:
                json.dump(meta, f)
        except Exception:
            pass

    def list_captures(self):
        """Return list of capture dicts sorted newest-first."""
        base = self._get_base()
        items = []
        try:
            for name in os.listdir(base):
                if name.endswith(".json"):
                    continue
                path = os.path.join(base, name)
                if os.path.isfile(path):
                    try:
                        st = os.stat(path)
                        items.append({
                            "name": name,
                            "path": path,
                            "size": st.st_size,
                            "mtime": int(st.st_mtime),
                        })
                    except OSError:
                        pass
        except OSError:
            pass
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return items
