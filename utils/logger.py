# -*- coding: utf-8 -*-
"""
Levelled logger -> /tmp/E2ScreenRecorder.log
Thread-safe, Python 2/3 compatible.
"""
from __future__ import absolute_import, print_function, division

import os
import threading
import time

LOG_PATH = "/tmp/E2ScreenRecorder.log"
MAX_SIZE  = 512 * 1024

LEVEL_DEBUG   = 10
LEVEL_INFO    = 20
LEVEL_WARNING = 30
LEVEL_ERROR   = 40

_LEVEL_NAMES = {
    LEVEL_DEBUG:   "DEBUG",
    LEVEL_INFO:    "INFO",
    LEVEL_WARNING: "WARNING",
    LEVEL_ERROR:   "ERROR",
}


class _Logger(object):

    def __init__(self):
        self._lock  = threading.Lock()
        self._level = LEVEL_DEBUG

    def set_level(self, level):
        self._level = level

    def _write(self, level, message):
        if level < self._level:
            return
        ts   = time.strftime("%Y-%m-%d %H:%M:%S")
        line = "[{}] [{}] {}\n".format(ts, _LEVEL_NAMES.get(level, "LOG"), message)
        with self._lock:
            try:
                if os.path.isfile(LOG_PATH) and os.path.getsize(LOG_PATH) >= MAX_SIZE:
                    os.rename(LOG_PATH, LOG_PATH + ".old")
                with open(LOG_PATH, "a") as f:
                    f.write(line)
            except Exception:
                pass

    def debug(self, msg):   self._write(LEVEL_DEBUG,   str(msg))
    def info(self, msg):    self._write(LEVEL_INFO,    str(msg))
    def warning(self, msg): self._write(LEVEL_WARNING, str(msg))
    def error(self, msg):   self._write(LEVEL_ERROR,   str(msg))


log = _Logger()
