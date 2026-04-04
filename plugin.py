# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
from Plugins.Plugin import PluginDescriptor

def main(session, **kwargs):
    from .ScreenRecorderPlugin import E2ScreenRecorder
    session.open(E2ScreenRecorder)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name        = "Screen Recorder",
            description = "Screenshot & video capture with WebIF",
            where       = [
                PluginDescriptor.WHERE_PLUGINMENU,
                PluginDescriptor.WHERE_EXTENSIONSMENU,
            ],
            icon        = "plugin.png",
            fnc         = main,
        )
    ]
