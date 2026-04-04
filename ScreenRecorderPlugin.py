# -*- coding: utf-8 -*-
"""
Main Enigma2 Screen class for E2ScreenRecorder.
All UI operations run in the E2 main thread via eTimer.

Black-screenshot fix integration:
  _take_screenshot() now calls grab_via_tool() first.
  Only falls back to raw framebuffer read if grab tool unavailable.
"""
from __future__ import absolute_import, print_function, division

import os
import time

from Screens.Screen   import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from enigma import eTimer

from .core.framebuffer import FramebufferCapture
from .core.converter   import PixelConverter
from .core.recorder    import FrameRecorder
from .core.storage     import StorageManager
from .core.encoder     import save_screenshot
from .utils.logger     import log
from .utils.notify     import showNotification

try:
    from .ui.SettingsScreen import SettingsScreen, cfg
except Exception:
    SettingsScreen = None
    cfg = None

try:
    from .webif.server import WebIFServer
    HAS_WEBIF = True
except Exception:
    HAS_WEBIF = False


class E2ScreenRecorder(Screen):

    skin = """
    <screen name="E2ScreenRecorder" position="center,center"
            size="620,430" title="Screen Recorder">
        <widget name="menu"    position="10,10"  size="600,330"
                scrollbarMode="showOnDemand"/>
        <widget name="status"  position="10,355" size="600,35"
                font="Regular;22"/>
        <widget name="rec_ind" position="10,395" size="300,28"
                font="Regular;22" foregroundColor="#FF3333"/>
        <widget name="webif"   position="320,395" size="290,28"
                font="Regular;18" foregroundColor="#33AAFF"/>
    </screen>"""

    def __init__(self, session, args=None):
        Screen.__init__(self, session)

        self._recorder  = None
        self._rec_start = 0.0
        self._last_shot = None
        self._storage   = StorageManager()
        self._webif     = None

        # eTimer — compatible with all E2 image variants
        self._rec_timer = eTimer()
        try:
            self._rec_timer.timeout.append(self._update_rec_indicator)
        except AttributeError:
            try:
                self._rec_timer.callback.append(self._update_rec_indicator)
            except Exception:
                pass

        menu_items = [
            ("\U0001f4f7  Screenshot (PNG)",         self._screenshot_png),
            ("\U0001f4f7  Screenshot (JPEG)",        self._screenshot_jpeg),
            ("\U0001f4f7  Screenshot (BMP)",         self._screenshot_bmp),
            ("\U0001f5bc   Preview Last Screenshot",  self._preview_last),
            ("\U0001f3a5  Start Recording",          self._start_recording),
            ("\u23f9   Stop Recording",              self._stop_recording),
            ("\U0001f4c2  Show Captures Folder",     self._show_folder),
            ("\U0001f310  Start WebIF Server",       self._start_webif),
            ("\u2699\ufe0f   Settings",              self._open_settings),
            ("\u274c  Exit",                         self.close),
        ]

        self["menu"]   = MenuList([x[0] for x in menu_items])
        self["status"] = Label("Ready \u2014 E2ScreenRecorder")
        self["rec_ind"] = Label("")
        self["webif"]  = Label("")
        self._menu_map = menu_items

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok":     self._menu_selected,
             "cancel": self.close,
             "up":     lambda: self["menu"].up(),
             "down":   lambda: self["menu"].down()}, -1)

        self.onShow.append(self._on_show)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def _on_show(self):
        if cfg and cfg.webif_enabled.value and HAS_WEBIF:
            self._start_webif(silent=True)

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _menu_selected(self):
        idx = self["menu"].getSelectedIndex()
        if 0 <= idx < len(self._menu_map):
            self._menu_map[idx][1]()

    # ── Screenshot ───────────────────────────────────────────────────────────

    def _take_screenshot(self, fmt="PNG"):
        try:
            dev = None
            if cfg and cfg.fb_device.value != "auto":
                dev = cfg.fb_device.value

            fb   = FramebufferCapture(device=dev)
            path = self._storage.next_screenshot_path(fmt.lower())

            # FIX: try Enigma2 native grab tool first (captures video+OSD composite)
            #      Only fall back to raw framebuffer read if grab unavailable.
            fb.open()
            grabbed = fb.grab_via_tool(path, jpeg_quality=90)

            if not grabbed:
                # Raw framebuffer path
                info = fb.get_info()
                raw  = fb.capture_raw()
                fb.close()
                rgb  = PixelConverter.to_rgb24(raw, info)
                save_screenshot(rgb, info["xres"], info["yres"], path, fmt)
            else:
                fb.close()
                # grab wrote a JPEG — if user wants PNG, convert
                if fmt.upper() == "PNG" and path.endswith(".jpg"):
                    png_path = path.replace(".jpg", ".png")
                    try:
                        from PIL import Image
                        Image.open(path).save(png_path)
                        os.remove(path)
                        path = png_path
                    except Exception:
                        pass  # keep the JPEG, it's valid

            self._last_shot = path
            self._storage.write_metadata(path, {})
            short = os.path.basename(path)
            self["status"].setText("Saved: " + short)
            log.info("Screenshot saved: {}".format(path))
            showNotification("Screenshot saved:\n{}".format(short), timeout=4)

        except Exception as e:
            self["status"].setText("Error: " + str(e))
            log.error("Screenshot failed: {}".format(e))

    def _screenshot_png(self):   self._take_screenshot("PNG")
    def _screenshot_jpeg(self):  self._take_screenshot("JPEG")
    def _screenshot_bmp(self):   self._take_screenshot("BMP")

    # ── Preview ──────────────────────────────────────────────────────────────

    def _preview_last(self):
        if self._last_shot and os.path.isfile(self._last_shot):
            try:
                from .ui.Preview import Preview
                self.session.open(Preview, self._last_shot)
            except Exception:
                self["status"].setText("Preview unavailable")
        else:
            captures = self._storage.list_captures()
            shots = [c for c in captures if c["name"].startswith("shot_")]
            if shots:
                try:
                    from .ui.Preview import Preview
                    self.session.open(Preview, shots[0]["path"])
                except Exception:
                    pass
            else:
                self["status"].setText("No screenshots found")

    # ── Recording ────────────────────────────────────────────────────────────

    def _start_recording(self):
        if self._recorder and self._recorder.is_alive():
            showNotification("Recording already in progress!", timeout=3)
            return

        fps     = int(cfg.video_fps.value) if cfg else 5
        fmt     = cfg.video_fmt.value      if cfg else "mp4"
        low_ram = cfg.low_ram_mode.value   if cfg else False
        dev     = (cfg.fb_device.value
                   if cfg and cfg.fb_device.value != "auto" else None)

        path = self._storage.next_video_path(fmt)
        self._recorder  = FrameRecorder(
            output_path=path, fps=fps, fmt=fmt,
            fb_device=dev, on_error=self._on_record_error, low_ram=low_ram)
        self._rec_start = time.time()
        self._recorder.start()

        if cfg and cfg.show_rec_osd.value:
            self["rec_ind"].setText("\u25cf REC  00:00")
        self["status"].setText("Recording: " + os.path.basename(path))

        try:
            self._rec_timer.start(1000, False)
        except Exception:
            pass

        showNotification("Recording started...", timeout=2)
        log.info("Recording started \u2192 {}".format(path))

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        try:
            self._rec_timer.stop()
        except Exception:
            pass
        self["rec_ind"].setText("")
        self["status"].setText("Recording saved.")
        showNotification("Recording stopped and saved.", timeout=4)
        log.info("Recording stopped.")

    def _update_rec_indicator(self):
        if self._recorder and self._recorder.is_alive():
            elapsed = time.time() - self._rec_start
            m, s    = divmod(int(elapsed), 60)
            self["rec_ind"].setText("\u25cf REC  {:02d}:{:02d}".format(m, s))
        else:
            try:
                self._rec_timer.stop()
            except Exception:
                pass

    def _on_record_error(self, msg):
        self["status"].setText("REC Error: " + msg)
        log.error("Recorder error: {}".format(msg))

    # ── WebIF ─────────────────────────────────────────────────────────────────

    def _start_webif(self, silent=False):
        if not HAS_WEBIF:
            if not silent:
                self["status"].setText("WebIF not available")
            return
        if self._webif and self._webif.is_running():
            if not silent:
                self["status"].setText("WebIF already running")
            return
        port = cfg.webif_port.value if cfg else 8765
        try:
            self._webif = WebIFServer(
                port=port, storage=self._storage,
                get_recorder=lambda: self._recorder,
                do_screenshot=self._take_screenshot,
                do_start_rec=self._start_recording,
                do_stop_rec=self._stop_recording,
            )
            self._webif.start()
            ip = self._get_local_ip()
            self["webif"].setText("WebIF: {}:{}".format(ip, port))
            if not silent:
                showNotification(
                    "WebIF started at http://{}:{}/".format(ip, port), timeout=5)
            log.info("WebIF started on port {}".format(port))
        except Exception as e:
            log.error("WebIF start failed: {}".format(e))
            if not silent:
                self["status"].setText("WebIF error: " + str(e))

    def _get_local_ip(self):
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "STB-IP"

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _show_folder(self):
        base = self._storage._get_base()
        self["status"].setText("Folder: " + base)
        showNotification("Captures stored in:\n{}".format(base), timeout=5)

    def _open_settings(self):
        if SettingsScreen:
            self.session.open(SettingsScreen)
        else:
            self["status"].setText("Settings unavailable")
