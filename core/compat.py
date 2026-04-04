# -*- coding: utf-8 -*-
"""
Python 2/3 unified shims for E2ScreenRecorder.
"""
from __future__ import absolute_import, print_function, division
import sys
import os

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3

if PY2:
    string_types = (str, unicode)  # noqa: F821
    text_type    = unicode          # noqa: F821
    binary_type  = str
    integer_types = (int, long)    # noqa: F821
    range        = xrange           # noqa: F821
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
