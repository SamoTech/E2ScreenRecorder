# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division


def showNotification(message, timeout=4):
    try:
        from Screens.MessageBox import MessageBox
        from Tools.Notifications import AddNotification
        AddNotification(
            MessageBox,
            message,
            type=MessageBox.TYPE_INFO,
            timeout=timeout
        )
    except Exception:
        try:
            from Screens.Standby import TryWithRestart
        except Exception:
            pass
        try:
            from Tools.Notifications import AddNotification
            from Screens.MessageBox import MessageBox
            AddNotification(MessageBox, message,
                            type=MessageBox.TYPE_INFO, timeout=timeout)
        except Exception:
            pass
