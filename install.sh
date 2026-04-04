#!/bin/sh
# v1.0.1 — post-audit patch
# Fixes: FIX-007 (sanitize FB_DEVICE before sed injection),
#        FIX-008 (stale PID lock detection),
#        FIX-009 (portable fb_size via wc -c),
#        FIX-017 (od fallback: xxd→hexdump→python for blank-frame detect),
#        FIX-018 (GNU vs BusyBox sed -i detection)
set -e

PLUGIN_NAME="E2ScreenRecorder"
INSTALL_DIR="/usr/lib/enigma2/python/Plugins/Extensions/${PLUGIN_NAME}"
LOCK_FILE="/tmp/.e2screenrecorder_install.lock"
LOG_FILE="/tmp/e2screenrecorder_install.log"
GITHUB_RAW="https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main"

# ── Logging ──────────────────────────────────────────────────────────────────
log_info()  { echo "[INFO]  $*" | tee -a "$LOG_FILE"; }
log_warn()  { echo "[WARN]  $*" | tee -a "$LOG_FILE"; }
log_error() { echo "[ERROR] $*" | tee -a "$LOG_FILE"; }
abort()     { log_error "$*"; exit 1; }

# ── FIX-008: stale PID lock detection ────────────────────────────────────────
check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            # FIX-008: PID is alive — real concurrent install
            abort "Install already running (PID $old_pid). Aborting."
        else
            # FIX-008: PID is dead — stale lock from crashed install
            log_warn "Removing stale lock file (PID $old_pid dead)"  # FIX-008
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $$ > "$LOCK_FILE"
}

release_lock() {
    rm -f "$LOCK_FILE"
}

# ── FIX-018: detect sed -i flavor (GNU vs BusyBox) ───────────────────────────
detect_sed() {
    if sed --version 2>/dev/null | grep -q GNU; then
        SED_INPLACE="sed -i"        # FIX-018: GNU sed
    else
        SED_INPLACE="sed -i.bak"    # FIX-018: BusyBox needs extension arg
    fi
    log_info "Sed flavor: $SED_INPLACE"
}

clean_sed_backups() {
    # FIX-018: remove .bak files created by BusyBox sed -i.bak
    find "$INSTALL_DIR" -name "*.bak" -delete 2>/dev/null || true
}

# ── FIX-009: portable framebuffer size check ──────────────────────────────────
check_framebuffer() {
    local fb="$1"
    if [ ! -e "$fb" ]; then
        log_warn "Framebuffer $fb not found"
        return 1
    fi

    # FIX-009: wc -c is universally available in BusyBox/toybox
    #          replaces 'stat -c%s' which is GNU-only
    fb_size=$(wc -c < "$fb" 2>/dev/null || echo 0)  # FIX-009
    if [ -z "$fb_size" ] || [ "$fb_size" -eq 0 ] 2>/dev/null; then
        # Fallback: ls -la parsing
        fb_size=$(ls -la "$fb" 2>/dev/null | awk '{print $5}' || echo 0)  # FIX-009
    fi
    log_info "Framebuffer $fb size: $fb_size bytes"

    # FIX-017: blank-frame detection — replace 'od' with portable alternatives
    # Try xxd first, then hexdump, then pure Python
    sample="unknown"
    if command -v xxd >/dev/null 2>&1; then
        zeros=$(xxd -l 64 "$fb" 2>/dev/null | grep -c "0000 0000 0000 0000" || echo 0)
        if [ "$zeros" -ge 4 ]; then sample="zero"; else sample="data"; fi
    elif command -v hexdump >/dev/null 2>&1; then
        zeros=$(hexdump -n 64 -e '16/1 "%02x" "\n"' "$fb" 2>/dev/null | \
                grep -c "^0000000000000000" || echo 0)
        if [ "$zeros" -ge 1 ]; then sample="zero"; else sample="data"; fi
    else
        # FIX-017: pure Python fallback for minimal BusyBox without od/xxd
        sample=$(python -c "
import sys
try:
    d = open('$fb','rb').read(64)
    print('zero' if d == b'\\x00'*len(d) else 'data')
except:
    print('unknown')
" 2>/dev/null || echo "unknown")  # FIX-017
    fi

    if [ "$sample" = "zero" ]; then
        log_warn "$fb appears blank (all zeros) — may be double-buffered"
        return 2  # caller can try /dev/fb1
    fi
    return 0
}

# ── FIX-007: sanitize fb_device path before injection ─────────────────────────
sanitize_path() {
    # FIX-007: strip all chars except alphanumeric, /, _, ., -
    # Prevents shell injection via FB_DEVICE value
    echo "$1" | tr -cd 'a-zA-Z0-9/_.-'  # FIX-007
}

# ── Detect best framebuffer ──────────────────────────────────────────────────
detect_framebuffer() {
    FB_DEVICE="/dev/fb0"
    check_framebuffer "/dev/fb0"
    status=$?
    if [ "$status" -eq 2 ] && [ -e "/dev/fb1" ]; then
        log_info "Trying /dev/fb1 (HiSilicon blank fb0 workaround)"
        check_framebuffer "/dev/fb1"
        if [ $? -eq 0 ]; then
            FB_DEVICE="/dev/fb1"
        fi
    fi
    log_info "Selected framebuffer device: $FB_DEVICE"
}

# ── Download plugin files ─────────────────────────────────────────────────────
download_plugin() {
    log_info "Creating install directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"

    FILES="
__init__.py
plugin.py
ScreenRecorderPlugin.py
core/__init__.py
core/compat.py
core/encoder.py
core/framebuffer.py
core/converter.py
core/recorder.py
core/storage.py
ui/__init__.py
ui/MainMenu.py
ui/Preview.py
ui/SettingsScreen.py
ui/StatusBar.py
backends/__init__.py
backends/GrabberPPM.py
backends/GrabberPIL.py
backends/GrabberFFmpeg.py
backends/GrabberGstreamer.py
backends/GrabberOpenCV.py
webif/__init__.py
webif/server.py
utils/__init__.py
utils/logger.py
utils/notify.py"

    for f in $FILES; do
        dir=$(dirname "$INSTALL_DIR/$f")
        mkdir -p "$dir"
        log_info "Downloading $f ..."
        if command -v wget >/dev/null 2>&1; then
            wget -q -O "$INSTALL_DIR/$f" "$GITHUB_RAW/E2ScreenRecorder/$f" || \
                log_warn "wget failed for $f"
        elif command -v curl >/dev/null 2>&1; then
            curl -sSL -o "$INSTALL_DIR/$f" "$GITHUB_RAW/E2ScreenRecorder/$f" || \
                log_warn "curl failed for $f"
        else
            abort "Neither wget nor curl found. Cannot download files."
        fi
    done
}

# ── Inject detected framebuffer device ───────────────────────────────────────
patch_fb_device() {
    # FIX-007: sanitize before using in any shell substitution
    FB_DEVICE_SAFE=$(sanitize_path "$FB_DEVICE")  # FIX-007
    if [ "$FB_DEVICE_SAFE" != "/dev/fb0" ]; then
        log_info "Patching framebuffer device to $FB_DEVICE_SAFE"
        # FIX-007: use Python for substitution — no shell expansion risk
        python -c "
import sys
path = sys.argv[1]
safe = sys.argv[2]
try:
    with open(path, 'r') as f: content = f.read()
    content = content.replace('/dev/fb0', safe)
    with open(path, 'w') as f: f.write(content)
except Exception as e:
    sys.exit(str(e))
" "$INSTALL_DIR/core/framebuffer.py" "$FB_DEVICE_SAFE" || \
            log_warn "Could not patch framebuffer path"  # FIX-007
    fi
    clean_sed_backups  # FIX-018: remove any stale .bak files
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    log_info "E2ScreenRecorder installer v1.0.1 starting"
    check_lock
    trap release_lock EXIT
    detect_sed        # FIX-018
    detect_framebuffer
    download_plugin
    patch_fb_device   # FIX-007
    log_info ""
    log_info "[OK] E2ScreenRecorder installed to $INSTALL_DIR"
    log_info "     Restart Enigma2: killall -1 enigma2"
    log_info "     WebIF default:   http://STB-IP:8765/"
    log_info "     Log file:        $LOG_FILE"
}

main "$@"
