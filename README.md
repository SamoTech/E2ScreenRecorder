# E2ScreenRecorder

> **Full-featured Screen Recorder plugin for all Enigma2 STB devices.**  
> Author: [Ossama Hashim](mailto:samo.hossam@gmail.com) | [SamoTech](https://github.com/SamoTech)

Captures `/dev/fb0` framebuffer → **PNG / JPEG / BMP** screenshots and **MP4 / AVI / MKV** video recordings.  
Includes a **built-in WebIF** — control everything from any browser on your LAN (phone or PC).

---

## Features

| Feature | Detail |
|---|---|
| Screenshots | PNG (lossless), JPEG (configurable quality), BMP, PPM |
| Video | MP4 via FFmpeg, AVI/MKV, frame-zip fallback |
| WebIF | Full control page at `http://STB-IP:8765/` |
| Framebuffer | ARGB8888, RGBA8888, RGB565, BGR888, CLUT8, all bpp |
| RAM safety | Ring-buffer mode for ≤256 MB devices |
| HiSilicon | Auto-detects blank `/dev/fb0` → tries `/dev/fb1` |
| Python compat | 2.7 – 3.12+ unified codebase |
| Dependencies | **Zero mandatory** — stdlib-only fallback always works |

---

## Installation

### Method 1 — opkg (recommended)

```bash
opkg update
opkg install enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk
```

### Method 2 — SCP + opkg

```bash
# From your PC:
scp enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk root@<STB-IP>:/tmp/

# On the STB:
opkg install /tmp/enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk
```

### Method 3 — Manual copy (no ipk)

```bash
scp -r E2ScreenRecorder/ \
  root@<STB-IP>:/usr/lib/enigma2/python/Plugins/Extensions/

# Restart Enigma2:
ssh root@<STB-IP> 'killall -1 enigma2'
```

---

## Build from Source

**Requirements:** `fakeroot`, `dpkg-deb`

```bash
# Install build deps (Debian/Ubuntu)
apt install fakeroot dpkg

# Clone the repo
git clone https://github.com/SamoTech/E2ScreenRecorder.git
cd E2ScreenRecorder

# Build default version (1.0.0)
bash build.sh

# Build a custom version
bash build.sh 1.2.0
```

Output: `enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk`

---

## WebIF

Once the plugin is running on the STB, open in any browser:

```
http://<STB-IP>:8765/
```

Available controls:
- 📷 Screenshot (PNG / JPEG / BMP)
- 🎥 Start / Stop recording
- ⬇ Download captures
- Live REC timer
- Dark / light mode toggle

The WebIF port (default `8765`) is configurable via **Settings** inside the plugin.

---

## Per-Image Compatibility

| Image | Python | Notes |
|---|---|---|
| OpenPLi 9+, OpenATV 7+ | 3.9+ | Full support — install `python3-pillow` for best quality |
| VTi 14, OpenPLi 4 | 2.7 | Works with PPM fallback; install `python-imaging` optionally |
| OpenDreambox OE2.6 | 3.8 | Full support |
| Pure2, Xtrend ET10000 | 3.6 | Full support |
| OpenBH, OpenSPA | 3.x | Full support |
| All others | any | Stdlib-only fallback always available |

Install optional enhancements (not required):

```bash
opkg install python3-pillow ffmpeg
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Blank / black screenshots | HiSilicon device — plugin auto-detects `/dev/fb1` |
| No video output | FFmpeg not found; ZIP of PNG frames saved as fallback |
| Low RAM crash | Enable **Low RAM Mode** in Settings (ring buffer: 30 frames max) |
| WebIF unreachable | Check STB firewall; change port in Settings if needed |
| Plugin not visible | Restart Enigma2: `killall -1 enigma2` |

Logs: `/tmp/E2ScreenRecorder.log`

---

## License

MIT © [Ossama Hashim](mailto:samo.hossam@gmail.com)
