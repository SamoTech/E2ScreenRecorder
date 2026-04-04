# -*- coding: utf-8 -*-
"""
Python 2/3 unified shims for E2ScreenRecorder.
"""
from __future__ import absolute_import, print_function, division
import sys
import os
import threading

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3

if PY2:
    string_types  = (str, unicode)   # noqa: F821
    text_type     = unicode           # noqa: F821
    binary_type   = str
    integer_types = (int, long)      # noqa: F821
    range         = xrange            # noqa: F821
else:
    string_types  = (str,)
    text_type     = str
    binary_type   = bytes
    integer_types = (int,)
    range         = range


def makedirs_safe(path):
    """os.makedirs that does not raise if path already exists."""
    try:
        os.makedirs(path)
    except OSError:
        pass


def ensure_bytes(s, encoding="utf-8"):
    if isinstance(s, binary_type):
        return s
    return s.encode(encoding)


def ensure_str(s, encoding="utf-8"):
    if isinstance(s, text_type):
        return s
    return s.decode(encoding)


def communicate_safe(proc, timeout=None):
    """
    subprocess.communicate() with optional timeout.

    Python 3.3+: uses native timeout parameter.
    Python 2   : timeout is implemented via a daemon thread that joins
                 with the given deadline; process is terminated on timeout.

    Returns (stdout_bytes, stderr_bytes).
    Raises RuntimeError on timeout.
    """
    if not PY2:
        # Python 3 — native timeout support
        try:
            return proc.communicate(timeout=timeout)
        except TypeError:
            # Very old Py3 build without timeout kwarg (shouldn't happen)
            return proc.communicate()

    # Python 2 path
    if timeout is None:
        return proc.communicate()

    result = [None, None]
    exc    = [None]

    def _worker():
        try:
            result[0], result[1] = proc.communicate()
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_worker)
    t.daemon = True
    t.start()
    t.join(timeout)

    if t.is_alive():
        try:
            proc.terminate()
        except Exception:
            pass
        t.join(5)
        raise RuntimeError(
            "subprocess timed out after {}s".format(timeout))

    if exc[0] is not None:
        raise exc[0]

    return result[0], result[1]
