#!/bin/sh
# =============================================================================
# E2ScreenRecorder — Clean RAW Installer (No ZIP / No IPK)
# Compatible: OpenPLi, OpenATV, VTi, OpenDreambox, OpenBH, Pure2, EGAMI, etc.
# Python: 2.7 – 3.12+   Arch: MIPS, ARMv7, ARMv8, SH4
# =============================================================================
set -e

PLUGIN="E2ScreenRecorder"
BASE_URL="https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/E2ScreenRecorder"
INSTALL_DIR="/usr/lib/enigma2/python/Plugins/Extensions/${PLUGIN}"
TMP_DIR="/tmp/${PLUGIN}_$$"
LOG="/tmp/${PLUGIN}_install.log"
MIN_FREE_KB=4096

# ── Logging helpers ──────────────────────────────────────────────────────────
log()  { echo "[INFO]  $*" | tee -a "$LOG"; }
ok()   { echo "[ OK ]  $*" | tee -a "$LOG"; }
warn() { echo "[WARN]  $*" | tee -a "$LOG"; }
die()  { echo "[FAIL]  $*" | tee -a "$LOG"; rm -rf "$TMP_DIR" 2>/dev/null; exit 1; }

# ── Cleanup trap ─────────────────────────────────────────────────────────────
cleanup() { rm -rf "$TMP_DIR" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo ""
echo "========================================================="
echo "  E2ScreenRecorder — Clean RAW Installer (No ZIP/No IPK)"
echo "========================================================="
echo "" | tee -a "$LOG"
log "Starting installer..."
log "Log: $LOG"

# =============================================================================
# Detect Image
# =============================================================================
log "--- Detecting image ---"
IMAGE="unknown"
for _f in /etc/issue /etc/enigma2-version /etc/opkg/arch.conf; do
    [ -f "$_f" ] || continue
    grep -qi "openatv"                "$_f" 2>/dev/null && IMAGE="openatv"  && break
    grep -qi "openpli"                "$_f" 2>/dev/null && IMAGE="openpli"  && break
    grep -qi "opendreambox\|dreambox" "$_f" 2>/dev/null && IMAGE="dreambox" && break
    grep -qi "vti"                    "$_f" 2>/dev/null && IMAGE="vti"      && break
    grep -qi "merlin"                 "$_f" 2>/dev/null && IMAGE="merlin"   && break
    grep -qi "openvix"                "$_f" 2>/dev/null && IMAGE="openvix"  && break
    grep -qi "openbh\|blackhole"      "$_f" 2>/dev/null && IMAGE="openbh"   && break
    grep -qi "pure2"                  "$_f" 2>/dev/null && IMAGE="pure2"    && break
    grep -qi "egami"                  "$_f" 2>/dev/null && IMAGE="egami"    && break
    grep -qi "openspa"                "$_f" 2>/dev/null && IMAGE="openspa"  && break
done
# opkg fallback
if [ "$IMAGE" = "unknown" ] && command -v opkg >/dev/null 2>&1; then
    _pkg="$(opkg info enigma2 2>/dev/null | head -20)"
    echo "$_pkg" | grep -qi "openatv" && IMAGE="openatv"
    echo "$_pkg" | grep -qi "openpli" && IMAGE="openpli"
fi
log "Image: $IMAGE"
log "Arch:  $(uname -m 2>/dev/null || echo unknown)"

# =============================================================================
# Detect Python
# =============================================================================
log "--- Detecting Python ---"
PY=""
for _c in python3 python python2; do
    command -v "$_c" >/dev/null 2>&1 && PY="$_c" && break
done
[ -z "$PY" ] && die "No Python interpreter found. Cannot proceed."
PY_VER="$($PY -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo '?')"
log "Python: $PY (major: $PY_VER)"

# =============================================================================
# Check network
# =============================================================================
log "--- Checking network ---"
_net=0
for _h in 8.8.8.8 1.1.1.1 raw.githubusercontent.com; do
    ping -c 1 -W 3 "$_h" >/dev/null 2>&1 && _net=1 && break
done
[ "$_net" -eq 0 ] && die "No network connectivity. Check LAN/internet and retry."
ok "Network OK"

# =============================================================================
# Check /tmp free space
# =============================================================================
log "--- Checking /tmp space ---"
_free="$(df -k /tmp 2>/dev/null | awk 'NR==2{print $4}')"
if [ -n "$_free" ] && [ "$_free" -lt "$MIN_FREE_KB" ]; then
    die "/tmp has only ${_free}KB free — need ${MIN_FREE_KB}KB. Clear space and retry."
fi
ok "/tmp free: ${_free}KB"

# =============================================================================
# Select download tool
# =============================================================================
log "--- Selecting download tool ---"
DL_CMD=""
if   command -v wget    >/dev/null 2>&1; then DL_CMD="wget -q --no-check-certificate --tries=3 --timeout=30 -O"
elif command -v curl    >/dev/null 2>&1; then DL_CMD="curl -s -L -k --retry 3 --max-time 30 -o"
elif busybox wget --help >/dev/null 2>&1; then DL_CMD="busybox wget -q -O"
else die "Neither wget nor curl found. Install one and retry."
fi
log "Download tool: $DL_CMD"

dl() { $DL_CMD "$1" "$2"; }   # usage: dl DEST URL

# =============================================================================
# Stop Enigma2
# =============================================================================
log "--- Stopping Enigma2 ---"
E2_WAS_RUNNING=0
if pgrep -x enigma2 >/dev/null 2>&1; then
    E2_WAS_RUNNING=1
    log "Enigma2 running — stopping (init 4)..."
    init 4 2>/dev/null || true
    sleep 3
    if pgrep -x enigma2 >/dev/null 2>&1; then
        warn "Still running — SIGTERM..."
        kill -TERM "$(pgrep -x enigma2)" 2>/dev/null || true
        sleep 2
    fi
    if pgrep -x enigma2 >/dev/null 2>&1; then
        warn "Force kill (SIGKILL)..."
        kill -9 "$(pgrep -x enigma2)" 2>/dev/null || true
        sleep 1
    fi
    ok "Enigma2 stopped"
else
    log "Enigma2 not running — skipping"
fi

# =============================================================================
# Remove old version
# =============================================================================
log "--- Removing old version ---"
if [ -d "$INSTALL_DIR" ]; then
    log "Removing existing install at $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
    ok "Old version removed"
else
    log "No existing install found"
fi

# =============================================================================
# Dependency check (opkg)
# =============================================================================
log "--- Dependency check ---"
if command -v opkg >/dev/null 2>&1; then
    log "Updating feeds..."
    opkg update 2>/dev/null || warn "opkg update failed (offline feed?) — continuing"

    if ! opkg list-installed 2>/dev/null | grep -q "^python3-core"; then
        log "Installing python3-core..."
        opkg install python3-core 2>/dev/null \
            && ok "python3-core installed" \
            || warn "python3-core install failed — using existing Python"
    else
        ok "python3-core already installed"
    fi

    # Pillow — prefer python3-pillow, fall back to python-imaging
    _pil=""
    opkg list 2>/dev/null | grep -q "^python3-pillow " && _pil="python3-pillow"
    opkg list 2>/dev/null | grep -q "^python-imaging "  && [ -z "$_pil" ] && _pil="python-imaging"
    if [ -n "$_pil" ] && ! opkg list-installed 2>/dev/null | grep -q "^${_pil}"; then
        log "Installing ${_pil}..."
        opkg install "$_pil" 2>/dev/null \
            && ok "${_pil} installed" \
            || warn "${_pil} unavailable — PPM/PNG fallback will be used"
    else
        ok "Pillow/PIL: present or not available in feed"
    fi

    if ! opkg list-installed 2>/dev/null | grep -q "^ffmpeg"; then
        log "Installing ffmpeg..."
        opkg install ffmpeg 2>/dev/null \
            && ok "ffmpeg installed" \
            || warn "ffmpeg unavailable — frame-ZIP fallback will be used for video"
    else
        ok "ffmpeg already installed"
    fi
else
    warn "opkg not found — skipping dependency install"
fi

# =============================================================================
# Download RAW files (atomic into TMP_DIR)
# =============================================================================
log "--- Downloading plugin files ---"

FILES="
__init__.py
plugin.py
ScreenRecorderPlugin.py
core/__init__.py
core/framebuffer.py
core/converter.py
core/encoder.py
core/recorder.py
core/storage.py
core/compat.py
backends/__init__.py
backends/GrabberPPM.py
backends/GrabberPIL.py
backends/GrabberFFmpeg.py
backends/GrabberGstreamer.py
backends/GrabberOpenCV.py
ui/__init__.py
ui/MainMenu.py
ui/Preview.py
ui/StatusBar.py
ui/SettingsScreen.py
utils/__init__.py
utils/logger.py
utils/notify.py
webif/__init__.py
webif/server.py
"

# Mandatory files — hard abort if any of these fail
MANDATORY="
__init__.py
plugin.py
ScreenRecorderPlugin.py
core/__init__.py
core/framebuffer.py
core/converter.py
core/encoder.py
core/recorder.py
core/storage.py
backends/__init__.py
backends/GrabberPPM.py
utils/__init__.py
utils/logger.py
utils/notify.py
"

mkdir -p "$TMP_DIR"
FAIL_LIST=""

for _f in $FILES; do
    _dest="${TMP_DIR}/${_f}"
    mkdir -p "$(dirname "$_dest")"
    _url="${BASE_URL}/${_f}"
    printf "[INFO]  -> %-48s" "$_f"
    if dl "$_dest" "$_url" 2>/dev/null && [ -s "$_dest" ]; then
        echo "OK" | tee -a "$LOG"
    else
        echo "FAIL" | tee -a "$LOG"
        FAIL_LIST="${FAIL_LIST} ${_f}"
    fi
done

# Check mandatory files
HARD_FAIL=0
for _mf in $MANDATORY; do
    case " $FAIL_LIST " in
        *" $_mf "*) warn "MANDATORY file failed: $_mf"; HARD_FAIL=1 ;;
    esac
done
if [ "$HARD_FAIL" -eq 1 ]; then
    die "One or more mandatory files failed to download. Check network and retry."
fi
if [ -n "$FAIL_LIST" ]; then
    warn "Optional files failed (non-fatal): $FAIL_LIST"
    warn "Plugin will run with reduced features (no WebIF / basic backends)"
fi
ok "Download complete"

# =============================================================================
# Verify Python syntax on downloaded core files
# =============================================================================
log "--- Verifying Python syntax ---"
_syn_fail=0
for _py in "${TMP_DIR}/core/"*.py "${TMP_DIR}/backends/"*.py \
           "${TMP_DIR}/__init__.py" "${TMP_DIR}/plugin.py"; do
    [ -f "$_py" ] || continue
    $PY -m py_compile "$_py" 2>/dev/null || {
        warn "Syntax issue in: $(basename "$_py") — installing anyway"
        _syn_fail=1
    }
done
[ "$_syn_fail" -eq 0 ] && ok "Python syntax OK" || warn "Some syntax warnings — see log"

# =============================================================================
# Install (atomic move TMP_DIR -> INSTALL_DIR)
# =============================================================================
log "--- Installing ---"
mkdir -p "$(dirname "$INSTALL_DIR")"
mv "$TMP_DIR" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Ensure __init__.py exists in every package dir (required for E2 import)
for _d in "$INSTALL_DIR" \
           "$INSTALL_DIR/core" \
           "$INSTALL_DIR/backends" \
           "$INSTALL_DIR/ui" \
           "$INSTALL_DIR/utils" \
           "$INSTALL_DIR/webif"; do
    [ -d "$_d" ] || continue
    [ -f "$_d/__init__.py" ] || touch "$_d/__init__.py"
done
ok "Installed to: $INSTALL_DIR"

# =============================================================================
# Compile .pyc bytecode
# =============================================================================
log "--- Compiling ---"
$PY -m compileall "$INSTALL_DIR" >/dev/null 2>&1 \
    && ok "Bytecode compilation OK" \
    || warn "Bytecode compilation had warnings (non-fatal)"

# =============================================================================
# Post-install verification
# =============================================================================
log "--- Post-install verification ---"
_vfail=0
for _vf in __init__.py plugin.py ScreenRecorderPlugin.py \
           core/framebuffer.py core/recorder.py backends/GrabberPPM.py; do
    if [ -f "${INSTALL_DIR}/${_vf}" ]; then
        echo "[ OK ]  verified: $_vf" | tee -a "$LOG"
    else
        echo "[WARN]  missing:  $_vf" | tee -a "$LOG"
        _vfail=1
    fi
done
[ "$_vfail" -eq 0 ] && ok "Verification passed" \
    || warn "Some files missing — plugin may have reduced functionality"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "========================================================="
echo "  Installation Summary"
echo "  Image  : $IMAGE"
echo "  Arch   : $(uname -m 2>/dev/null || echo unknown)"
echo "  Python : $PY (v${PY_VER})"
echo "  Install: $INSTALL_DIR"
echo "  Log    : $LOG"
echo "========================================================="
echo ""

# =============================================================================
# Restart Enigma2
# =============================================================================
log "--- Restarting Enigma2 ---"
if [ "$E2_WAS_RUNNING" -eq 1 ]; then
    log "Restarting Enigma2 (init 3)..."
    init 3 2>/dev/null || /usr/bin/enigma2 &
    ok "Enigma2 restart initiated"
else
    log "Enigma2 was not running — skipping restart"
fi

echo ""
echo "[ OK ] E2ScreenRecorder installed successfully!"
echo "       Access WebIF: http://<STB-IP>:8765/"
echo ""
exit 0
