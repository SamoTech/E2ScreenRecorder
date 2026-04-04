# E2ScreenRecorder

Full-featured Screen Recorder plugin for **all Enigma2 STB devices**.  
Captures `/dev/fb0` framebuffer → PNG / JPEG / BMP screenshots and  
MP4 / AVI / MKV video recordings. Includes a **built-in WebIF** so you  
can control the recorder from any browser on your LAN (phone or PC).

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

### Method 1 — wget direct install (recommended)

```bash
wget -qO- https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/install.sh | bash
```

### Method 2 — Manual copy via SCP

```bash
scp -r E2ScreenRecorder/ \
  root@STB-IP:/usr/lib/enigma2/python/Plugins/Extensions/
```

Then restart Enigma2:
```bash
killall -1 enigma2
```

### Uninstall

```bash
wget -qO- https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/uninstall.sh | bash
```

---

## WebIF

Once the plugin is running, open:

```
http://<STB-IP>:8765/
```

From any browser — works on phone, tablet, or PC.  
Controls: Screenshot (PNG/JPEG/BMP), Start/Stop recording,  
Download captures, live REC timer, dark/light mode toggle.

---

## Per-Image Notes

| Image | Python | Notes |
|---|---|---|
| OpenPLi 9+, OpenATV 7+ | 3.9+ | Full support, install `python3-pillow` for best quality |
| VTi 14, OpenPLi 4 | 2.7 | Works with PPM fallback; install `python-imaging` optionally |
| OpenDreambox OE2.6 | 3.8 | Full support |
| Pure2, Xtrend | 3.6 | Full support |
| OpenBH, OpenSPA | 3.x | Full support |
| All others | any | Stdlib-only fallback always available |

Install optional enhancements (not required):
```bash
opkg install python3-pillow ffmpeg
```

---

## Architecture

```
Plugin loads
    ├─► ScreenRecorderPlugin.py  (E2 Screen, main thread only)
    │       ├─► core/framebuffer.py    ← ioctl /dev/fb0|fb1, yoffset, chunked read
    │       ├─► core/converter.py     ← 32bpp/16bpp/8bpp → RGB24 (Numpy or pure-Python)
    │       ├─► core/encoder.py       ← dispatches to best available backend
    │       │       ├─► backends/GrabberPIL.py    (Pillow/PIL — preferred)
    │       │       ├─► backends/GrabberOpenCV.py (cv2 — optional)
    │       │       └─► backends/GrabberPPM.py    (zero deps — always available)
    │       ├─► core/recorder.py      ← daemon thread, ring buffer, mux via FFmpeg
    │       ├─► core/storage.py       ← auto-detects /media/hdd|usb|mmc|/tmp
    │       └─► webif/server.py       ← stdlib HTTP server, daemon thread
    └─► ui/SettingsScreen.py          (persistent config via Enigma2 ConfigList)
```

---

## Key Design Guarantees

1. **All UI calls** stay in the Enigma2 main thread via `eTimer`
2. **All I/O** (framebuffer, file writes, HTTP server) runs in daemon threads
3. **Every external import** is inside `try/except ImportError` — loads on any image
4. **HiSilicon blank-frame detection** — auto-falls back to `/dev/fb1`
5. **Ring buffer** caps memory to 30 frames on low-RAM devices
6. **WebIF** is a zero-dependency embedded HTTP server with inline SPA HTML

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Blank screenshots | HiSilicon device — plugin auto-detects `/dev/fb1` |
| No video output | FFmpeg not found — ZIP of PNG frames saved as fallback |
| Low RAM crash | Enable *Low RAM Mode* in Settings (ring buffer: 30 frames) |
| WebIF unreachable | Check STB firewall; port 8765 configurable in Settings |
| Logs | `/tmp/E2ScreenRecorder.log` |
