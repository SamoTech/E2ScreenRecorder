# Changelog

All notable changes to E2ScreenRecorder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.2] — 2026-04-04  Recording Stop-After-1s Hotfix

### Fixed — Critical

- **FIX-021** `core/recorder.py` `run()` — Added `_open_fb()` method called
  inside the recording thread so HiSilicon `/dev/fb1` blank-frame detection
  and fallback are applied per-thread, right before the capture loop starts.
  Previously the device was selected at plugin open time, causing Strategy 1
  (FFmpeg rawvideo) to read from the wrong framebuffer device and produce
  an all-black output that FFmpeg immediately discarded, making the recording
  appear to stop after exactly 1 second.

- **FIX-022** `core/recorder.py` `_run_frame_dump()` — Replaced `time.sleep()`
  with `self._stop_event.wait(delay)` in the capture loop interruptible sleep.
  `time.sleep()` blocks the thread for a full frame interval (0.2 s at 5 fps)
  after `stop()` is called, causing the thread to exit its loop one frame late
  and then enter mux with zero frames captured when recording was very short.
  `wait()` wakes immediately when `stop()` fires.

- **FIX-023** `core/recorder.py` — `makedirs_safe()` (from `compat.py`) now
  applied on ALL three strategy code paths (`_try_grab_pipe`, `_run_frame_dump`).
  Strategy 2 and 3 were still using bare `os.makedirs()`, which raises `OSError`
  on Python 2 if the directory already exists (e.g. rapid stop/start cycle),
  killing the thread silently before a single frame was written.

- **FIX-024** `core/recorder.py` `run()` — `on_error` callback now receives
  `"{ExceptionType}: {message}"` instead of bare `str(e)`. Matches what
  `ScreenRecorderPlugin._on_record_error()` logs; makes silent failures
  visible in the OSD status label and in `/tmp/E2ScreenRecorder.log`.

### Improved

- **IMPROVE-001** `core/recorder.py` `_mux_frames()` — FFmpeg stderr now
  redirected to `/tmp/ffmpeg_e2rec.log` (loglevel `warning`) instead of
  being discarded. Enables post-mortem diagnosis of mux failures without
  any UI change.

---

## [1.0.1] — 2026-04-04  Post-Audit Release

### Fixed — Critical

- **FIX-001** `core/framebuffer.py` `capture_raw()` — Chunked read loop (65536-byte blocks) prevents `struct.error` partial reads on MIPS Python 2 kernels. Affects DM800se, VU+ Solo2, OpenMIPS.
- **FIX-002** `core/framebuffer.py` `capture_raw()` — `yoffset` double-buffer seek. `os.lseek(fd, yoffset * stride, SEEK_SET)` before read. Fixes wrong-page capture on DM7020HDv2 and other double-buffered STBs.
- **FIX-006** `backends/GrabberPPM.py` `save_png()` — PNG CRC bytes/str concat `TypeError` on Python 2 fixed. All tag literals use explicit `b""` prefix. `zlib.crc32() & 0xFFFFFFFF` mask applied.
- **FIX-007** `backends/GrabberPPM.py` `save_png()` — PNG IHDR `struct.pack` format changed to `b">IIBBBBB"`. `struct.calcsize == 13` verified on all platforms. Eliminates invalid PNG output on some ARM devices.
- **FIX-010** `core/recorder.py` `FrameRecorder.run()` — Frame ring buffer capped at 30 frames when `low_ram=True`. Prevents OOM crash on 128 MB RAM devices (DM800se, VU+ Solo).

### Fixed — Major

- **FIX-003** `core/framebuffer.py` — Added `__enter__`/`__exit__` context manager protocol. File descriptor now guaranteed closed on exception via `with FramebufferCapture() as fb:` pattern.
- **FIX-004** `core/framebuffer.py` `open()` — HiSilicon blank-frame auto-detection. Reads first 256 bytes; if all-zero and `/dev/fb1` exists, automatically switches device. Fixes silent all-black screenshots on AB PULSe 4K, AX HD51, Mut@nt HD51.
- **FIX-012** `core/storage.py` `_get_base()` — Mount detection changed from `os.path.ismount()` alone to `ismount() OR isdir()` with write-access verification. Fixes HDD path always skipped on overlayfs images (OpenATV 7, OpenPLi 12).
- **FIX-013** `core/storage.py` — Added `write_metadata(path, info_dict)`. Eliminates `AttributeError` crash in `ScreenRecorderPlugin._take_screenshot()`.
- **FIX-014** `core/storage.py` — Added `list_captures()`. Eliminates `AttributeError` crash in WebIF `/api/captures` endpoint.
- **FIX-017** `ScreenRecorderPlugin.py` `_start_recording()` — `int(cfg.video_fps.value)` cast applied. `ConfigSelection` returns `str`; passing to `FrameRecorder` without cast caused `TypeError: unsupported operand type(s) for /`.
- **FIX-019** `core/compat.py` — Added `makedirs_safe()` shim. Replaces all `os.makedirs()` calls; compatible with Python 2 (no `exist_ok` kwarg). Prevents `OSError` on rapid stop/start cycles.
- **FIX-020** `webif/server.py` `WebIFServer` — `_ReuseHTTPServer` subclass sets `allow_reuse_address = True`. Prevents "Address already in use" `OSError` on plugin reload without full Enigma2 restart.

### Fixed — Minor (applied in v1.0.1)

- **FIX-008** eTimer callback binding catches both `AttributeError` and `TypeError` (covers all known E2 image variants).
- **FIX-009** `core/recorder.py` `run()` — `finally` block guarantees `tmp_dir` cleanup and `fb.close()` on all exit paths.
- **FIX-011** `backends/GrabberFFmpeg.py` — FFmpeg search paths extended: adds `/opt/bin/ffmpeg`, `/usr/share/ffmpeg/ffmpeg`, `/bin/ffmpeg`. Covers OpenBH, EGAMI, and other non-standard FFmpeg installations.
- **FIX-015** `webif/server.py` — CORS headers (`Access-Control-Allow-Origin: *`) added to file download route.
- **FIX-016** `core/converter.py` — `np.clip()` applied before `astype(np.uint8)` in Numpy 32bpp path. Prevents silent value wrap on HiSilicon devices with non-standard `red_len` values.
- **FIX-018** `build.sh` — `sed -i` replaced with Python one-liner for BusyBox `sh`/`ash` compatibility on embedded build hosts.
- **MINOR-001** Log rotation via `RotatingFileHandler` (512 KB × 2 backups). Prevents `/tmp` exhaustion on long-running devices.
- **MINOR-002** `utils/notify.py` — `Screens.MessageBox` fallback added for images where `AddNotificationPopup` path differs.
- **MINOR-003** Pillow 10+ compatibility: `Image.frombytes()` → `Image.frombuffer()` with explicit `"raw"` decoder.
- **MINOR-004** `backends/GrabberOpenCV.py` — `cv2.imencode()` return value checked; raises `RuntimeError` on failure.
- **MINOR-006** `core/compat.py` — `__all__` populated with all exported names.
- **MINOR-007** `build.sh` — `msgfmt` call added to compile `.po` → `.mo` for Arabic locale.
- **MINOR-008** `plugin.png` 48×48 icon added to source tree.
- **MINOR-009** `backends/GrabberFFmpeg.py` `stop()` — Misleading `stdin.write(b"q")` removed; `terminate()` is the correct and only stop mechanism for rawvideo `/dev/fb0` input.
- **MINOR-011** `backends/GrabberFFmpeg.py` — `binary` property exposed; `recorder.py` uses `ffr.binary` instead of `ffr._binary`.
- **MINOR-013** `core/recorder.py` — `elapsed()` method added to `FrameRecorder`; used by WebIF `/api/status`.

### Deferred to v1.1.0

- MINOR-005: WebIF request timeout
- MINOR-010: `list_captures()` sort by mtime
- MINOR-012: WebIF dark mode persistence across reload

---

## [1.0.0] — 2025-12-01  Initial Release

### Added

- Screenshot capture: PNG (built-in encoder), JPEG (Pillow), PPM (fallback)
- Video recording: MP4 H.264 via FFmpeg; ZIP frame archive fallback
- Framebuffer capture: ARGB8888, RGBA8888, RGB565, CLUT8 pixel formats
- Auto framebuffer device detection (`/dev/fb0` primary)
- Enigma2 OSD screen with live `● REC MM:SS` indicator
- Background daemon thread for video recording
- Smart storage path selection: HDD → USB → MMC → `/tmp`
- Python 2.6–3.12+ unified codebase with `compat.py` shims
- Numpy acceleration with pure Python fallback
- 22 Enigma2 images identified and tested
- `install.sh` with dependency auto-detection and installation
- `uninstall.sh` with optional dep pruning
- Arabic locale (`ar`) translation strings
- ipk package builder (`build.sh`)
- `meta/plugin.xml` and `CONTROL/control` package descriptor
