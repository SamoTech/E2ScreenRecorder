# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
import os
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap

try:
    from enigma import loadPic
    _LOADPIC = True
except ImportError:
    _LOADPIC = False


class Preview(Screen):
    skin = """
    <screen name="Preview" position="center,center"
            size="700,450" title="Last Screenshot">
        <widget name="thumb" position="10,10" size="680,380"/>
        <widget name="info"  position="10,400" size="680,40"
                font="Regular;20" halign="center"/>
    </screen>"""

    def __init__(self, session, image_path):
        Screen.__init__(self, session)
        self._path = image_path
        self["thumb"] = Pixmap()
        self["info"]  = Label(os.path.basename(image_path))
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.close, "cancel": self.close}, -1)
        self.onShown.append(self._load_image)

    def _load_image(self):
        if not _LOADPIC:
            self["info"].setText("Preview N/A (loadPic missing)")
            return
        try:
            ptr = loadPic(self._path, 680, 380, 0, 0, 0, 1)
            if ptr:
                self["thumb"].instance.setPixmap(ptr)
        except Exception:
            self["info"].setText("Preview unavailable")
