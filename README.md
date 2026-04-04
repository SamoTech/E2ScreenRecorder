# E2ScreenRecorder

> **Full-featured Screen Recorder plugin for all Enigma2 STB devices.**  
> Author: [Ossama Hashim](mailto:samo.hossam@gmail.com) &nbsp;|&nbsp; [SamoTech](https://github.com/SamoTech)

Captures `/dev/fb0` framebuffer → **PNG / JPEG / BMP** screenshots and **MP4 / AVI / MKV** video recordings.  
Includes a **built-in WebIF** — control everything from any browser on your LAN (phone or PC).  
**No ipk. No deb. One command installs everything.**

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

## Install

Run this **one command** on the STB (no ipk / no deb required):

```sh
wget -q "--no-check-certificate" https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/install.sh -O - | sh
```

Then restart Enigma2:

```sh
killall -1 enigma2
```

---

## Uninstall

```sh
wget -q "--no-check-certificate" https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/uninstall.sh -O - | sh
```

Then restart Enigma2:

```sh
killall -1 enigma2
```

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

Optional enhancements (not required):

```sh
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
