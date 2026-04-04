#!/bin/sh
# =============================================================================
# E2ScreenRecorder — Production Install Script
# Version : 2.0.0
# Target  : All Enigma2 STB images (BusyBox/toybox shell, MIPS/ARM/AArch64)
# Features: install / uninstall / update  |  env detection  |  dep handling
# Usage   : sh install.sh [install|uninstall|update]
# =============================================================================
# BusyBox-safe: no bash-isms, no process substitution, no arrays
# set -e stops on first unhandled error; traps clean up on exit
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
    C_RESET="\033[0m"
else
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_RESET=""
fi

# ── Logging ───────────────────────────────────────────────────────────────────
log_info()    { printf "${C_GREEN}[INFO]${C_RESET}  %s\n" "$*" | tee -a "$LOG_FILE"; }
log_warn()    { printf "${C_YELLOW}[WARN]${C_RESET}  %s\n" "$*" | tee -a "$LOG_FILE"; }
log_error()   { printf "${C_RED}[ERROR]${C_RESET} %s\n" "$*" | tee -a "$LOG_FILE"; }
log_section() { printf "${C_CYAN}=== %s ===${C_RESET}\n" "$*" | tee -a "$LOG_FILE"; }
abort()       { log_error "$*"; exit 1; }

# ── Lock management ───────────────────────────────────────────────────────────
# Detects stale locks left by previously crashed installs (PID dead = stale).
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
# Reads /etc/*release files to identify the Enigma2 image family.
detect_image() {
    IMAGE_NAME="Unknown"
    for f in /etc/issue /etc/os-release /etc/opkg/arch.conf \
              /etc/enigma2-version /etc/distro-version; do
        if [ -f "$f" ]; then
            content=$(cat "$f" 2>/dev/null || echo "")
            case "$content" in
                *OpenATV*)    IMAGE_NAME="OpenATV";    break ;;
                *OpenPLi*|*openpli*) IMAGE_NAME="OpenPLi"; break ;;
                *OpenPLI*)    IMAGE_NAME="OpenPLi";    break ;;
                *DreamOS*|*Dreambox*|*dreambox*) IMAGE_NAME="DreamOS"; break ;;
                *VTi*)        IMAGE_NAME="VTi";        break ;;
                *OpenDreambox*) IMAGE_NAME="OpenDreambox"; break ;;
                *OpenBH*|*BlackHole*) IMAGE_NAME="OpenBH"; break ;;
                *OpenSPA*)    IMAGE_NAME="OpenSPA";    break ;;
                *openHDF*|*OpenHDF*) IMAGE_NAME="OpenHDF"; break ;;
                *Pure2*)      IMAGE_NAME="Pure2";      break ;;
                *EGAMI*)      IMAGE_NAME="EGAMI";      break ;;
                *Beyonwiz*)   IMAGE_NAME="Beyonwiz";   break ;;
                *teamBlue*)   IMAGE_NAME="teamBlue";   break ;;
                *OpenMIPS*)   IMAGE_NAME="OpenMIPS";   break ;;
                *Merlin*)     IMAGE_NAME="Merlin";     break ;;
                *OpenVIX*)    IMAGE_NAME="OpenVIX";    break ;;
            esac
        fi
    done
    log_info "Detected image: $IMAGE_NAME"
}

# Detect Python version (2 or 3) and set PY_BIN / PY_VER.
detect_python() {
    PY_BIN=""
    PY_VER=0
    if python3 --version >/dev/null 2>&1; then
        PY_BIN="python3"
        PY_VER=3
    elif python --version 2>&1 | grep -q "Python 3"; then
        PY_BIN="python"
        PY_VER=3
    elif python --version 2>&1 | grep -q "Python 2"; then
        PY_BIN="python"
        PY_VER=2
    elif python2 --version >/dev/null 2>&1; then
        PY_BIN="python2"
        PY_VER=2
    fi

    if [ -z "$PY_BIN" ]; then
        log_warn "Python not found in PATH — plugin may not work."
        PY_BIN="python"
        PY_VER=3
    else
        py_full=$($PY_BIN --version 2>&1 || echo "")
        log_info "Python: $py_full (binary: $PY_BIN)"
    fi
}

# Detect CPU architecture from uname.
detect_arch() {
    ARCH=$(uname -m 2>/dev/null || echo "unknown")
    case "$ARCH" in
        mips*)   ARCH="mipsel" ;;
        arm*)    ARCH="arm"    ;;
        aarch64) ARCH="aarch64" ;;
        x86_64)  ARCH="x86_64"  ;;
    esac
    log_info "Architecture: $ARCH"
}

# ── Pre-install checks ────────────────────────────────────────────────────────
# If plugin exists: stop Enigma2, wipe old installation cleanly.
preinstall_check() {
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Existing installation found at $INSTALL_DIR — removing it."
        stop_enigma2
        remove_plugin_files
    else
        log_info "No previous installation found."
    fi
}

# Stop Enigma2 gracefully (SIGTERM first, SIGKILL fallback after 3s).
stop_enigma2() {
    if pidof enigma2 >/dev/null 2>&1; then
        log_info "Stopping Enigma2..."
        kill -TERM $(pidof enigma2) 2>/dev/null || true
        sleep 3
        if pidof enigma2 >/dev/null 2>&1; then
            log_warn "Enigma2 still running — sending SIGKILL."
            kill -9 $(pidof enigma2) 2>/dev/null || true
            sleep 1
        fi
        log_info "Enigma2 stopped."
    else
        log_info "Enigma2 is not running."
    fi
}

# Remove old plugin files including compiled bytecode.
remove_plugin_files() {
    log_info "Removing $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"

    # Clean any stray compiled files in parent dir
    find /usr/lib/enigma2/python/Plugins/Extensions \
         -maxdepth 2 -name "__pycache__" -type d \
         -exec rm -rf {} + 2>/dev/null || true
    find /usr/lib/enigma2/python/Plugins/Extensions \
         -maxdepth 3 \( -name "*.pyc" -o -name "*.pyo" \) \
         -delete 2>/dev/null || true

    log_info "Old installation removed."
}

# ── Dependency handling ───────────────────────────────────────────────────────
# opkg update + install missing packages based on Python version.
install_deps() {
    log_section "Dependency Check"

    if ! command -v opkg >/dev/null 2>&1; then
        log_warn "opkg not found — skipping dependency install."
        return
    fi

    log_info "Running opkg update..."
    opkg update 2>&1 | tee -a "$LOG_FILE" || log_warn "opkg update failed (no internet?)"

    # Common tools
    for pkg in wget curl unzip; do
        if ! command -v "$pkg" >/dev/null 2>&1; then
            log_info "Installing $pkg ..."
            opkg install "$pkg" 2>&1 | tee -a "$LOG_FILE" || log_warn "Could not install $pkg"
        else
            log_info "$pkg already available."
        fi
    done

    # Python packages — branch on detected version
    if [ "$PY_VER" -eq 3 ]; then
        PYCORE="python3-core"
        PYREQ="python3-requests"
        PYJSON="python3-json"
        PYIMAGE="python3-pillow"
        PYZLIB="python3-compression"
    else
        PYCORE="python-core"
        PYREQ="python-requests"
        PYJSON="python-json"
        PYIMAGE="python-imaging"
        PYZLIB="python-compression"
    fi

    for pkg in "$PYCORE" "$PYREQ" "$PYJSON" "$PYZLIB"; do
        if opkg list-installed 2>/dev/null | grep -q "^${pkg} "; then
            log_info "$pkg already installed."
        else
            log_info "Installing $pkg ..."
            opkg install "$pkg" 2>&1 | tee -a "$LOG_FILE" || \
                log_warn "Could not install $pkg — plugin may have reduced features."
        fi
    done

    # Pillow/PIL is recommended but not mandatory — log only
    if ! opkg list-installed 2>/dev/null | grep -q "^${PYIMAGE} "; then
        log_warn "$PYIMAGE not installed — screenshots will use built-in PPM/PNG backend."
        opkg install "$PYIMAGE" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    # FFmpeg — recommended for video recording
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_warn "ffmpeg not found — installing..."
        opkg install ffmpeg 2>&1 | tee -a "$LOG_FILE" || \
            log_warn "ffmpeg not available — video will fall back to frame-zip."
    else
        log_info "ffmpeg already available."
    fi
}

# ── Framebuffer detection ─────────────────────────────────────────────────────
# HiSilicon devices export a blank /dev/fb0; real OSD is on /dev/fb1.
detect_framebuffer() {
    FB_DEVICE="/dev/fb0"

    if [ ! -e "/dev/fb0" ]; then
        log_warn "/dev/fb0 not found."
        if [ -e "/dev/fb1" ]; then
            FB_DEVICE="/dev/fb1"
            log_info "Using /dev/fb1 as primary framebuffer."
        fi
        return
    fi

    # Blank-frame detection: try xxd -> hexdump -> python
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
import sys
try:
    d = open('/dev/fb0','rb').read(64)
    print(1 if d == b'\\x00'*len(d) else 0)
except:
    print(0)
" 2>/dev/null || echo 0)
    fi

    if [ "$blank" = "1" ] && [ -e "/dev/fb1" ]; then
        log_warn "/dev/fb0 is blank (HiSilicon?) — switching to /dev/fb1."
        FB_DEVICE="/dev/fb1"
    fi

    log_info "Selected framebuffer: $FB_DEVICE"
}

# Sanitize path: allow only safe characters (prevents injection).
sanitize_path() {
    echo "$1" | tr -cd 'a-zA-Z0-9/_.-'
}

# ── File installation ─────────────────────────────────────────────────────────
# Downloads plugin from GitHub raw or falls back to ZIP archive.
download_plugin() {
    log_section "Downloading Plugin Files"
    mkdir -p "$TMP_DIR"

    # File manifest — all paths relative to E2ScreenRecorder/ in repo
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

    # Choose downloader
    if command -v wget >/dev/null 2>&1; then
        DLCMD="wget -q -O"
    elif command -v curl >/dev/null 2>&1; then
        DLCMD="curl -sSL -o"
    else
        abort "Neither wget nor curl is available. Cannot download plugin."
    fi

    failed=0
    for f in $FILES; do
        dest="$INSTALL_DIR/$f"
        destdir=$(dirname "$dest")
        mkdir -p "$destdir"
        url="${GITHUB_RAW}/E2ScreenRecorder/${f}"
        log_info "  → $f"
        $DLCMD "$dest" "$url" 2>>"$LOG_FILE" || {
            log_warn "    Failed to download $f"
            failed=$((failed + 1))
        }
    done

    if [ "$failed" -gt 5 ]; then
        log_warn "Too many download failures ($failed). Trying ZIP fallback..."
        download_via_zip
    fi
}

# ZIP fallback: download full archive and extract in one shot.
download_via_zip() {
    log_info "Downloading ZIP archive from GitHub..."
    zip_path="$TMP_DIR/e2sr_main.zip"

    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$zip_path" "$GITHUB_ZIP" || abort "ZIP download failed."
    else
        curl -sSL -o "$zip_path" "$GITHUB_ZIP" || abort "ZIP download failed."
    fi

    if command -v unzip >/dev/null 2>&1; then
        unzip -q "$zip_path" -d "$TMP_DIR/" || abort "unzip failed."
        src="$TMP_DIR/E2ScreenRecorder-main/E2ScreenRecorder"
        if [ -d "$src" ]; then
            mkdir -p "$INSTALL_DIR"
            cp -r "$src/." "$INSTALL_DIR/"
            log_info "Extracted from ZIP archive."
        else
            abort "Expected directory $src not found in ZIP."
        fi
    else
        abort "unzip not available — cannot extract ZIP fallback."
    fi
}

# Set correct permissions on installed files.
set_permissions() {
    log_info "Setting permissions (755)..."
    chmod -R 755 "$INSTALL_DIR" 2>/dev/null || \
        log_warn "chmod failed — continuing anyway."
    # Ensure Python files are executable
    find "$INSTALL_DIR" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
    # Ensure directories are executable/traversable
    find "$INSTALL_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
}

# ── Post-install patching ─────────────────────────────────────────────────────
# Patch framebuffer path in core/framebuffer.py if /dev/fb1 was selected.
patch_fb_device() {
    FB_SAFE=$(sanitize_path "$FB_DEVICE")
    if [ "$FB_SAFE" != "/dev/fb0" ]; then
        log_info "Patching framebuffer path to $FB_SAFE in framebuffer.py"
        $PY_BIN -c "
import sys
path = sys.argv[1]
safe = sys.argv[2]
try:
    with open(path, 'r') as fh: content = fh.read()
    content = content.replace('/dev/fb0', safe)
    with open(path, 'w') as fh: fh.write(content)
    print('Patched OK')
except Exception as e:
    print('Patch failed: ' + str(e))
    sys.exit(1)
" "$INSTALL_DIR/core/framebuffer.py" "$FB_SAFE" 2>>"$LOG_FILE" || \
            log_warn "Could not patch framebuffer path — defaulting to /dev/fb0."
    fi
}

# Compile .pyc files where possible to speed up first load.
compile_python() {
    log_info "Compiling Python bytecode..."
    $PY_BIN -m compileall -q "$INSTALL_DIR" 2>>"$LOG_FILE" || \
        log_warn "compileall had warnings — not critical."
}

# ── Restart Enigma2 ───────────────────────────────────────────────────────────
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

# ── Cleanup ────────────────────────────────────────────────────────────────────
cleanup_tmp() {
    rm -rf "$TMP_DIR" 2>/dev/null || true
}

# ── INSTALL ───────────────────────────────────────────────────────────────────
do_install() {
    log_section "E2ScreenRecorder Installer v2.0.0"
    acquire_lock
    trap 'release_lock; cleanup_tmp' EXIT

    detect_image
    detect_python
    detect_arch
    preinstall_check
    install_deps
    detect_framebuffer
    download_plugin
    set_permissions
    patch_fb_device
    compile_python
    restart_enigma2

    log_section "Installation Complete"
    log_info "Plugin installed at : $INSTALL_DIR"
    log_info "Image detected      : $IMAGE_NAME"
    log_info "Python              : $PY_BIN (v$PY_VER)"
    log_info "Architecture        : $ARCH"
    log_info "Framebuffer         : $FB_DEVICE"
    log_info "WebIF default port  : 8765"
    log_info "Log file            : $LOG_FILE"
    printf "${C_GREEN}[OK] E2ScreenRecorder is installed. Enjoy!${C_RESET}\n"
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

    log_info "Stopping Enigma2..."
    stop_enigma2

    log_info "Removing plugin files..."
    remove_plugin_files

    # Remove opkg-installed package record if present
    if command -v opkg >/dev/null 2>&1; then
        opkg remove enigma2-plugin-extensions-e2screenrecorder 2>/dev/null || true
    fi

    restart_enigma2

    log_section "Uninstall Complete"
    printf "${C_GREEN}[OK] E2ScreenRecorder has been removed.${C_RESET}\n"
}

# ── UPDATE ────────────────────────────────────────────────────────────────────
# Pulls latest version from GitHub and reinstalls without touching settings.
do_update() {
    log_section "E2ScreenRecorder Updater"

    # Backup config if it exists
    cfg_src="/etc/enigma2/E2ScreenRecorder.conf"
    cfg_bak="/tmp/e2sr_config_backup"
    if [ -f "$cfg_src" ]; then
        cp "$cfg_src" "$cfg_bak" 2>/dev/null && \
            log_info "Config backed up to $cfg_bak"
    fi

    # Re-run install (preinstall_check will wipe old files)
    do_install

    # Restore config
    if [ -f "$cfg_bak" ]; then
        cp "$cfg_bak" "$cfg_src" 2>/dev/null && \
            log_info "Config restored from backup."
    fi

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
        exit 1
        ;;
esac
