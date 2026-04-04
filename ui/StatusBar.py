# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
from Screens.Screen import Screen
from Components.Label import Label


class StatusBar(Screen):
    skin = """
    <screen name="StatusBar" position="30,30" size="280,50"
            flags="wfNoBorder" backgroundColor="#AA000000">
        <widget name="rec" position="5,5" size="270,40"
                font="Regular;26" foregroundColor="#FF3333"
                backgroundColor="transparent" valign="center" halign="left"/>
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["rec"] = Label("\u25cf REC  00:00")

    def update(self, elapsed_secs):
        m, s = divmod(int(elapsed_secs), 60)
        self["rec"].setText("\u25cf REC  {:02d}:{:02d}".format(m, s))
