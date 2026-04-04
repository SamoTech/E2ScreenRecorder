#!/bin/sh
# =============================================================================
# E2ScreenRecorder — Production Install Script
# Version : 2.1.0
# Target  : All Enigma2 STB images (BusyBox/toybox shell, MIPS/ARM/AArch64)
# Features: install / uninstall / update  |  env detection  |  full dep check
# Usage   : sh install.sh [install|uninstall|update]
# =============================================================================
# BusyBox-safe: POSIX sh only — no bash-isms, no arrays, no process substitution
# set -e stops on first unhandled error; traps clean up temp files on exit
# =============================================================================
set -e

# ── Constants ─────────────────────────────────────────────────────────────────
PLUGIN_NAME="E2ScreenRecorder"
INSTALL_DIR="/usr/lib/enigma2/python/Plugins/Extensions/${PLUGIN_NAME}"
LOCK_FILE="/tmp/.e2sr_install.lock"
LOG_FILE="/tmp/e2sr_install.log"
GITHUB_RAW="https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main"
GITHUB_ZIP="https://github.com/SamoTech/E2ScreenRecorder/archive/refs/heads/main.zip"
TMP_DIR="/tmp/e2sr_tmp_$$"

# Colour codes — suppressed on non-interactive terminals
if [ -t 1 ]; then
    C_GREEN="\033[1;32m"; C_YELLOW="\033[1;33m"
    C_RED="\033[1;31m";   C_CYAN="\033[1;36m"
    C_BOLD="\033[1m";     C_RESET="\033[0m"
else
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

# ── Logging ───────────────────────────────────────────────────────────────────
log_info()    { printf "${C_GREEN}[INFO]${C_RESET}  %s\n" "$*" | tee -a "$LOG_FILE"; }
log_warn()    { printf "${C_YELLOW}[WARN]${C_RESET}  %s\n" "$*" | tee -a "$LOG_FILE"; }
log_error()   { printf "${C_RED}[ERROR]${C_RESET} %s\n" "$*" | tee -a "$LOG_FILE"; }
log_ok()      { printf "${C_GREEN}[OK]${C_RESET}    %s\n" "$*" | tee -a "$LOG_FILE"; }
log_skip()    { printf "  ${C_CYAN}[SKIP]${C_RESET}  %s\n" "$*" | tee -a "$LOG_FILE"; }
log_section() { printf "\n${C_BOLD}${C_CYAN}=== %s ===${C_RESET}\n" "$*" | tee -a "$LOG_FILE"; }
abort()       { log_error "$*"; exit 1; }

# ── Lock management ───────────────────────────────────────────────────────────
acquire_lock() {
    if [ -f "$LOCK_FILE" ]; then
        old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            abort "Another install is running (PID $old_pid). Aborting."
        else
            log_warn "Removing stale lock (PID $old_pid is dead)."
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $$ > "$LOCK_FILE"
}
release_lock() { rm -f "$LOCK_FILE"; }

# ── Environment detection ─────────────────────────────────────────────────────
detect_image() {
    IMAGE_NAME="Unknown"
    for f in /etc/issue /etc/os-release /etc/opkg/arch.conf \
              /etc/enigma2-version /etc/distro-version; do
        [ -f "$f" ] || continue
        content=$(cat "$f" 2>/dev/null || echo "")
        case "$content" in
            *OpenATV*)              IMAGE_NAME="OpenATV";       break ;;
            *OpenPLi*|*openpli*|*OpenPLI*) IMAGE_NAME="OpenPLi"; break ;;
            *DreamOS*|*[Dd]reambox*) IMAGE_NAME="DreamOS";      break ;;
            *VTi*)                  IMAGE_NAME="VTi";           break ;;
            *OpenDreambox*)         IMAGE_NAME="OpenDreambox";  break ;;
            *OpenBH*|*BlackHole*)   IMAGE_NAME="OpenBH";        break ;;
            *OpenSPA*)              IMAGE_NAME="OpenSPA";       break ;;
            *[Oo]pen[Hh][Dd][Ff]*) IMAGE_NAME="OpenHDF";        break ;;
            *Pure2*)                IMAGE_NAME="Pure2";         break ;;
            *EGAMI*)                IMAGE_NAME="EGAMI";         break ;;
            *Beyonwiz*)             IMAGE_NAME="Beyonwiz";      break ;;
            *teamBlue*)             IMAGE_NAME="teamBlue";      break ;;
            *OpenMIPS*)             IMAGE_NAME="OpenMIPS";      break ;;
            *Merlin*)               IMAGE_NAME="Merlin";        break ;;
            *OpenVIX*)              IMAGE_NAME="OpenVIX";       break ;;
            *IHAD*)                 IMAGE_NAME="IHAD";          break ;;
            *Newnigma*)             IMAGE_NAME="Newnigma2";     break ;;
        esac
    done
    log_info "Detected image  : $IMAGE_NAME"
}

detect_python() {
    PY_BIN=""; PY_VER=0
    if   python3 --version >/dev/null 2>&1; then PY_BIN="python3"; PY_VER=3
    elif python  --version 2>&1 | grep -q "Python 3"; then PY_BIN="python"; PY_VER=3
    elif python  --version 2>&1 | grep -q "Python 2"; then PY_BIN="python"; PY_VER=2
    elif python2 --version >/dev/null 2>&1; then PY_BIN="python2"; PY_VER=2
    fi
    if [ -z "$PY_BIN" ]; then
        log_warn "Python not found in PATH — plugin may not work."
        PY_BIN="python"; PY_VER=3
    else
        py_full=$($PY_BIN --version 2>&1 || echo "")
        log_info "Python          : $py_full  (binary: $PY_BIN)"
    fi
}

detect_arch() {
    ARCH=$(uname -m 2>/dev/null || echo "unknown")
    case "$ARCH" in
        mips*)   ARCH="mipsel"  ;;
        arm*)    ARCH="arm"     ;;
        aarch64) ARCH="aarch64" ;;
        x86_64)  ARCH="x86_64"  ;;
    esac
    log_info "Architecture    : $ARCH"
}

# ── Pre-install checks ────────────────────────────────────────────────────────
preinstall_check() {
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Existing installation found — removing it cleanly."
        stop_enigma2
        remove_plugin_files
    else
        log_info "No previous installation found."
    fi
}

stop_enigma2() {
    if pidof enigma2 >/dev/null 2>&1; then
        log_info "Stopping Enigma2 (SIGTERM)..."
        kill -TERM $(pidof enigma2) 2>/dev/null || true
        sleep 3
        if pidof enigma2 >/dev/null 2>&1; then
            log_warn "Enigma2 still alive — sending SIGKILL."
            kill -9 $(pidof enigma2) 2>/dev/null || true
            sleep 1
        fi
        log_info "Enigma2 stopped."
    else
        log_info "Enigma2 is not running."
    fi
}

remove_plugin_files() {
    log_info "Removing $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
    find /usr/lib/enigma2/python/Plugins/Extensions \
         -maxdepth 2 -name "__pycache__" -type d \
         -exec rm -rf {} + 2>/dev/null || true
    find /usr/lib/enigma2/python/Plugins/Extensions \
         -maxdepth 3 \( -name "*.pyc" -o -name "*.pyo" \) \
         -delete 2>/dev/null || true
    log_info "Old installation removed."
}

# =============================================================================
# ── DEPENDENCY HANDLING ───────────────────────────────────────────────────────
# =============================================================================
# Full matrix of every package the plugin needs, organised by priority tier:
#
#   TIER 1 – REQUIRED  : plugin WILL NOT LOAD without these
#   TIER 2 – IMPORTANT : reduced features / fallback mode without these
#   TIER 3 – OPTIONAL  : speed / quality enhancements only
#
# Each package is checked with opkg list-installed first (fast, no network).
# Missing packages are installed via opkg; failures are logged but non-fatal
# for TIER 2/3 because the plugin has pure-Python fallbacks for everything.
# =============================================================================

# Helper: check if an opkg package is already installed.
_opkg_installed() {
    opkg list-installed 2>/dev/null | grep -q "^${1} "
}

# Helper: try to install a package; returns 0 on success, 1 on failure.
_opkg_install() {
    pkg="$1"
    if _opkg_installed "$pkg"; then
        log_skip "$pkg  (already installed)"
        return 0
    fi
    log_info "  Installing $pkg ..."
    opkg install "$pkg" 2>&1 | tee -a "$LOG_FILE" && return 0 || return 1
}

# Helper: verify a Python module can actually be imported.
_py_module_ok() {
    $PY_BIN -c "import $1" 2>/dev/null
}

install_deps() {
    log_section "Dependency Check  (image: $IMAGE_NAME  |  python: v$PY_VER)"

    # ── opkg availability ───────────────────────────────────────────────────
    if ! command -v opkg >/dev/null 2>&1; then
        log_warn "opkg not found — cannot install packages. Continuing with what is present."
        _verify_minimum_runtime
        return
    fi

    # ── opkg update ─────────────────────────────────────────────────────────
    log_info "Running opkg update ..."
    opkg update 2>&1 | tee -a "$LOG_FILE" \
        || log_warn "opkg update failed — package lists may be stale."

    # ====================================================================
    # TIER 1 — REQUIRED
    # The plugin uses only Python stdlib for its core path, so the only
    # hard requirement is a working Python interpreter + its standard
    # library modules: os, sys, struct, mmap, ctypes, fcntl, array,
    # threading, zlib, io, json, zipfile, socket, http.server / BaseHTTPServer
    # All of these ship inside the python3-core or python-core package.
    # ====================================================================
    log_info "--- TIER 1: Required packages ---"

    if [ "$PY_VER" -eq 3 ]; then
        _opkg_install "python3"           || log_warn "python3 meta-package missing"
        _opkg_install "python3-core"      || abort "python3-core is required and could not be installed."
        # zlib / compression — used by our built-in PNG encoder (zlib.compress)
        _opkg_install "python3-compression" \
            || _opkg_install "python3-zlib" \
            || log_warn "python3 zlib package not found — PNG fallback may fail on some images."
        # threading — FrameRecorder and WebIF server both run as daemon threads
        _opkg_install "python3-threading" \
            || log_warn "python3-threading not found — it is usually bundled inside python3-core."
        # io / codecs — used by every file write path
        _opkg_install "python3-io"        || true  # almost always in core
        # json — used by WebIF API responses
        _opkg_install "python3-json"      \
            || log_warn "python3-json missing — WebIF status API will be unavailable."
        # ctypes — used by framebuffer ioctl helpers on some STB kernels
        _opkg_install "python3-ctypes"    \
            || log_warn "python3-ctypes not found — ioctl fallback path will be used."
        # logging module — used by utils/logger.py
        _opkg_install "python3-logging"   || true
        # urllib / http.server — built-in WebIF depends on http.server (py3 stdlib)
        _opkg_install "python3-urllib"    || true
        # shell utilities needed during install itself
        _opkg_install "wget"  || _opkg_install "curl"  \
            || log_warn "Neither wget nor curl installed — file downloads may fail."
        _opkg_install "unzip" || log_warn "unzip not installed — ZIP fallback will be unavailable."
    else
        # Python 2.7 path
        _opkg_install "python"            || abort "python (2.7) is required and could not be installed."
        _opkg_install "python-core"       || abort "python-core is required and could not be installed."
        _opkg_install "python-compression" \
            || _opkg_install "python-zlib" \
            || log_warn "python zlib package not found — PNG fallback may fail."
        _opkg_install "python-threading"  \
            || log_warn "python-threading not found — usually bundled in python-core."
        _opkg_install "python-io"         || true
        _opkg_install "python-json"       \
            || log_warn "python-json missing — WebIF status API will be unavailable."
        _opkg_install "python-ctypes"     \
            || log_warn "python-ctypes not found — ioctl fallback path will be used."
        _opkg_install "python-logging"    || true
        _opkg_install "wget"  || _opkg_install "curl"  \
            || log_warn "Neither wget nor curl installed."
        _opkg_install "unzip" || log_warn "unzip not installed."
    fi

    # ====================================================================
    # TIER 2 — IMPORTANT  (plugin runs in fallback/reduced mode without)
    # ====================================================================
    log_info "--- TIER 2: Important packages (quality/feature fallbacks) ---"

    if [ "$PY_VER" -eq 3 ]; then
        # Pillow — best screenshot quality (PNG, JPEG, BMP with metadata)
        # Without it the plugin uses the built-in pure-Python PPM/PNG writer
        if ! _py_module_ok "PIL"; then
            _opkg_install "python3-pillow" \
                || _opkg_install "python3-pil" \
                || _opkg_install "python3-imaging" \
                || log_warn "Pillow not available — screenshots use built-in PPM/PNG encoder (lossless, no JPEG)."
        else
            log_skip "PIL/Pillow  (Python module already importable)"
        fi

        # struct / codecs extras — explicit large-buffer struct.unpack
        _opkg_install "python3-codecs"    || true
        _opkg_install "python3-misc"      || true  # includes many small stdlib extras
        _opkg_install "python3-mmap"      || true  # mmap.mmap used by framebuffer engine

    else
        if ! _py_module_ok "PIL"; then
            _opkg_install "python-imaging" \
                || _opkg_install "python-pillow" \
                || log_warn "Pillow/PIL not available — screenshots use built-in PPM/PNG encoder."
        else
            log_skip "PIL/Pillow  (Python module already importable)"
        fi
        _opkg_install "python-codecs"     || true
        _opkg_install "python-misc"       || true
        _opkg_install "python-mmap"       || true
    fi

    # FFmpeg binary — preferred video encoder
    # Without it FrameRecorder falls back to a ZIP archive of PNG frames
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_info "  Installing ffmpeg ..."
        _opkg_install "ffmpeg" \
            || _opkg_install "ffmpeg-x" \
            || log_warn "ffmpeg not available — video recording will produce a ZIP of PNG frames instead of MP4/AVI."
    else
        log_skip "ffmpeg  ($(ffmpeg -version 2>&1 | head -1))"
    fi

    # ====================================================================
    # TIER 3 — OPTIONAL  (speed / quality enhancements only)
    # ====================================================================
    log_info "--- TIER 3: Optional packages (speed / quality enhancements) ---"

    if [ "$PY_VER" -eq 3 ]; then
        # NumPy — accelerates pixel-format conversion (ARGB→RGB24) significantly
        # Without it the converter uses a pure-Python loop (slower but correct)
        if ! _py_module_ok "numpy"; then
            _opkg_install "python3-numpy" \
                || log_warn "NumPy not available — pixel conversion uses pure-Python loop (correct, but slower on 1080p)."
        else
            log_skip "numpy  (already importable)"
        fi

        # OpenCV — optional enhanced backend for screenshots
        if ! _py_module_ok "cv2"; then
            _opkg_install "python3-opencv" \
                || _opkg_install "python3-cv2" \
                || true   # fully optional — no warning needed
        else
            log_skip "cv2/OpenCV  (already importable)"
        fi

        # GStreamer Python bindings — native E2 video recording path
        if ! _py_module_ok "gi"; then
            _opkg_install "python3-gi" \
                || _opkg_install "python3-pygobject" \
                || true   # optional — FFmpeg path is preferred anyway
        else
            log_skip "gi/GStreamer bindings  (already importable)"
        fi

    else
        if ! _py_module_ok "numpy"; then
            _opkg_install "python-numpy" || true
        else
            log_skip "numpy  (already importable)"
        fi
        if ! _py_module_ok "gi"; then
            _opkg_install "python-gi" || _opkg_install "python-pygobject" || true
        else
            log_skip "gi/GStreamer bindings  (already importable)"
        fi
    fi

    # ── Post-install: verify minimum runtime is actually usable ─────────────
    _verify_minimum_runtime
}

# Final sanity check: confirm the absolute minimum modules are importable.
_verify_minimum_runtime() {
    log_info "--- Runtime verification ---"
    failed_mods=""

    for mod in os sys struct threading zlib io json; do
        if _py_module_ok "$mod"; then
            log_ok "  import $mod"
        else
            log_error "  import $mod  FAILED"
            failed_mods="$failed_mods $mod"
        fi
    done

    # mmap and ctypes: warn but not fatal (fallback paths exist)
    for mod in mmap ctypes fcntl; do
        if _py_module_ok "$mod"; then
            log_ok "  import $mod"
        else
            log_warn "  import $mod  not available — fallback path will be used."
        fi
    done

    # Pillow availability summary
    if _py_module_ok "PIL"; then
        log_ok "  import PIL (Pillow)  — full screenshot quality available"
    else
        log_warn "  import PIL  not available — using built-in PPM/PNG encoder"
    fi

    # FFmpeg binary summary
    if command -v ffmpeg >/dev/null 2>&1; then
        log_ok "  ffmpeg binary found  — MP4/AVI video recording enabled"
    else
        log_warn "  ffmpeg not found     — video falls back to ZIP-of-frames"
    fi

    # NumPy summary
    if _py_module_ok "numpy"; then
        log_ok "  import numpy  — accelerated pixel conversion enabled"
    else
        log_warn "  import numpy  not available — pure-Python converter in use"
    fi

    if [ -n "$failed_mods" ]; then
        abort "Critical Python modules unavailable:$failed_mods  — cannot continue."
    fi

    log_ok "Runtime check passed."
}

# ── Framebuffer detection ─────────────────────────────────────────────────────
detect_framebuffer() {
    FB_DEVICE="/dev/fb0"
    if [ ! -e "/dev/fb0" ]; then
        log_warn "/dev/fb0 not found."
        [ -e "/dev/fb1" ] && FB_DEVICE="/dev/fb1" && \
            log_info "Using /dev/fb1 as primary framebuffer."
        return
    fi
    blank=0
    if command -v xxd >/dev/null 2>&1; then
        zeros=$(xxd -l 64 /dev/fb0 2>/dev/null | grep -c "0000 0000 0000 0000" || echo 0)
        [ "$zeros" -ge 4 ] && blank=1
    elif command -v hexdump >/dev/null 2>&1; then
        zeros=$(hexdump -n 64 -e '16/1 "%02x" "\n"' /dev/fb0 2>/dev/null | \
                grep -c "^0000000000000000" || echo 0)
        [ "$zeros" -ge 1 ] && blank=1
    else
        blank=$($PY_BIN -c "
try:
    d=open('/dev/fb0','rb').read(64)
    print(1 if d==b'\\x00'*len(d) else 0)
except: print(0)
" 2>/dev/null || echo 0)
    fi
    if [ "$blank" = "1" ] && [ -e "/dev/fb1" ]; then
        log_warn "/dev/fb0 is blank (HiSilicon?) — switching to /dev/fb1."
        FB_DEVICE="/dev/fb1"
    fi
    log_info "Selected framebuffer: $FB_DEVICE"
}

sanitize_path() { echo "$1" | tr -cd 'a-zA-Z0-9/_.-'; }

# ── File installation ─────────────────────────────────────────────────────────
download_plugin() {
    log_section "Downloading Plugin Files"
    mkdir -p "$TMP_DIR"
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

    if command -v wget >/dev/null 2>&1; then DLCMD="wget -q -O"
    elif command -v curl >/dev/null 2>&1; then DLCMD="curl -sSL -o"
    else abort "Neither wget nor curl is available. Cannot download plugin."
    fi

    failed=0
    for f in $FILES; do
        dest="$INSTALL_DIR/$f"
        mkdir -p "$(dirname "$dest")"
        url="${GITHUB_RAW}/E2ScreenRecorder/${f}"
        log_info "  → $f"
        $DLCMD "$dest" "$url" 2>>"$LOG_FILE" || {
            log_warn "    Failed: $f"
            failed=$((failed + 1))
        }
    done
    if [ "$failed" -gt 5 ]; then
        log_warn "$failed download failures — trying ZIP fallback..."
        download_via_zip
    fi
}

download_via_zip() {
    log_info "Downloading ZIP archive from GitHub..."
    zip_path="$TMP_DIR/e2sr_main.zip"
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$zip_path" "$GITHUB_ZIP" || abort "ZIP download failed."
    else
        curl -sSL -o "$zip_path" "$GITHUB_ZIP" || abort "ZIP download failed."
    fi
    command -v unzip >/dev/null 2>&1 || abort "unzip not available — cannot extract ZIP."
    unzip -q "$zip_path" -d "$TMP_DIR/" || abort "unzip failed."
    src="$TMP_DIR/E2ScreenRecorder-main/E2ScreenRecorder"
    [ -d "$src" ] || abort "Expected source dir not found inside ZIP: $src"
    mkdir -p "$INSTALL_DIR"
    cp -r "$src/." "$INSTALL_DIR/"
    log_info "Extracted from ZIP archive OK."
}

set_permissions() {
    log_info "Setting permissions ..."
    find "$INSTALL_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
    find "$INSTALL_DIR" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
    chmod 755 "$INSTALL_DIR" 2>/dev/null || true
}

# ── Post-install patching ─────────────────────────────────────────────────────
patch_fb_device() {
    FB_SAFE=$(sanitize_path "$FB_DEVICE")
    [ "$FB_SAFE" = "/dev/fb0" ] && return
    log_info "Patching framebuffer path → $FB_SAFE"
    $PY_BIN -c "
import sys
path,safe=sys.argv[1],sys.argv[2]
try:
    with open(path,'r') as fh: c=fh.read()
    with open(path,'w') as fh: fh.write(c.replace('/dev/fb0',safe))
except Exception as e: sys.exit(str(e))
" "$INSTALL_DIR/core/framebuffer.py" "$FB_SAFE" 2>>"$LOG_FILE" \
        || log_warn "Could not patch framebuffer path — defaulting to /dev/fb0."
}

compile_python() {
    log_info "Compiling Python bytecode ..."
    $PY_BIN -m compileall -q "$INSTALL_DIR" 2>>"$LOG_FILE" \
        || log_warn "compileall had warnings — not critical."
}

# ── Enigma2 lifecycle ─────────────────────────────────────────────────────────
restart_enigma2() {
    log_info "Restarting Enigma2..."
    sleep 1
    if command -v systemctl >/dev/null 2>&1 && \
       systemctl list-units --type=service 2>/dev/null | grep -q enigma2; then
        systemctl restart enigma2 2>/dev/null || killall -9 enigma2 2>/dev/null || true
    else
        killall -9 enigma2 2>/dev/null || true
    fi
    log_info "Enigma2 restart signal sent."
}

cleanup_tmp() { rm -rf "$TMP_DIR" 2>/dev/null || true; }

# ── INSTALL ───────────────────────────────────────────────────────────────────
do_install() {
    log_section "E2ScreenRecorder Installer v2.1.0"
    acquire_lock
    trap 'release_lock; cleanup_tmp' EXIT

    detect_image
    detect_python
    detect_arch
    preinstall_check
    install_deps          # ← full tier-1/2/3 dependency matrix
    detect_framebuffer
    download_plugin
    set_permissions
    patch_fb_device
    compile_python
    restart_enigma2

    log_section "Installation Complete"
    log_info "Plugin installed at : $INSTALL_DIR"
    log_info "Image               : $IMAGE_NAME"
    log_info "Python              : $PY_BIN (v$PY_VER)"
    log_info "Architecture        : $ARCH"
    log_info "Framebuffer         : $FB_DEVICE"
    log_info "WebIF port          : 8765  →  http://STB-IP:8765/"
    log_info "Log file            : $LOG_FILE"
    printf "${C_GREEN}${C_BOLD}[OK] E2ScreenRecorder is installed!${C_RESET}\n"
}

# ── UNINSTALL ─────────────────────────────────────────────────────────────────
do_uninstall() {
    log_section "E2ScreenRecorder Uninstaller"
    acquire_lock
    trap 'release_lock' EXIT
    detect_python
    if [ ! -d "$INSTALL_DIR" ]; then
        log_warn "Plugin not found at $INSTALL_DIR — nothing to remove."
        exit 0
    fi
    stop_enigma2
    remove_plugin_files
    command -v opkg >/dev/null 2>&1 && \
        opkg remove enigma2-plugin-extensions-e2screenrecorder 2>/dev/null || true
    restart_enigma2
    log_section "Uninstall Complete"
    printf "${C_GREEN}[OK] E2ScreenRecorder has been removed.${C_RESET}\n"
}

# ── UPDATE ────────────────────────────────────────────────────────────────────
do_update() {
    log_section "E2ScreenRecorder Updater"
    cfg_src="/etc/enigma2/E2ScreenRecorder.conf"
    cfg_bak="/tmp/e2sr_config_backup"
    [ -f "$cfg_src" ] && cp "$cfg_src" "$cfg_bak" 2>/dev/null && \
        log_info "Config backed up → $cfg_bak"
    do_install
    [ -f "$cfg_bak" ] && cp "$cfg_bak" "$cfg_src" 2>/dev/null && \
        log_info "Config restored."
    log_section "Update Complete"
    printf "${C_GREEN}[OK] E2ScreenRecorder updated to latest version.${C_RESET}\n"
}

# ── Entry point ───────────────────────────────────────────────────────────────
ACTION="${1:-install}"
case "$ACTION" in
    install)   do_install   ;;
    uninstall) do_uninstall ;;
    update)    do_update    ;;
    *)
        printf "Usage: sh install.sh [install|uninstall|update]\n"
        printf "  install   — Install or reinstall the plugin (default)\n"
        printf "  uninstall — Remove the plugin completely\n"
        printf "  update    — Pull latest version from GitHub\n"
        exit 1 ;;
esac
