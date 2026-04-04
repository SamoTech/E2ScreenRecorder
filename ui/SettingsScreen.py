# -*- coding: utf-8 -*-
"""
Full settings ConfigScreen for E2ScreenRecorder.
"""
from __future__ import absolute_import, print_function, division

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import (
    config, ConfigSubsection, ConfigSelection,
    ConfigInteger, ConfigYesNo, getConfigListEntry
)
from Components.ConfigList import ConfigListScreen

# ── Config tree ───────────────────────────────────────────────────────────────
if not hasattr(config, "plugins"):
    from Components.config import ConfigSubsection as _CS
    config.plugins = _CS()

try:
    cfg = config.plugins.E2ScreenRecorder
except AttributeError:
    config.plugins.E2ScreenRecorder = ConfigSubsection()
    cfg = config.plugins.E2ScreenRecorder

for _attr, _val in [
    ("screenshot_fmt",  lambda: ConfigSelection(default="PNG",
        choices=["PNG", "JPEG", "BMP", "PPM"])),
    ("jpeg_quality",    lambda: ConfigInteger(default=92, limits=(10, 100))),
    ("video_fps",       lambda: ConfigSelection(default="5",
        choices=["1", "2", "5", "10", "15", "25"])),
    ("video_fmt",       lambda: ConfigSelection(default="mp4",
        choices=["mp4", "avi", "mkv", "ts"])),
    ("fb_device",       lambda: ConfigSelection(default="auto",
        choices=["auto", "/dev/fb0", "/dev/fb1"])),
    ("low_ram_mode",    lambda: ConfigYesNo(default=False)),
    ("upscale_sd",      lambda: ConfigYesNo(default=False)),   # NEW
    ("webif_enabled",   lambda: ConfigYesNo(default=True)),
    ("webif_port",      lambda: ConfigInteger(default=8765, limits=(1024, 65535))),
    ("show_rec_osd",    lambda: ConfigYesNo(default=True)),
]:
    if not hasattr(cfg, _attr):
        setattr(cfg, _attr, _val())


class SettingsScreen(ConfigListScreen, Screen):
    skin = """
    <screen name="SettingsScreen" position="center,center"
            size="640,500" title="Screen Recorder Settings">
        <widget name="config"  position="10,10"  size="620,440"
                scrollbarMode="showOnDemand"/>
        <widget name="hint"    position="10,455" size="620,35"
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
            getConfigListEntry("Screenshot Format",       cfg.screenshot_fmt),
            getConfigListEntry("JPEG Quality (%)",        cfg.jpeg_quality),
            getConfigListEntry("Upscale SD to 720p",      cfg.upscale_sd),
            getConfigListEntry("Video FPS",               cfg.video_fps),
            getConfigListEntry("Video Format",            cfg.video_fmt),
            getConfigListEntry("Framebuffer Device",      cfg.fb_device),
            getConfigListEntry("Low RAM Mode (<256MB)",   cfg.low_ram_mode),
            getConfigListEntry("WebIF Enabled",           cfg.webif_enabled),
            getConfigListEntry("WebIF Port",              cfg.webif_port),
            getConfigListEntry("Show REC OSD",            cfg.show_rec_osd),
        ]
        ConfigListScreen.__init__(self, self._entries, session=session)

    def _save(self):
        for e in self._entries:
            e[1].save()
        config.plugins.E2ScreenRecorder.save()
        self.close()
