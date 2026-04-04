# -*- coding: utf-8 -*-
"""
Python 2/3 unified compatibility shims for E2ScreenRecorder.
Import this module first in every other module.
"""
from __future__ import absolute_import, print_function, division

import sys
import os
import io

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3

if PY2:
    string_types  = (str, unicode)   # noqa: F821
    text_type     = unicode           # noqa: F821
    binary_type   = str
    integer_types = (int, long)       # noqa: F821
    range         = xrange            # noqa: F821

    def iteritems(d):   return d.iteritems()
    def itervalues(d):  return d.itervalues()
else:
    string_types  = (str,)
    text_type     = str
    binary_type   = bytes
    integer_types = (int,)
    range         = range

    def iteritems(d):   return d.items()
    def itervalues(d):  return d.values()


def ensure_bytes(s, encoding="utf-8"):
    if isinstance(s, binary_type):
        return s
    return s.encode(encoding)


def ensure_str(s, encoding="utf-8"):
    if isinstance(s, binary_type):
        return s.decode(encoding)
    return s


def open_binary(path, mode="rb"):
    return io.open(path, mode)


def makedirs_safe(path):
    """os.makedirs with exist_ok equivalent for Python 2."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError:
            pass
