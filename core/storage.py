# -*- coding: utf-8 -*-
# v1.0.1 — post-audit patch
# Fixes: FIX-020 (per-path OSError logging + guaranteed /tmp fallback)
from __future__ import absolute_import, print_function, division

import os
import time
import json

from ..utils.logger import log


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
            if not (os.path.ismount(parent) or parent == "/tmp"):
                continue
            if not os.path.exists(path):
                try:
                    os.makedirs(path)
                except OSError as e:
                    # FIX-020: log the specific error per path instead of
                    # silently swallowing it, then try next candidate
                    log.warn("StorageManager: cannot create {}: {}".format(
                        path, e))  # FIX-020
                    continue
            if os.access(path, os.W_OK):
                return path
            else:
                log.warn("StorageManager: {} not writable, skipping".format(
                    path))  # FIX-020

        # FIX-020: guaranteed /tmp fallback with explicit log entry
        fallback = "/tmp/screenshots"
        log.warn("StorageManager: all preferred paths failed, "
                 "falling back to {}".format(fallback))  # FIX-020
        if not os.path.exists(fallback):
            try:
                os.makedirs(fallback)
            except OSError as e:
                log.error("StorageManager: fallback mkdir failed: {}".format(e))
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
        """Write JSON sidecar metadata next to each capture file."""
        meta_path = capture_path + ".json"
        try:
            with open(meta_path, "w") as f:
                json.dump(meta, f)
        except Exception as e:
            log.warn("StorageManager: metadata write failed: {}".format(e))

    def list_captures(self):
        """Return list of dicts sorted newest-first for WebIF."""
        base    = self._get_base()
        result  = []
        try:
            for name in os.listdir(base):
                if name.endswith(".json"):
                    continue
                full = os.path.join(base, name)
                if os.path.isfile(full):
                    try:
                        st = os.stat(full)
                        result.append({
                            "name":  name,
                            "path":  full,
                            "size":  st.st_size,
                            "mtime": st.st_mtime,
                        })
                    except OSError:
                        pass
        except OSError:
            pass
        result.sort(key=lambda x: x["mtime"], reverse=True)
        return result
