# -*- coding: utf-8 -*-
"""
Enigma2 notification helper - degrades gracefully when not in E2 env.
"""
from __future__ import absolute_import, print_function, division


def showNotification(msg, title="Screen Recorder", timeout=5):
    try:
        from Screens.MessageBox import MessageBox
        import NavigationInstance
        session = NavigationInstance.instance
        if session is not None:
            session.openWithCallback(
                lambda ret: None, MessageBox, msg,
                MessageBox.TYPE_INFO, timeout=timeout)
            return
    except Exception:
        pass
    try:
        from Screens.MessageBox import MessageBox
        from Tools.Notifications import addNotification
        addNotification(MessageBox, text=msg,
                        type=MessageBox.TYPE_INFO, timeout=timeout)
        return
    except Exception:
        pass
    try:
        import sys
        print("[E2ScreenRecorder] NOTIFY: {}".format(msg), file=sys.stderr)
    except Exception:
        pass
