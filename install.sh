#!/bin/sh
# =============================================================================
# E2ScreenRecorder — Installer v2.3.0
# Repo layout: plugin files live at repo ROOT (no E2ScreenRecorder/ subdir)
# Compatible: OpenPLi, OpenATV, VTi, OpenDreambox, OpenBH, Pure2, EGAMI, etc.
# Python: 2.7 – 3.12+   Arch: MIPS, ARMv7, ARMv8 (cortexa15hf), SH4
# =============================================================================
set -e

PLUGIN="E2ScreenRecorder"
REPO_RAW="https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main"
INSTALL_DIR="/usr/lib/enigma2/python/Plugins/Extensions/${PLUGIN}"
TMP_DIR="/tmp/e2sr_tmp_$$"
LOG="/tmp/${PLUGIN}_install.log"
MIN_FREE_KB=4096

# ── Logging helpers ──────────────────────────────────────────────────────────
log()  { printf '[INFO]  %s\n' "$*"  | tee -a "$LOG"; }
ok()   { printf '[ OK ]  %s\n' "$*"  | tee -a "$LOG"; }
warn() { printf '[WARN]  %s\n' "$*"  | tee -a "$LOG"; }
die()  { printf '[ERROR] %s\n' "$*"  | tee -a "$LOG"; rm -rf "$TMP_DIR" 2>/dev/null; exit 1; }

# ── Cleanup trap ─────────────────────────────────────────────────────────────
cleanup() { rm -rf "$TMP_DIR" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo ""
echo "========================================================="
echo "  E2ScreenRecorder Installer v2.3.0"
echo "========================================================="
echo "" | tee -a "$LOG"
log "Starting installer  —  log: $LOG"

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
if [ "$IMAGE" = "unknown" ] && command -v opkg >/dev/null 2>&1; then
    _pkg="$(opkg info enigma2 2>/dev/null | head -20)"
    echo "$_pkg" | grep -qi "openatv" && IMAGE="openatv" || true
    echo "$_pkg" | grep -qi "openpli" && IMAGE="openpli" || true
fi
log "Image : $IMAGE"
log "Arch  : $(uname -m 2>/dev/null || echo unknown)"

# =============================================================================
# Detect Python
# =============================================================================
log "--- Detecting Python ---"
PY=""
for _c in python3 python python2; do
    command -v "$_c" >/dev/null 2>&1 && PY="$_c" && break
done
[ -z "$PY" ] && die "No Python interpreter found."
PY_VER="$($PY -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo '?')"
log "Python: $PY  (major: $PY_VER)"

# =============================================================================
# Network check
# =============================================================================
log "--- Checking network ---"
_net=0
for _h in 8.8.8.8 1.1.1.1 raw.githubusercontent.com; do
    ping -c 1 -W 3 "$_h" >/dev/null 2>&1 && _net=1 && break
done
[ "$_net" -eq 0 ] && die "No network. Check LAN/internet and retry."
ok "Network OK"

# =============================================================================
# /tmp free space  (fixed: pure arithmetic, no bc/awk needed)
# =============================================================================
log "--- Checking /tmp space ---"
_free="$(df -k /tmp 2>/dev/null | awk 'NR==2{print $4}')"
if [ -n "$_free" ]; then
    # strip any trailing non-digits (busybox df quirk)
    _free_num="$(echo "$_free" | tr -cd '0-9')"
    if [ -n "$_free_num" ] && [ "$_free_num" -lt "$MIN_FREE_KB" ] 2>/dev/null; then
        die "/tmp only ${_free_num}KB free — need ${MIN_FREE_KB}KB."
    fi
    ok "/tmp free: ${_free_num}KB"
else
    warn "Could not determine /tmp free space — continuing"
fi

# =============================================================================
# Download tool
# =============================================================================
log "--- Selecting download tool ---"
DL=""
if   command -v wget  >/dev/null 2>&1; then
    DL="wget -q --no-check-certificate --tries=3 --timeout=30 -O"
elif command -v curl  >/dev/null 2>&1; then
    DL="curl -s -L -k --retry 3 --max-time 30 -o"
elif busybox wget --help >/dev/null 2>&1; then
    DL="busybox wget -q -O"
else
    die "Neither wget nor curl found."
fi
log "Download tool: $(echo "$DL" | cut -d' ' -f1)"

# dl DEST URL
dl() { $DL "$1" "$2"; }

# =============================================================================
# Dependency check (opkg) — non-fatal throughout
# =============================================================================
log "--- Dependency check ---"
if command -v opkg >/dev/null 2>&1; then
    log "opkg update..."
    opkg update 2>/dev/null || warn "opkg update failed — continuing"

    _opkg_try() {
        pkg="$1"
        if opkg list-installed 2>/dev/null | grep -q "^${pkg} "; then
            log "  [SKIP] ${pkg} already installed"
        else
            opkg install "$pkg" 2>/dev/null \
                && ok  "  ${pkg} installed" \
                || warn "  ${pkg} not available in feed (non-fatal)"
        fi
    }

    log "--- TIER 1: Required ---"
    for _p in python3-core python3-compression python3-threading \
              python3-io python3-json python3-ctypes python3-logging; do
        _opkg_try "$_p"
    done

    log "--- TIER 2: Important ---"
    # Pillow — try python3-pillow first, then python-imaging
    if $PY -c "from PIL import Image" >/dev/null 2>&1; then
        ok "  PIL/Pillow already importable"
    else
        _opkg_try python3-pillow || _opkg_try python-imaging || true
    fi
    for _p in python3-codecs python3-misc python3-mmap; do
        _opkg_try "$_p"
    done

    log "--- TIER 3: Optional ---"
    for _p in python3-numpy python3-opencv python3-gi ffmpeg; do
        _opkg_try "$_p"
    done
else
    warn "opkg not found — skipping dependency install"
fi

# =============================================================================
# Stop Enigma2
# =============================================================================
log "--- Stopping Enigma2 ---"
E2_WAS_RUNNING=0
if pgrep -x enigma2 >/dev/null 2>&1; then
    E2_WAS_RUNNING=1
    log "Stopping Enigma2 (init 4)..."
    init 4 2>/dev/null || true; sleep 3
    pgrep -x enigma2 >/dev/null 2>&1 && \
        { warn "Still running — SIGTERM"; kill -TERM "$(pgrep -x enigma2)" 2>/dev/null || true; sleep 2; }
    pgrep -x enigma2 >/dev/null 2>&1 && \
        { warn "Force SIGKILL"; kill -9 "$(pgrep -x enigma2)" 2>/dev/null || true; sleep 1; }
    ok "Enigma2 stopped"
else
    log "Enigma2 not running"
fi

# Remove old install
if [ -d "$INSTALL_DIR" ]; then
    log "Removing old install at $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
    ok "Old install removed"
fi

# =============================================================================
# File list — paths relative to repo ROOT (no E2ScreenRecorder/ prefix)
# =============================================================================
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

# =============================================================================
# Download each file from repo root
# =============================================================================
log "--- Downloading plugin files ---"
mkdir -p "$TMP_DIR"
FAIL_LIST=""

for _f in $FILES; do
    _dest="${TMP_DIR}/${_f}"
    mkdir -p "$(dirname "$_dest")"
    # URL = REPO_RAW/<file>  (repo root, no subdir prefix)
    _url="${REPO_RAW}/${_f}"
    printf '[INFO]    -> %-48s' "$_f" | tee -a "$LOG"
    if dl "$_dest" "$_url" 2>/dev/null && [ -s "$_dest" ]; then
        printf 'OK\n'  | tee -a "$LOG"
    else
        printf 'FAIL\n' | tee -a "$LOG"
        FAIL_LIST="${FAIL_LIST} ${_f}"
        rm -f "$_dest" 2>/dev/null
    fi
done

# Check mandatory
HARD_FAIL=0
for _mf in $MANDATORY; do
    case " $FAIL_LIST " in
        *" $_mf "*) warn "MANDATORY failed: $_mf"; HARD_FAIL=1 ;;
    esac
done

if [ "$HARD_FAIL" -eq 1 ]; then
    # ── ZIP fallback ──────────────────────────────────────────────────────
    warn "Trying ZIP archive fallback..."
    ZIP_URL="https://github.com/SamoTech/E2ScreenRecorder/archive/refs/heads/main.zip"
    ZIP_FILE="/tmp/e2sr_main_$$.zip"
    ZIP_TMP="/tmp/e2sr_zip_$$"

    dl "$ZIP_FILE" "$ZIP_URL" 2>/dev/null || die "ZIP download failed. Check network."
    [ -s "$ZIP_FILE" ] || die "ZIP download empty."

    mkdir -p "$ZIP_TMP"
    UNZIP=""
    command -v unzip        >/dev/null 2>&1 && UNZIP="unzip -q"
    command -v busybox      >/dev/null 2>&1 && busybox unzip --help >/dev/null 2>&1 && \
        [ -z "$UNZIP" ] && UNZIP="busybox unzip -q"
    $PY -c "import zipfile" >/dev/null 2>&1 && \
        [ -z "$UNZIP" ] && UNZIP="$PY -c \"import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])\""

    [ -z "$UNZIP" ] && die "No unzip tool found (unzip, busybox unzip, or python zipfile)."

    log "Extracting ZIP with: $(echo "$UNZIP" | cut -d' ' -f1)..."
    case "$UNZIP" in
        "$PY"*) $PY -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
                    "$ZIP_FILE" "$ZIP_TMP" ;;
        *)      $UNZIP "$ZIP_FILE" -d "$ZIP_TMP" ;;
    esac
    rm -f "$ZIP_FILE"

    # GitHub ZIP extracts to E2ScreenRecorder-main/ at root
    # Plugin files are at E2ScreenRecorder-main/<file>  (no subdir)
    SRC_DIR="$ZIP_TMP/E2ScreenRecorder-main"
    [ -d "$SRC_DIR" ] || die "Expected ZIP source dir not found: $SRC_DIR"

    rm -rf "$TMP_DIR"; mkdir -p "$TMP_DIR"
    # Copy all plugin files (skip installer/build scripts and meta)
    for _f in $FILES; do
        _src="${SRC_DIR}/${_f}"
        _dest="${TMP_DIR}/${_f}"
        mkdir -p "$(dirname "$_dest")"
        if [ -f "$_src" ]; then
            cp "$_src" "$_dest"
            log "  ZIP → $_f"
        else
            warn "  ZIP missing: $_f"
        fi
    done
    rm -rf "$ZIP_TMP"

    # Re-check mandatory after ZIP
    HARD_FAIL=0
    for _mf in $MANDATORY; do
        [ -f "${TMP_DIR}/${_mf}" ] || { warn "Still missing: $_mf"; HARD_FAIL=1; }
    done
    [ "$HARD_FAIL" -eq 1 ] && die "Core files missing after ZIP fallback. See $LOG."
    ok "ZIP fallback succeeded"
fi

[ -n "$FAIL_LIST" ] && \
    warn "Optional files not downloaded (non-fatal — reduced features): $FAIL_LIST"

# =============================================================================
# Python syntax check
# =============================================================================
log "--- Verifying Python syntax ---"
_syn_ok=0; _syn_fail=0
for _py in "${TMP_DIR}/__init__.py" "${TMP_DIR}/plugin.py" \
           "${TMP_DIR}/ScreenRecorderPlugin.py" \
           "${TMP_DIR}/core/"*.py "${TMP_DIR}/backends/"*.py \
           "${TMP_DIR}/utils/"*.py "${TMP_DIR}/webif/"*.py; do
    [ -f "$_py" ] || continue
    if $PY -m py_compile "$_py" 2>/dev/null; then
        _syn_ok=$((_syn_ok + 1))
    else
        warn "Syntax issue in $(basename "$_py")"
        _syn_fail=$((_syn_fail + 1))
    fi
done
log "Syntax: ${_syn_ok} OK  /  ${_syn_fail} warnings"
[ "$_syn_ok" -gt 0 ] && ok "Python syntax check passed" || \
    warn "Syntax check had issues — installing anyway"

# =============================================================================
# Install (atomic mv)
# =============================================================================
log "--- Installing ---"
mkdir -p "$(dirname "$INSTALL_DIR")"
mv "$TMP_DIR" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Ensure __init__.py in every package dir
for _d in "$INSTALL_DIR" \
           "$INSTALL_DIR/core" \
           "$INSTALL_DIR/backends" \
           "$INSTALL_DIR/ui" \
           "$INSTALL_DIR/utils" \
           "$INSTALL_DIR/webif"; do
    [ -d "$_d" ] && { [ -f "$_d/__init__.py" ] || touch "$_d/__init__.py"; }
done
ok "Installed to: $INSTALL_DIR"

# =============================================================================
# Compile .pyc
# =============================================================================
log "--- Compiling bytecode ---"
$PY -m compileall "$INSTALL_DIR" >/dev/null 2>&1 \
    && ok "Bytecode OK" \
    || warn "Bytecode compilation had warnings (non-fatal)"

# =============================================================================
# Post-install verification
# =============================================================================
log "--- Verification ---"
_vfail=0
for _vf in __init__.py plugin.py ScreenRecorderPlugin.py \
           core/framebuffer.py core/recorder.py \
           backends/GrabberPPM.py utils/logger.py; do
    if [ -f "${INSTALL_DIR}/${_vf}" ]; then
        ok "  verified: $_vf"
    else
        warn "  missing:  $_vf"
        _vfail=1
    fi
done
[ "$_vfail" -eq 0 ] && ok "Verification passed" || \
    warn "Some optional files missing — plugin will run with reduced features"

# Detect WebIF port for summary
WEBIF_PORT=8765

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "========================================================="
echo "  Installation Complete!"
echo "  Image  : $IMAGE"
echo "  Arch   : $(uname -m 2>/dev/null || echo unknown)"
echo "  Python : $PY (v${PY_VER})"
echo "  Dir    : $INSTALL_DIR"
echo "  Log    : $LOG"
echo "  WebIF  : http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo STB-IP):${WEBIF_PORT}/"
echo "========================================================="
echo ""

# =============================================================================
# Restart Enigma2
# =============================================================================
log "--- Restarting Enigma2 ---"
if [ "$E2_WAS_RUNNING" -eq 1 ]; then
    log "Restarting (init 3)..."
    init 3 2>/dev/null || { warn "init 3 failed — trying direct launch"; /usr/bin/enigma2 & }
    ok "Enigma2 restart initiated"
else
    log "Enigma2 was not running — skipping restart"
    echo ""
    echo "  Run:  init 3   (or reboot)  to start Enigma2"
    echo ""
fi

echo ""
echo "[ OK ] E2ScreenRecorder installed successfully!"
echo ""
echo "  Access plugin : Plugins menu  →  Screen Recorder"
echo "  WebIF browser : http://<STB-IP>:${WEBIF_PORT}/"
echo "  Logfile       : $LOG"
echo ""
exit 0
