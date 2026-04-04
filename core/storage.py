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
            try:
                os.makedirs(fallback)
            except OSError:
                pass
        return fallback

    def _timestamp(self):
        return time.strftime("%Y%m%d_%H%M%S")

    def next_screenshot_path(self, ext="png"):
        base = self._get_base()
        return os.path.join(base, "shot_{}.{}".format(self._timestamp(), ext))

    def next_video_path(self, ext="mp4"):
        base = self._get_base()
        return os.path.join(base, "rec_{}.{}".format(self._timestamp(), ext))

    def write_metadata(self, image_path, meta):
        try:
            json_path = image_path + ".json"
            with open(json_path, "w") as f:
                json.dump(meta, f)
        except Exception:
            pass

    def list_captures(self):
        base = self._get_base()
        items = []
        try:
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".json"):
                    continue
                fpath = os.path.join(base, name)
                if os.path.isfile(fpath):
                    try:
                        st = os.stat(fpath)
                        items.append({
                            "name":  name,
                            "path":  fpath,
                            "size":  st.st_size,
                            "mtime": int(st.st_mtime),
                        })
                    except OSError:
                        pass
        except OSError:
            pass
        return items
