# Contributing to E2ScreenRecorder

Thank you for your interest in contributing. This document explains how
to submit bug reports, propose features, and open pull requests.

## Bug Reports

Open an issue at https://github.com/SamoTech/E2ScreenRecorder/issues

Please include:

1. **Device model** (e.g. DM920 UHD, VU+ Duo4K)
2. **Enigma2 image + version** (e.g. OpenATV 7.2, OpenPLi 12)
3. **Python version** (`python3 --version` or `python --version`)
4. **Plugin version** (from `capabilities.json`)
5. **Log output** (`cat /tmp/E2ScreenRecorder.log`)
6. **Steps to reproduce**
7. **Expected vs actual behaviour**

## Pull Requests

### Code Style

- Use `from __future__ import absolute_import, print_function, division` at top of every file
- All imports of optional packages inside `try/except ImportError`
- No f-strings (use `.format()`) — Python 2.6 compatibility required
- No walrus operator, no `match`, no positional-only params
- All file I/O via `io.open()` with explicit `encoding=`
- `struct` format strings with explicit endian prefix (`<I`, `>H`, `=B`)
- All UI callbacks must execute in the Enigma2 main thread (use `eTimer` or `reactor.callLater`)

### Testing Checklist

Before opening a PR, test on at minimum:

- [ ] Python 2.7 (OpenMIPS or VTi 14 image)
- [ ] Python 3.8+ (OpenATV 7 or OpenPLi 10+)
- [ ] Device with zero optional deps (Pillow/Numpy/FFmpeg all absent)
- [ ] Device with all deps present

### Adding a New Backend

1. Create `backends/GrabberXxx.py`
2. Implement `is_available()` classmethod
3. Implement `save_xxx(rgb24, width, height, path)` or equivalent
4. Register in `core/encoder.py` dispatcher
5. Wrap all imports in `try/except ImportError`
6. Add row to Dependency Matrix in README.md

## Licence

By contributing you agree that your contribution will be licensed under
the MIT License that covers this project.
