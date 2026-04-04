# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import (
    config, ConfigSubsection, ConfigSelection,
    ConfigInteger, ConfigYesNo, getConfigListEntry
)
from Components.ConfigList import ConfigListScreen

config.plugins.E2ScreenRecorder = ConfigSubsection()
cfg = config.plugins.E2ScreenRecorder

cfg.screenshot_fmt  = ConfigSelection(default="PNG",
    choices=["PNG", "JPEG", "BMP", "PPM"])
cfg.jpeg_quality    = ConfigInteger(default=85, limits=(10, 100))
cfg.video_fps       = ConfigSelection(default="5",
    choices=["1", "2", "5", "10", "15", "25"])
cfg.video_fmt       = ConfigSelection(default="mp4",
    choices=["mp4", "avi", "mkv", "ts"])
cfg.fb_device       = ConfigSelection(default="auto",
    choices=["auto", "/dev/fb0", "/dev/fb1"])
cfg.low_ram_mode    = ConfigYesNo(default=False)
cfg.webif_enabled   = ConfigYesNo(default=True)
cfg.webif_port      = ConfigInteger(default=8765, limits=(1024, 65535))
cfg.show_rec_osd    = ConfigYesNo(default=True)


class SettingsScreen(ConfigListScreen, Screen):
    skin = """
    <screen name="SettingsScreen" position="center,center"
            size="640,480" title="Screen Recorder Settings">
        <widget name="config" position="10,10" size="620,420"
                scrollbarMode="showOnDemand"/>
        <widget name="hint"   position="10,440" size="620,30"
                font="Regular;18" foregroundColor="#888888"/>
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["hint"] = Label("OK=Save  EXIT=Cancel")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok": self._save, "cancel": self.close,
             "up": self.keyUp, "down": self.keyDown}, -1)
        self._entries = [
            getConfigListEntry("Screenshot Format",     cfg.screenshot_fmt),
            getConfigListEntry("JPEG Quality (%)",      cfg.jpeg_quality),
            getConfigListEntry("Video FPS",             cfg.video_fps),
            getConfigListEntry("Video Format",          cfg.video_fmt),
            getConfigListEntry("Framebuffer Device",    cfg.fb_device),
            getConfigListEntry("Low RAM Mode (<256MB)", cfg.low_ram_mode),
            getConfigListEntry("WebIF Enabled",         cfg.webif_enabled),
            getConfigListEntry("WebIF Port",            cfg.webif_port),
            getConfigListEntry("Show REC OSD",          cfg.show_rec_osd),
        ]
        ConfigListScreen.__init__(self, self._entries, session=session)

    def _save(self):
        for e in self._entries:
            e[1].save()
        config.plugins.E2ScreenRecorder.save()
        self.close()
