# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList


class MainMenu(Screen):
    skin = """
    <screen name="MainMenu" position="center,center" size="560,380" title="Screen Recorder">
        <widget name="menu"   position="10,10"  size="540,300" scrollbarMode="showOnDemand"/>
        <widget name="hint"   position="10,320" size="540,50"  font="Regular;20"
                foregroundColor="#aaaaaa"/>
    </screen>"""

    def __init__(self, session, items):
        Screen.__init__(self, session)
        self._items = items
        self["menu"] = MenuList([x[0] for x in items])
        self["hint"] = Label("OK=Select  EXIT=Close")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok": self._ok, "cancel": self.close,
             "up": lambda: self["menu"].up(),
             "down": lambda: self["menu"].down()}, -1)

    def _ok(self):
        idx = self["menu"].getSelectedIndex()
        if 0 <= idx < len(self._items):
            self._items[idx][1]()
