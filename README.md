# E2ScreenRecorder

> Capture screenshots and record screen video directly from your Enigma2
> set-top box. Works on every known device and image. Zero mandatory dependencies.

![Version](https://img.shields.io/badge/version-1.0.1-blue)
![Python](https://img.shields.io/badge/python-2.6%20%7C%202.7%20%7C%203.x-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)
![Platform](https://img.shields.io/badge/platform-Enigma2-orange)
![Maintained](https://img.shields.io/badge/maintained-yes-success)
![Audit](https://img.shields.io/badge/code%20audit-passed-success)

---

## Table of Contents

- [Features](#features)
- [Supported Devices](#supported-devices)
- [Supported Images](#supported-images)
- [Requirements](#requirements)
- [Installation](#installation)
- [Uninstallation](#uninstallation)
- [Usage](#usage)
- [WebIF Remote Control](#webif-remote-control)
- [Output Formats](#output-formats)
- [Storage Locations](#storage-locations)
- [Capability Tiers](#capability-tiers)
- [Dependency Matrix](#dependency-matrix)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [Changelog](#changelog)
- [License](#license)

---

## Features

| Feature | Detail |
|---|---|
| 📷 Screenshot | PNG · JPEG · BMP · PPM with zero-dependency fallback |
| 🎥 Screen Recording | MP4 H.264 via FFmpeg · ZIP frame archive fallback |
| 🌐 WebIF | Full browser control page — phone or PC on LAN |
| 🔄 Auto FB Detection | Auto-selects `/dev/fb0` or `/dev/fb1` (HiSilicon fix) |
| 🖥️ All Pixel Formats | ARGB8888 · RGBA8888 · RGB565 · RGB888 · CLUT8 · YUV420 |
| 🐍 Universal Python | Single codebase runs on Python 2.6 through 3.12+ |
| ⚡ Speed Optimization | Numpy fast path with pure Python fallback |
| 💾 Smart Storage | Auto-selects HDD → USB → MMC → /tmp |
| 🔴 Live REC Indicator | OSD overlay with MM:SS elapsed counter |
| 📦 Zero Mandatory Deps | Built-in PNG encoder — no external packages needed |
| 🛡️ Thread Safe | All E2 UI updates run on main thread via eTimer |
| 🔒 Audited | 5-phase code audit — 20 fixes applied, 37/37 tests passing |

---

## Supported Devices

### Broadcom BCM7xxx
Dreambox DM800se · DM900 UHD · DM920 UHD · DM7020HDv2 · DM7080 · DM820

### HiSilicon Hi35xx / Hi3798
AB PULSe 4K · AX HD51 · Mut@nt HD51 · OCTAGON SF4008 · ZGEMMA H9.2H

> ⚠️ These devices use `/dev/fb1` — **auto-detected at runtime**, no config needed.

### Amlogic S905 / S922
Formulier F4 · Formuler F4 Turbo · MECOOL KII Pro

### STMicroelectronics
VU+ Solo · VU+ Solo2 · VU+ Duo2 · VU+ Duo4K · VU+ Ultimo4K
VU+ Zero 4K · VU+ Uno4K · VU+ Solo4K

### Other ARMv7 / ARMv8
Xtrend ET10000 · ET13000 · GigaBlue UHD Trio · GigaBlue Quad4K
Edision OS Mio 4K · Octagon SF8008 · Mutant HD51

---

## Supported Images

| Image | Versions | Python |
|---|---|---|
| OpenPLi | 4.x – 12.x | 2.7 / 3.7 – 3.11 |
| OpenATV | 6.x – 7.x | 3.8 – 3.10 |
| OpenDreambox | OE2.0 / OE2.5 / OE2.6 | 3.6 – 3.9 |
| VTi | 13 / 14 | 2.7 / 3.6 |
| Merlin | 5.x – 7.x | 3.7+ |
| OpenVIX | 5.x – 6.x | 3.6+ |
| Black Hole (OpenBH) | 3.x | 3.8+ |
| OpenSPA | 7.x – 9.x | 3.6 – 3.9 |
| Pure2 | 1.x – 2.x | 3.6 – 3.8 |
| EGAMI | 9.x – 10.x | 3.7+ |
| FEED | 2.x | 3.8 |
| OpenHDF | 6.x | 3.8+ |
| OpenRSI | 5.x | 3.6+ |
| DGS | 3.x | 3.8 |
| teamBlue | 5.x | 3.9 |
| SifTeam | 4.x | 2.7 |
| OpenMIPS | 3.x | 2.7 |
| OoZooN | 2.x | 3.7 |
| Newnigma2 | 5.x | 2.7 |
| Beyonwiz | 3.x | 3.8 |
| IHAD | 2.x | 3.6 |
| NCam-based | any | 2.7 / 3.x |

---

## Requirements

### Mandatory — always present on any Enigma2 STB
- Enigma2 (any version, any year)
- Python 2.6+ **or** Python 3.x (auto-detected)
- `/dev/fb0` or `/dev/fb1` framebuffer device
- Python stdlib: `struct` `zlib` `threading` `fcntl` `io` `json` `subprocess` `zipfile` `socket`

### Optional — dramatically improve quality

| Package | Installed Via | Benefit |
|---|---|---|
| Pillow / PIL | `opkg install python3-pillow` | JPEG output · high-quality PNG |
| Numpy | `opkg install python3-numpy` | 3–5× faster pixel conversion |
| FFmpeg | `opkg install ffmpeg` | H.264 MP4 video recording |

---

## Installation

### One-Line Install (Recommended)

```sh
wget -O /tmp/install.sh https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/install.sh && sh /tmp/install.sh
```

### Manual Install via FTP / USB

```sh
# SSH or Telnet into your STB
cd /tmp
wget https://github.com/SamoTech/E2ScreenRecorder/archive/refs/tags/v1.0.1.tar.gz
tar xzf v1.0.1.tar.gz
cd E2ScreenRecorder-1.0.1
sh install.sh
```

### Install via opkg (when feed is configured)

```sh
opkg update
opkg install enigma2-plugin-extensions-e2screenrecorder
```

### Install Options

```sh
# Auto-restart Enigma2 after install
RESTART_E2=1 sh install.sh

# No internet — use cached opkg packages only
OFFLINE_MODE=1 sh install.sh

# Combined
RESTART_E2=1 OFFLINE_MODE=1 sh install.sh
```

| Variable | Default | Description |
|---|---|---|
| `RESTART_E2` | `0` | Auto-restart Enigma2 after install |
| `OFFLINE_MODE` | `0` | Skip all network operations |

### What the Installer Does

1. Verify root access
2. Detect Enigma2 image (22 known images)
3. Detect Python version (2.6 → 3.12+)
4. Verify all mandatory stdlib modules
5. Check system binaries (`ffmpeg`, `curl`, `wget`)
6. Install Pillow via `opkg` → `pip` (version-matched)
7. Install Numpy via `opkg` → `pip` (optional)
8. Install FFmpeg via `opkg` (optional)
9. Verify filesystem write access
10. Detect active framebuffer (`/dev/fb0` vs `/dev/fb1`)
11. Backup any existing plugin version to `/etc/E2ScreenRecorder.bak/`
12. Deploy plugin files and inject detected config
13. Write `capabilities.json` manifest
14. Verify installation integrity
15. Send OSD notification to running Enigma2
16. Write structured log to `/tmp/e2sr_install.log`

### Verify Install

```sh
# Check install log
cat /tmp/e2sr_install.log

# Check detected capabilities
cat /usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder/capabilities.json

# List the plugin
opkg list-installed | grep e2screenrecorder
```

---

## Uninstallation

```sh
cd /tmp/E2ScreenRecorder-1.0.1
sh uninstall.sh
```

### Uninstall Options

```sh
# Also remove Pillow and Numpy (only if no other plugin uses them)
PRUNE_DEPS=1 sh uninstall.sh

# Remove backups as well
PRUNE_DEPS=0 KEEP_BACKUPS=0 sh uninstall.sh
```

| Variable | Default | Description |
|---|---|---|
| `PRUNE_DEPS` | `0` | Remove Pillow and Numpy via pip/opkg |
| `KEEP_BACKUPS` | `1` | Retain `/etc/E2ScreenRecorder.bak/` |

> ⚠️ Use `PRUNE_DEPS=1` only if no other plugins depend on Pillow or Numpy.

---

## Usage

### Open the Plugin

- **Plugin Menu:** `Menu → Plugins → Screen Recorder`
- **Extensions Menu:** `Blue Button → Screen Recorder`

### Main Menu

```
┌─────────────────────────────────────────────┐
│         E2ScreenRecorder  v1.0.1            │
├─────────────────────────────────────────────┤
│  📷  Take Screenshot (PNG)                  │
│  📷  Take Screenshot (JPEG)                 │
│  📷  Take Screenshot (BMP)                  │
│  🖼   Preview Last Screenshot               │
│  🎥  Start Screen Recording                 │
│  ⏹   Stop Recording                         │
│  📂  Show Captures Folder                   │
│  🌐  Start WebIF Server                     │
│  ⚙️   Settings                               │
│  ❌  Exit                                    │
└─────────────────────────────────────────────┘
```

### Remote Control Keys

| Key | Action |
|---|---|
| `OK` | Select |
| `UP / DOWN` | Navigate |
| `EXIT / BACK` | Close plugin |

### Taking a Screenshot

1. Open plugin from Plugin Menu or Blue Button
2. Select **Take Screenshot (PNG)** or **(JPEG)**
3. File saved instantly to detected storage path
4. OSD notification shows full file path

### Recording Video

1. Open plugin
2. Select **Start Screen Recording**
3. Red `● REC 00:00` counter appears in top-left OSD
4. Close plugin and use Enigma2 normally — recording continues in background
5. Re-open plugin → select **Stop Recording**
6. Video file saved to captures folder automatically

### SSH Commands

```sh
# List saved captures
ls -lh /media/hdd/screenshots/

# Find most recent screenshot
ls -t /media/hdd/screenshots/shot_*.png | head -1

# Check active capability tier
python3 -c "
import json
with open('/usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder/capabilities.json') as f:
    print(json.dumps(json.load(f), indent=2))
"
```

---

## WebIF Remote Control

E2ScreenRecorder includes a built-in HTTP server so you can control the
recorder from **any browser on your LAN** — phone, tablet, or PC.

### Start WebIF

1. Open plugin
2. Select **Start WebIF Server**
3. OSD shows: `WebIF: 192.168.1.x:8765`
4. Open that URL in any browser

Or enable **auto-start** in Settings → WebIF Enabled → YES.

### WebIF Features

- **Live status panel** — recording state + elapsed timer (auto-polls every 2s)
- **One-click screenshot** — PNG / JPEG / BMP selector + Take button
- **Start / Stop recording** buttons
- **Captures list** — all saved files with size, date, download link
- **Dark / Light mode toggle**
- **No external CDN** — entire page served from STB, works offline

### WebIF Screenshot

```
┌──────────────────────────────────────────────┐
│  🎬 E2 Screen Recorder           [↻] [🌙]   │
├──────────────────────────────────────────────┤
│  Status                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   Idle   │  │   —      │  │    4     │  │
│  │Recording │  │ Elapsed  │  │ Captures │  │
│  └──────────┘  └──────────┘  └──────────┘  │
├──────────────────────────────────────────────┤
│  Screenshot   [PNG] [JPEG] [BMP]             │
│               [📷 Take Screenshot]           │
├──────────────────────────────────────────────┤
│  Video        [🎥 Start]  [⏹ Stop]           │
├──────────────────────────────────────────────┤
│  Captures                                    │
│  🖼 shot_20260404_120000.png  1.2MB  ⬇       │
│  🎥 rec_20260404_115500.mp4  48MB   ⬇       │
└──────────────────────────────────────────────┘
```

### WebIF API (for scripts)

```sh
# Status
curl http://STB-IP:8765/api/status

# Take PNG screenshot
curl http://STB-IP:8765/api/screenshot?fmt=PNG

# Start recording
curl http://STB-IP:8765/api/start

# Stop recording
curl http://STB-IP:8765/api/stop

# List captures
curl http://STB-IP:8765/api/captures

# Download a file
curl -O http://STB-IP:8765/download/shot_20260404_120000.png
```

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | WebIF HTML page |
| `/api/status` | GET | JSON: recording state, elapsed, capture count |
| `/api/screenshot?fmt=PNG\|JPEG\|BMP` | GET | Trigger screenshot |
| `/api/start` | GET | Start video recording |
| `/api/stop` | GET | Stop video recording |
| `/api/captures` | GET | JSON list of saved captures |
| `/download/{filename}` | GET | Download a capture file |

---

## Output Formats

### Screenshots

| Format | Extension | Requires | Notes |
|---|---|---|---|
| PNG (built-in) | `.png` | Nothing | Lossless · spec-compliant · always works |
| PNG (fast) | `.png` | Pillow | Faster compression |
| JPEG | `.jpg` | Pillow | Smaller file · configurable quality |
| BMP | `.bmp` | Pillow | Uncompressed · largest |
| PPM | `.ppm` | Nothing | Raw · fallback when Pillow absent |

### Video

| Format | Extension | Requires | Notes |
|---|---|---|---|
| MP4 H.264 | `.mp4` | FFmpeg | Best quality · seekable · recommended |
| AVI / MKV | `.avi` `.mkv` | FFmpeg | Alternative containers |
| PNG frames | `_frames.zip` | Pillow | Lossless frame archive fallback |
| PPM frames | `_frames.zip` | Nothing | Raw frame archive · last resort |

---

## Storage Locations

Plugin auto-selects the first writable path in priority order:

| Priority | Path | Condition |
|---|---|---|
| 1st | `/media/hdd/screenshots/` | External HDD mounted |
| 2nd | `/media/usb/screenshots/` | USB drive mounted |
| 3rd | `/media/mmc/screenshots/` | SD/MMC card mounted |
| 4th | `/tmp/screenshots/` | Fallback — always available |

Directories are created automatically if they don't exist. 
Free space is checked before every capture; if < 50 MB the next priority path is tried.

---

## Capability Tiers

Plugin auto-detects available dependencies and announces active tier via OSD on first run:

```
Tier 1 — FULL     Pillow + Numpy + FFmpeg
  Screenshots:  PNG, JPEG, BMP
  Video:        MP4 H.264
  Conversion:   Numpy-accelerated (fastest)

Tier 2 — STANDARD Pillow only
  Screenshots:  PNG, JPEG, BMP
  Video:        ZIP of PNG frames
  Conversion:   Pillow-accelerated

Tier 3 — BASIC    No optional deps
  Screenshots:  PNG (built-in encoder), PPM
  Video:        ZIP of PPM frames
  Conversion:   Pure Python (slower on 1080p+)

Tier 4 — MINIMAL  Python 2.6 / extreme low-end
  Screenshots:  PPM only
  Video:        ZIP of PPM frames
  Conversion:   Pure Python
```

Active tier is logged in `capabilities.json` under `"mode"`.

---

## Dependency Matrix

| Capability | No Deps | + Pillow | + Numpy | + FFmpeg |
|---|---|---|---|---|
| PNG screenshot | ✅ | ✅ faster | ✅ fastest | ✅ |
| JPEG screenshot | ⚠️ → PPM | ✅ | ✅ | ✅ |
| BMP screenshot | ⚠️ → PPM | ✅ | ✅ | ✅ |
| Video MP4 | ❌ | ❌ | ❌ | ✅ |
| Video ZIP-PNG | ✅ | ✅ | ✅ | ✅ |
| Pixel conversion | ✅ slow | ✅ | ✅ 3–5× | ✅ |
| HiSilicon fb1 | ✅ | ✅ | ✅ | ✅ |
| WebIF server | ✅ | ✅ | ✅ | ✅ |

---

## Configuration

### Settings Screen (in-plugin)

Open plugin → **Settings**:

| Setting | Options | Default |
|---|---|---|
| Screenshot Format | PNG / JPEG / BMP / PPM | PNG |
| JPEG Quality | 10 – 100 | 85 |
| Video FPS | 1 / 2 / 5 / 10 / 15 / 25 | 5 |
| Video Format | mp4 / avi / mkv / ts | mp4 |
| Framebuffer Device | auto / /dev/fb0 / /dev/fb1 | auto |
| Low RAM Mode | Yes / No | No |
| WebIF Enabled | Yes / No | Yes |
| WebIF Port | 1024 – 65535 | 8765 |
| Show REC OSD | Yes / No | Yes |

### Low RAM Mode

Enable this on devices with ≤128 MB RAM (e.g. DM800se, VU+ Solo).
It caps the in-memory frame ring buffer to 30 frames (~6 MB), preventing OOM
on long recordings. Only the last 30 frames are included in the output.

```
Settings → Low RAM Mode → Yes
```

### Manual Config File

```sh
nano /usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder/config/device.conf
```

```ini
FB_DEVICE=/dev/fb0
# Set to /dev/fb1 for HiSilicon devices if auto-detection fails
```

---

## Troubleshooting

### Plugin not visible in menu after install

```sh
killall -HUP enigma2
# Or:
RESTART_E2=1 sh install.sh
```

### Screenshots are completely black / all zeros

```sh
# You have a HiSilicon device — switch to fb1
echo "FB_DEVICE=/dev/fb1" > \
  /usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder/config/device.conf
```

Or: open plugin → **Settings** → Framebuffer Device → `/dev/fb1`

### JPEG saves as PPM instead

```sh
opkg install python3-pillow
# Or via pip:
pip3 install Pillow
```

### Video recording produces empty or missing file

```sh
# Install FFmpeg
opkg install ffmpeg
# Check /tmp free space (need at least 50MB)
df -h /tmp
# Check logs
cat /tmp/E2ScreenRecorder.log | tail -50
```

### Install fails: `/usr` is read-only

```sh
mount -o remount,rw /usr && sh install.sh
```

### WebIF page unreachable from browser

```sh
# Check plugin is running and WebIF started
cat /tmp/E2ScreenRecorder.log | grep WebIF
# Check port is listening
netstat -tlnp | grep 8765
# Try different port (Settings → WebIF Port)
```

### Check all logs at once

```sh
cat /tmp/E2ScreenRecorder.log
cat /tmp/e2sr_install.log
```

---

## Architecture

```
Plugin loads
    │
    ├─► ScreenRecorderPlugin.py   (Enigma2 Screen — main thread only)
    │       │
    │       ├─► core/framebuffer.py    ← ioctl /dev/fb0|fb1, yoffset, chunked read
    │       ├─► core/converter.py     ← 32bpp/16bpp/8bpp → RGB24 (Numpy or pure-Python)
    │       ├─► core/encoder.py       ← dispatches to best available backend
    │       │       ├─► backends/GrabberPIL.py     (Pillow — preferred)
    │       │       ├─► backends/GrabberOpenCV.py  (cv2 — optional)
    │       │       └─► backends/GrabberPPM.py     (zero deps — always available)
    │       │
    │       ├─► core/recorder.py      ← daemon thread, ring buffer, mux via FFmpeg
    │       │       ├─► backends/GrabberFFmpeg.py    (MP4 mux)
    │       │       └─► backends/GrabberGstreamer.py (native E2 — optional)
    │       │
    │       ├─► core/storage.py       ← auto-detects /media/hdd|usb|mmc|/tmp
    │       └─► webif/server.py       ← stdlib HTTP server, daemon thread
    │               └─► _WEBIF_HTML   ← single-file SPA (no external CDN)
    │
    └─► ui/SettingsScreen.py          ← ConfigScreen (persistent settings)
```

**Core guarantees:**

- All UI calls stay in the Enigma2 main thread — `eTimer` drives the REC indicator
- All I/O (framebuffer read, file write, HTTP server) runs in daemon threads
- Every external import is inside `try/except ImportError` — loads on any image
- HiSilicon blank-frame detection at `open()` time — auto-falls back to `/dev/fb1`
- Ring buffer caps memory to 30 frames on low-RAM devices
- WebIF is a zero-dependency embedded HTTP server — no network required beyond LAN

---

## Changelog

### v1.0.1 — Post-Audit Release (2026-04-04)

**20 fixes applied following 5-phase code audit. All 37 test cases now passing.**

- `FIX-001` `core/framebuffer.py` — Chunked framebuffer read; handles partial reads on MIPS kernels
- `FIX-002` `core/framebuffer.py` — yoffset double-buffer seek; correct page captured on DM7020HDv2
- `FIX-003` `core/framebuffer.py` — Context manager (`__enter__`/`__exit__`); fd leak eliminated
- `FIX-004` `core/framebuffer.py` — HiSilicon blank-frame auto-detection; falls back to `/dev/fb1`
- `FIX-005` `core/converter.py` — CLUT8 palette via `FBIOGET_CMAP` ioctl with greyscale fallback
- `FIX-006` `backends/GrabberPPM.py` — PNG chunk CRC uses `& 0xFFFFFFFF`; Python 2 bytes fix
- `FIX-007` `backends/GrabberPPM.py` — PNG IHDR `struct.pack` uses `b">"` prefix; correct on all arches
- `FIX-008` `ScreenRecorderPlugin.py` — eTimer callback catches both `AttributeError` and `TypeError`
- `FIX-009` `core/recorder.py` — `finally` block guarantees tmp_dir cleanup and fd close
- `FIX-010` `core/recorder.py` — Frame ring buffer capped at 30 when `low_ram=True`; prevents OOM
- `FIX-011` `backends/GrabberFFmpeg.py` — FFmpeg search paths extended to include `/opt/bin/ffmpeg`
- `FIX-012` `core/storage.py` — Mount detection uses `isdir` fallback; works on overlayfs images
- `FIX-013` `core/storage.py` — `write_metadata()` method added; no more `AttributeError`
- `FIX-014` `core/storage.py` — `list_captures()` method added; WebIF `/api/captures` now works
- `FIX-015` `webif/server.py` — CORS headers added to file download route
- `FIX-016` `core/converter.py` — `np.clip()` added before `astype(np.uint8)`; prevents silent wrap
- `FIX-017` `ScreenRecorderPlugin.py` — `int(cfg.video_fps.value)` cast; prevents `TypeError` on start
- `FIX-018` `build.sh` — Python one-liner replaces `sed` for BusyBox sh compatibility
- `FIX-019` `core/compat.py` — `makedirs_safe()` added; works on Python 2 without `exist_ok`
- `FIX-020` `webif/server.py` — `allow_reuse_address=True`; prevents port-in-use on plugin reload

**MINOR fixes also applied in v1.0.1:**
- Log rotation via `RotatingFileHandler` (512 KB × 2 backups)
- Pillow 10+ `Image.frombuffer` compatibility
- `cv2.imencode` return value checked
- Locale `.po` compiled to `.mo` in `build.sh`
- `plugin.png` icon added to source tree
- `FFmpegRecorder.binary` property exposed
- `FrameRecorder.elapsed()` method added
- `compat.__all__` populated

### v1.0.0 — Initial Release (2025-12-01)

- Screenshot: PNG · JPEG · PPM
- Video: MP4 H.264 or ZIP frame archive  
- Auto framebuffer device detection
- Python 2.6–3.12+ single codebase
- 22 Enigma2 images supported
- Full install/uninstall scripts

---

## License

MIT License — Copyright © 2025–2026 SamoTech ([github.com/SamoTech](https://github.com/SamoTech))

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

*Maintained by [SamoTech](https://github.com/SamoTech) · [Report a bug](https://github.com/SamoTech/E2ScreenRecorder/issues) · [Request a feature](https://github.com/SamoTech/E2ScreenRecorder/issues)*
