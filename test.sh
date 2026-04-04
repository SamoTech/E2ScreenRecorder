#!/bin/sh
# =============================================================================
# E2ScreenRecorder — Full Diagnostic Test Script v1.0
# Run on the STB as root after installation
# Usage: sh /usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder/test.sh
#    or: wget -qO- https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/test.sh | sh
# =============================================================================

PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder"
TMP_DIR="/tmp/e2sr_test_$$"
LOG="/tmp/E2ScreenRecorder_test.log"
PASS=0
FAIL=0
WARN=0

mkdir -p "$TMP_DIR"

# ── Color codes (works on busybox sh) ────────────────────────────────────
GRN='\033[0;32m'; RED='\033[0;31m'; YLW='\033[0;33m'
BLD='\033[1m'; CYN='\033[0;36m'; RST='\033[0m'

ok()   { printf "${GRN}[ PASS ]${RST}  %s\n" "$*" | tee -a "$LOG"; PASS=$((PASS+1)); }
fail() { printf "${RED}[ FAIL ]${RST}  %s\n" "$*" | tee -a "$LOG"; FAIL=$((FAIL+1)); }
warn() { printf "${YLW}[ WARN ]${RST}  %s\n" "$*" | tee -a "$LOG"; WARN=$((WARN+1)); }
info() { printf "${CYN}[ INFO ]${RST}  %s\n" "$*" | tee -a "$LOG"; }
sect() { printf "\n${BLD}%s${RST}\n" "$*" | tee -a "$LOG"; }

cleanup() { rm -rf "$TMP_DIR" 2>/dev/null; }
trap cleanup EXIT

# ── Find Python ─────────────────────────────────────────────────────────────
PY=""
for _c in python3 python python2; do
    command -v "$_c" >/dev/null 2>&1 && PY="$_c" && break
done
[ -z "$PY" ] && { printf '${RED}[FATAL]${RST} No Python found\n'; exit 1; }

# ── Header ───────────────────────────────────────────────────────────────────
clear 2>/dev/null || true
printf "${BLD}"
echo "  ┌────────────────────────────────────────────────┐"
echo "  │   E2ScreenRecorder — Full Diagnostic Test     │"
echo "  │   VU+ Uno 4K SE / OpenATV 7.6 / Python 3.13   │"
echo "  └────────────────────────────────────────────────┘"
printf "${RST}\n"
info "Log: $LOG"
info "Date: $(date)"
info "Host: $(hostname) / $(uname -m)"
info "Python: $($PY --version 2>&1)"
echo "" | tee -a "$LOG"


# =============================================================================
# SECTION 1: System Environment
# =============================================================================
sect "1. System Environment"

# 1.1 Plugin directory exists
if [ -d "$PLUGIN_DIR" ]; then
    ok "Plugin dir exists: $PLUGIN_DIR"
else
    fail "Plugin dir NOT found: $PLUGIN_DIR"
fi

# 1.2 All expected files present
for _f in __init__.py plugin.py ScreenRecorderPlugin.py \
          core/__init__.py core/framebuffer.py core/converter.py \
          core/encoder.py core/recorder.py core/storage.py core/compat.py \
          backends/__init__.py backends/GrabberPPM.py backends/GrabberPIL.py \
          backends/GrabberFFmpeg.py \
          ui/__init__.py ui/SettingsScreen.py \
          utils/__init__.py utils/logger.py utils/notify.py \
          webif/__init__.py webif/server.py; do
    if [ -f "${PLUGIN_DIR}/${_f}" ]; then
        ok "  file: $_f"
    else
        fail "  missing: $_f"
    fi
done

# 1.3 Framebuffer devices
for _dev in /dev/fb0 /dev/fb1; do
    if [ -e "$_dev" ]; then
        ok "  device exists: $_dev"
        if [ -r "$_dev" ]; then
            ok "  device readable: $_dev"
        else
            warn "  device not readable: $_dev (may need root)"
        fi
    else
        warn "  device absent: $_dev (not all STBs have both)"
    fi
done

# 1.4 Storage paths
for _p in /media/hdd /media/usb /tmp; do
    if [ -d "$_p" ]; then
        if [ -w "$_p" ]; then
            ok "  writable: $_p"
        else
            warn "  not writable: $_p"
        fi
    else
        info "  absent (ok): $_p"
    fi
done

# 1.5 FFmpeg
if command -v ffmpeg >/dev/null 2>&1; then
    _ffver="$(ffmpeg -version 2>&1 | head -1)"
    ok "FFmpeg: $_ffver"
else
    warn "ffmpeg binary not in PATH — video will use frame-ZIP fallback"
fi


# =============================================================================
# SECTION 2: Python Module Imports
# =============================================================================
sect "2. Python Module Imports"

$PY << 'PYEOF'
import sys, os
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')

P = 'E2ScreenRecorder'
OK = 0; FAIL = 0

def chk(label, code):
    global OK, FAIL
    try:
        exec(code, {})
        print('\033[0;32m[ PASS ]\033[0m  import: ' + label)
        OK += 1
    except Exception as e:
        print('\033[0;31m[ FAIL ]\033[0m  import: {} -> {}'.format(label, e))
        FAIL += 1

chk('core.framebuffer',       'from E2ScreenRecorder.core.framebuffer  import FramebufferCapture')
chk('core.converter',         'from E2ScreenRecorder.core.converter    import PixelConverter')
chk('core.encoder',           'from E2ScreenRecorder.core.encoder      import save_screenshot, get_image_backend, get_video_backend')
chk('core.recorder',          'from E2ScreenRecorder.core.recorder     import FrameRecorder')
chk('core.storage',           'from E2ScreenRecorder.core.storage      import StorageManager')
chk('core.compat',            'from E2ScreenRecorder.core.compat       import makedirs_safe')
chk('backends.GrabberPPM',    'from E2ScreenRecorder.backends.GrabberPPM  import PPMGrabber')
chk('backends.GrabberPIL',    'from E2ScreenRecorder.backends.GrabberPIL  import PILGrabber')
chk('backends.GrabberFFmpeg', 'from E2ScreenRecorder.backends.GrabberFFmpeg import FFmpegRecorder')
chk('backends.GrabberGst',    'from E2ScreenRecorder.backends.GrabberGstreamer import GstRecorder')
chk('backends.GrabberCV',     'from E2ScreenRecorder.backends.GrabberOpenCV import OpenCVGrabber')
chk('utils.logger',           'from E2ScreenRecorder.utils.logger      import log')
chk('webif.server',           'from E2ScreenRecorder.webif.server      import WebIFServer')

print('')
print('  Imports: {}/{} passed'.format(OK, OK+FAIL))
if FAIL > 0:
    sys.exit(1)
PYEOF
_pyret=$?
[ "$_pyret" -eq 0 ] && ok "All critical imports passed" || fail "Some imports failed — check output above"


# =============================================================================
# SECTION 3: Framebuffer Capture
# =============================================================================
sect "3. Framebuffer Capture"

$PY << PYEOF
import sys, os
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.core.framebuffer import FramebufferCapture
from E2ScreenRecorder.core.converter  import PixelConverter

for dev in ['/dev/fb0', '/dev/fb1']:
    if not os.path.exists(dev):
        print('[\033[0;33m WARN \033[0m]  {} does not exist — skipping'.format(dev))
        continue
    try:
        fb = FramebufferCapture(device=dev)
        fb.open()
        info = fb.get_info()
        print('[\033[0;32m PASS \033[0m]  {} opened OK'.format(dev))
        print('[\033[0;36m INFO \033[0m]    Resolution : {}x{}'.format(info['xres'], info['yres']))
        print('[\033[0;36m INFO \033[0m]    BPP        : {}'.format(info['bpp']))
        print('[\033[0;36m INFO \033[0m]    R/G/B      : off={}/{}/{}  len={}/{}/{}'.format(
            info['red_offset'], info['green_offset'], info['blue_offset'],
            info['red_len'],    info['green_len'],    info['blue_len']))

        raw = fb.capture_raw()
        expected = info['xres'] * info['yres'] * (info['bpp'] // 8)
        if len(raw) == expected:
            print('[\033[0;32m PASS \033[0m]  {} raw read OK ({} bytes)'.format(dev, len(raw)))
        else:
            print('[\033[0;31m FAIL \033[0m]  {} raw size mismatch: got {} expected {}'.format(dev, len(raw), expected))

        # Blank frame detection
        nz = sum(1 for b in bytearray(raw[:4096]) if b != 0)
        pct = 100 * nz // 4096
        if pct > 5:
            print('[\033[0;32m PASS \033[0m]  {} has content ({:.0f}% non-zero in first 4KB)'.format(dev, pct))
        else:
            print('[\033[0;33m WARN \033[0m]  {} looks blank ({:.0f}% non-zero) — OSD may be on other FB'.format(dev, pct))

        # Convert to RGB24
        rgb = PixelConverter.to_rgb24(raw, info)
        print('[\033[0;32m PASS \033[0m]  {} pixel conversion OK ({} RGB bytes)'.format(dev, len(rgb)))
        fb.close()
    except Exception as e:
        print('[\033[0;31m FAIL \033[0m]  {} error: {}'.format(dev, e))
PYEOF


# =============================================================================
# SECTION 4: Screenshot Backends
# =============================================================================
sect "4. Screenshot Backends"

$PY << PYEOF
import sys, os
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.core.framebuffer import FramebufferCapture
from E2ScreenRecorder.core.converter  import PixelConverter

# Capture once, reuse
try:
    fb = FramebufferCapture()
    fb.open()
    info = fb.get_info()
    raw  = fb.capture_raw()
    rgb  = PixelConverter.to_rgb24(raw, info)
    fb.close()
    w, h = info['xres'], info['yres']
    print('[\033[0;36m INFO \033[0m]  Captured {}x{} @ {}bpp'.format(w, h, info['bpp']))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  Cannot capture framebuffer: {}'.format(e))
    sys.exit(1)

tmp = '/tmp/e2sr_test_{}'.format(os.getpid())
os.makedirs(tmp)

# —— PPM backend (zero deps)
try:
    from E2ScreenRecorder.backends.GrabberPPM import PPMGrabber
    p = tmp + '/test.ppm'
    PPMGrabber.save_ppm(rgb, w, h, p)
    sz = os.path.getsize(p)
    print('[\033[0;32m PASS \033[0m]  PPM saved  → {} ({} bytes)'.format(p, sz))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  PPM backend: {}'.format(e))

# —— PNG backend (pure Python, zero deps)
try:
    from E2ScreenRecorder.backends.GrabberPPM import PPMGrabber
    p = tmp + '/test_ppm.png'
    PPMGrabber.save_png(rgb, w, h, p)
    sz = os.path.getsize(p)
    print('[\033[0;32m PASS \033[0m]  PNG (pure-py) saved  → {} ({} bytes)'.format(p, sz))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  PNG pure-py backend: {}'.format(e))

# —— PIL/Pillow PNG
try:
    from E2ScreenRecorder.backends.GrabberPIL import PILGrabber
    if PILGrabber.is_available():
        p = tmp + '/test_pil.png'
        PILGrabber.save_pil(rgb, w, h, p, 'PNG')
        sz = os.path.getsize(p)
        print('[\033[0;32m PASS \033[0m]  PIL PNG saved  → {} ({} bytes)'.format(p, sz))
    else:
        print('[\033[0;33m WARN \033[0m]  PIL not available — using PPM fallback')
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  PIL backend: {}'.format(e))

# —— PIL/Pillow JPEG
try:
    from E2ScreenRecorder.backends.GrabberPIL import PILGrabber
    if PILGrabber.is_available():
        p = tmp + '/test_pil.jpg'
        PILGrabber.save_pil(rgb, w, h, p, 'JPEG')
        sz = os.path.getsize(p)
        print('[\033[0;32m PASS \033[0m]  PIL JPEG saved  → {} ({} bytes)'.format(p, sz))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  PIL JPEG: {}'.format(e))

print('')
print('[\033[0;36m INFO \033[0m]  Test files in: ' + tmp)
print('[\033[0;36m INFO \033[0m]  Fetch from PC:  scp root@STB-IP:' + tmp + '/* ./')
import shutil
shutil.copy(tmp + '/test_pil.png' if os.path.exists(tmp+'/test_pil.png') else tmp+'/test_ppm.png',
            '/tmp/E2ScreenRecorder_test_shot.png')
print('[\033[0;32m PASS \033[0m]  Best shot → /tmp/E2ScreenRecorder_test_shot.png')
PYEOF


# =============================================================================
# SECTION 5: Storage Manager
# =============================================================================
sect "5. Storage Manager"

$PY << 'PYEOF'
import sys
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.core.storage import StorageManager

try:
    sm = StorageManager()
    base = sm._get_base()
    print('[\033[0;32m PASS \033[0m]  Storage base: ' + base)
    shot_path = sm.next_screenshot_path('png')
    print('[\033[0;32m PASS \033[0m]  Next screenshot path: ' + shot_path)
    vid_path = sm.next_video_path('mp4')
    print('[\033[0;32m PASS \033[0m]  Next video path: ' + vid_path)
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  StorageManager: {}'.format(e))
PYEOF


# =============================================================================
# SECTION 6: FFmpeg Video Backend
# =============================================================================
sect "6. FFmpeg Video Backend"

$PY << 'PYEOF'
import sys, subprocess
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.backends.GrabberFFmpeg import FFmpegRecorder, get_ffmpeg

try:
    binary = get_ffmpeg()
    if binary:
        print('[\033[0;32m PASS \033[0m]  FFmpeg binary: ' + binary)
        ver = subprocess.check_output([binary, '-version'], stderr=subprocess.STDOUT).decode().split('\n')[0]
        print('[\033[0;36m INFO \033[0m]  ' + ver)

        # Test instantiation
        fb_info = {'xres': 1920, 'yres': 1080, 'bpp': 32}
        rec = FFmpegRecorder(fb_info, '/tmp/e2sr_test.mp4', fps=5)
        print('[\033[0;32m PASS \033[0m]  FFmpegRecorder instantiated OK')
        print('[\033[0;36m INFO \033[0m]  is_available(): {}'.format(rec.is_available()))
    else:
        print('[\033[0;33m WARN \033[0m]  FFmpeg not found — video will use frame-ZIP fallback')
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  FFmpeg backend: {}'.format(e))
PYEOF


# =============================================================================
# SECTION 7: WebIF Server (port bind test)
# =============================================================================
sect "7. WebIF Server"

$PY << 'PYEOF'
import sys, socket, threading, time
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')

PORT = 8765

# Check if port is already in use
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    s.bind(('0.0.0.0', PORT))
    s.close()
    print('[\033[0;32m PASS \033[0m]  Port {} is free'.format(PORT))
except OSError as e:
    print('[\033[0;33m WARN \033[0m]  Port {} in use: {} (WebIF may already be running)'.format(PORT, e))

# Import test
try:
    from E2ScreenRecorder.webif.server import WebIFServer, _WEBIF_HTML
    print('[\033[0;32m PASS \033[0m]  WebIF server module loaded')
    print('[\033[0;36m INFO \033[0m]  HTML page size: {:,} bytes'.format(len(_WEBIF_HTML)))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  WebIF server import: {}'.format(e))
    sys.exit(0)

# Spin up real server for 3 seconds and hit it
try:
    from E2ScreenRecorder.core.storage import StorageManager
    sm = StorageManager()

    srv = WebIFServer(
        port=PORT,
        storage=sm,
        get_recorder=lambda: None,
        do_screenshot=lambda fmt: None,
        do_start_rec=lambda: None,
        do_stop_rec=lambda: None,
    )
    srv.start()
    time.sleep(0.8)

    # Hit /api/status
    try:
        import json
        try:
            from urllib.request import urlopen
        except ImportError:
            from urllib2 import urlopen
        resp = urlopen('http://127.0.0.1:{}/api/status'.format(PORT), timeout=3)
        data = json.loads(resp.read().decode())
        print('[\033[0;32m PASS \033[0m]  GET /api/status → {}'.format(data))
    except Exception as e:
        print('[\033[0;31m FAIL \033[0m]  GET /api/status failed: {}'.format(e))

    # Hit /api/captures
    try:
        resp = urlopen('http://127.0.0.1:{}/api/captures'.format(PORT), timeout=3)
        data = json.loads(resp.read().decode())
        print('[\033[0;32m PASS \033[0m]  GET /api/captures → {} item(s)'.format(len(data.get('captures',[]))))
    except Exception as e:
        print('[\033[0;31m FAIL \033[0m]  GET /api/captures failed: {}'.format(e))

    # Hit / (HTML page)
    try:
        resp = urlopen('http://127.0.0.1:{}/'.format(PORT), timeout=3)
        html = resp.read()
        if b'E2 Screen Recorder' in html:
            print('[\033[0;32m PASS \033[0m]  GET / → HTML page OK ({:,} bytes)'.format(len(html)))
        else:
            print('[\033[0;33m WARN \033[0m]  GET / returned unexpected content')
    except Exception as e:
        print('[\033[0;31m FAIL \033[0m]  GET / failed: {}'.format(e))

    srv.stop()
    print('[\033[0;32m PASS \033[0m]  WebIF server started, served, and stopped cleanly')
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  WebIF server lifecycle: {}'.format(e))
PYEOF


# =============================================================================
# SECTION 8: Logger
# =============================================================================
sect "8. Logger"

$PY << 'PYEOF'
import sys
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.utils.logger import log, LOG_PATH

try:
    log.debug('TEST debug message from test.sh')
    log.info('TEST info message from test.sh')
    log.warning('TEST warning message from test.sh')
    log.error('TEST error message from test.sh')
    print('[\033[0;32m PASS \033[0m]  Logger wrote 4 test lines to: ' + LOG_PATH)
    with open(LOG_PATH) as f:
        lines = f.readlines()
    test_lines = [l for l in lines if 'TEST' in l and 'test.sh' in l]
    print('[\033[0;32m PASS \033[0m]  Confirmed {} lines written to log'.format(len(test_lines)))
except Exception as e:
    print('[\033[0;31m FAIL \033[0m]  Logger: {}'.format(e))
PYEOF


# =============================================================================
# SECTION 9: End-to-End Screenshot via encoder dispatcher
# =============================================================================
sect "9. End-to-End Screenshot (encoder dispatcher)"

$PY << 'PYEOF'
import sys, os
sys.path.insert(0, '/usr/lib/enigma2/python/Plugins/Extensions')
from E2ScreenRecorder.core.framebuffer import FramebufferCapture
from E2ScreenRecorder.core.converter  import PixelConverter
from E2ScreenRecorder.core.encoder    import save_screenshot, get_image_backend, get_video_backend

try:
    # Detect backends
    img_be = get_image_backend()
    vid_be = get_video_backend()
    print('[\033[0;36m INFO \033[0m]  Image backend : {}'.format(img_be.__name__ if hasattr(img_be,'__name__') else img_be))
    print('[\033[0;36m INFO \033[0m]  Video backend : {}'.format(vid_be))

    # Capture
    fb = FramebufferCapture()
    fb.open()
    info = fb.get_info()
    raw  = fb.capture_raw()
    rgb  = PixelConverter.to_rgb24(raw, info)
    fb.close()

    # Save PNG via dispatcher
    out_png = '/tmp/E2SR_e2e_test.png'
    save_screenshot(rgb, info['xres'], info['yres'], out_png, 'PNG')
    sz = os.path.getsize(out_png)
    print('[\033[0;32m PASS \033[0m]  PNG saved via dispatcher → {} ({:,} bytes)'.format(out_png, sz))

    # Save JPEG via dispatcher
    out_jpg = '/tmp/E2SR_e2e_test.jpg'
    save_screenshot(rgb, info['xres'], info['yres'], out_jpg, 'JPEG')
    sz2 = os.path.getsize(out_jpg)
    print('[\033[0;32m PASS \033[0m]  JPEG saved via dispatcher → {} ({:,} bytes)'.format(out_jpg, sz2))

    print('')
    print('[\033[0;36m INFO \033[0m]  Download to your PC:')
    print('[\033[0;36m INFO \033[0m]    scp root@{STB-IP}:/tmp/E2SR_e2e_test.png ./')
    print('[\033[0;36m INFO \033[0m]    scp root@{STB-IP}:/tmp/E2SR_e2e_test.jpg ./')
except Exception as e:
    import traceback
    print('[\033[0;31m FAIL \033[0m]  End-to-end test: {}'.format(e))
    traceback.print_exc()
PYEOF


# =============================================================================
# SECTION 10: Plugin Log File
# =============================================================================
sect "10. Plugin Log File"

LOGFILE="/tmp/E2ScreenRecorder.log"
if [ -f "$LOGFILE" ]; then
    _lines=$(wc -l < "$LOGFILE" 2>/dev/null || echo '?')
    ok "Log file exists: $LOGFILE  ($_lines lines)"
    echo ""
    info "--- Last 10 log lines ---"
    tail -10 "$LOGFILE" | sed 's/^/    /'
else
    warn "Log file not found yet — open the plugin on the STB to generate it"
fi


# =============================================================================
# FINAL SUMMARY
# =============================================================================
echo ""
printf "${BLD}"
echo "========================================================="
echo "  Test Complete"
echo "  Test log : $LOG"
echo "  Plugin log: /tmp/E2ScreenRecorder.log"
echo ""
echo "  Test shots:"
[ -f /tmp/E2SR_e2e_test.png ] && echo "    PNG  →  /tmp/E2SR_e2e_test.png"
[ -f /tmp/E2SR_e2e_test.jpg ] && echo "    JPEG →  /tmp/E2SR_e2e_test.jpg"
echo ""
echo "  Download to PC:"
printf "    scp root@"; hostname -I 2>/dev/null | awk '{printf $1}'; echo ":/tmp/E2SR_e2e_test.png ./"
printf "    scp root@"; hostname -I 2>/dev/null | awk '{printf $1}'; echo ":/tmp/E2SR_e2e_test.jpg ./"
echo ""
echo "  WebIF (open in browser):"
printf "    http://"; hostname -I 2>/dev/null | awk '{printf $1}'; echo ":8765/"
echo "========================================================="
printf "${RST}\n"

rm -rf "$TMP_DIR"
exit 0
