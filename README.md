# E2ScreenRecorder

> Full-featured Screen Recorder plugin for **all Enigma2 STB devices**.
> Captures `/dev/fb0` framebuffer → PNG / JPEG / BMP screenshots and
> MP4 / AVI / MKV video recordings. Includes a **built-in WebIF** so you
> can control the recorder from any browser on your LAN (phone or PC).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 2.7+](https://img.shields.io/badge/python-2.7%20%7C%203.x-blue.svg)]()
[![Platform: Enigma2](https://img.shields.io/badge/platform-Enigma2-orange.svg)]()

---

## Features

| Feature | Detail |
|---|---|
| **Screenshots** | PNG (lossless), JPEG (configurable quality), BMP, PPM |
| **Video recording** | MP4 via FFmpeg; AVI/MKV; frame-ZIP fallback (no FFmpeg needed) |
| **WebIF** | Full control page at `http://STB-IP:8765/` — works on any phone/PC |
| **Framebuffer** | ARGB8888, RGBA8888, RGB565, BGR888, CLUT8 — all bpp auto-detected |
| **HiSilicon STBs** | Auto-detects blank `/dev/fb0` and falls back to `/dev/fb1` |
| **Double-buffering** | Reads `yoffset` from `FBIOGET_VSCREENINFO` for correct visible page |
| **Low RAM safety** | Ring-buffer mode (30-frame cap) for devices with \u2264256 MB RAM |
| **Python compat** | Single codebase: Python 2.7 through 3.12+ |
| **Zero mandatory deps** | stdlib-only fallback always available; PIL/FFmpeg/cv2 are optional |

---

## Architecture

```
E2ScreenRecorder/
\u251c\u2500\u2500 __init__.py              # Enigma2 plugin entry point
\u251c\u2500\u2500 plugin.py                # PluginDescriptor registration
\u251c\u2500\u2500 ScreenRecorderPlugin.py  # Main Screen class (UI + orchestration)
\u251c\u2500\u2500 core/
\u2502   \u251c\u2500\u2500 framebuffer.py       # FB capture engine (ioctl + chunked read)
\u2502   \u251c\u2500\u2500 converter.py         # Pixel format normalisation \u2192 RGB24
\u2502   \u251c\u2500\u2500 encoder.py           # Image/video encoder dispatcher
\u2502   \u251c\u2500\u2500 recorder.py          # Threaded video capture + muxing
\u2502   \u251c\u2500\u2500 storage.py           # Path resolver + metadata writer
\u2502   \u2514\u2500\u2500 compat.py            # Python 2/3 unified shims
\u251c\u2500\u2500 backends/
\u2502   \u251c\u2500\u2500 GrabberPIL.py        # PIL/Pillow backend (best quality)
\u2502   \u251c\u2500\u2500 GrabberPPM.py        # Pure Python PNG/PPM (zero deps)
\u2502   \u251c\u2500\u2500 GrabberFFmpeg.py     # FFmpeg CLI subprocess backend
\u2502   \u251c\u2500\u2500 GrabberGstreamer.py  # GStreamer Python binding backend
\u2502   \u2514\u2500\u2500 GrabberOpenCV.py     # OpenCV (cv2) optional backend
\u251c\u2500\u2500 ui/
\u2502   \u251c\u2500\u2500 MainMenu.py          # Navigation menu screen
\u2502   \u251c\u2500\u2500 Preview.py           # Thumbnail preview screen
\u2502   \u251c\u2500\u2500 StatusBar.py         # OSD overlay: REC indicator + timer
\u2502   \u2514\u2500\u2500 SettingsScreen.py    # Full settings ConfigScreen
\u251c\u2500\u2500 webif/
\u2502   \u2514\u2500\u2500 server.py            # Embedded HTTP server + SPA WebIF
\u251c\u2500\u2500 utils/
\u2502   \u251c\u2500\u2500 logger.py            # Levelled logger \u2192 /tmp/E2ScreenRecorder.log
\u2502   \u2514\u2500\u2500 notify.py            # Enigma2 notification helper
\u251c\u2500\u2500 locale/ar/LC_MESSAGES/
\u2502   \u2514\u2500\u2500 E2ScreenRecorder.po  # Arabic translation
\u251c\u2500\u2500 meta/
\u2502   \u251c\u2500\u2500 plugin.xml
\u2502   \u2514\u2500\u2500 CONTROL/control      # ipk package descriptor
\u2514\u2500\u2500 build.sh                 # ipk builder script
```

---

## Installation

### Method 1 \u2014 opkg (recommended)

```bash
opkg update
opkg install enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk
```

### Method 2 \u2014 Manual SCP

```bash
scp -r E2ScreenRecorder/ \
  root@STB-IP:/usr/lib/enigma2/python/Plugins/Extensions/
# Then restart Enigma2:
ssh root@STB-IP killall -1 enigma2
```

### Optional dependencies (greatly improve quality)

```bash
opkg install python3-pillow   # Best screenshot quality
opkg install ffmpeg           # Video recording
```

---

## WebIF

Once the plugin is open on the STB, navigate to **Settings \u2192 Start WebIF Server**,
or enable **WebIF Enabled** in settings (auto-starts when plugin opens).

Then open from any device on your LAN:

```
http://<STB-IP>:8765/
```

**WebIF features:**
- \uD83D\uDCF7 Take screenshot (PNG / JPEG / BMP)
- \uD83C\uDFA5 Start / Stop video recording
- \u23EC Download any capture directly to your device
- Live REC timer with 2-second status polling
- Dark / light mode toggle
- Works on mobile, tablet, and desktop browsers

---

## Dependency Matrix

| Backend | Dependency | Py2 | Py3 | Notes |
|---|---|---|---|---|
| `GrabberPPM` | None (stdlib) | \u2705 | \u2705 | Universal fallback |
| `GrabberPIL` | `python3-pillow` | \u2705 | \u2705 | Best screenshot quality |
| `GrabberFFmpeg` | `ffmpeg` binary | \u2705 | \u2705 | Best for video |
| `GrabberGstreamer` | `gi.repository` | \u2705 | \u2705 | Native E2 integration |
| `GrabberOpenCV` | `python3-opencv` | \u26a0\ufe0f | \u2705 | Optional enhancement |
| NumPy conversion | `python3-numpy` | \u2705 | \u2705 | Speed-up only, optional |

---

## Supported Enigma2 Images

OpenPLi 4.x\u201312.x, OpenATV 6.x\u20137.x, OpenDreambox OE2.0/2.5/2.6,
VTi, Merlin, OpenVIX, OpenBH (Black Hole), OpenSPA, Pure2, EGAMI,
OpenHDF, OpenRSI, DGS, teamBlue, SifTeam, OpenMIPS, OoZooN,
Beyonwiz, Xtrend OE, IHAD, Newnigma2, NCam \u2014 and all derivatives.

---

## Tested Devices

| Device | Image | Python | SoC |
|---|---|---|---|
| DM920 UHD | OpenPLi 9.0 | 3.9 | ARMv7 |
| VU+ Duo4K | OpenATV 7.2 | 3.10 | ARMv8 |
| VU+ Solo2 | VTi 14 | 2.7 | MIPS |
| Xtrend ET10000 | Pure2 | 3.6 | ARMv7 |
| DM900 | OpenDreambox OE2.6 | 3.8 | ARMv7 |
| DM800se | OpenPLi 4.0 | 2.7 | MIPS (128MB) |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Blank screenshots | HiSilicon device \u2014 plugin auto-detects `/dev/fb1` |
| No video output | FFmpeg not found \u2014 ZIP of PNG frames saved as fallback |
| Plugin crashes (low RAM) | Enable **Low RAM Mode** in Settings (30-frame ring buffer) |
| WebIF unreachable | Default port 8765 \u2014 configurable in Settings; check STB firewall |
| Logs | `/tmp/E2ScreenRecorder.log` |

---

## Building the ipk

```bash
bash build.sh
# Output: enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk
```

Requires `fakeroot` and `dpkg-deb` on the build machine.

---

## License

MIT \u00a9 2026 [SamoTech](https://github.com/SamoTech)
