#!/bin/sh
# =============================================================================
# install.sh - E2ScreenRecorder Plugin Installer
# Author : Ossama Hashim <samo.hossam@gmail.com>
# Project: https://github.com/SamoTech/E2ScreenRecorder
#
# Usage (run directly on STB — no ipk/deb needed):
#   wget -q "--no-check-certificate" https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/install.sh -O - | sh
#
# What it does:
#   1. Auto-detects Enigma2 install path (/usr/lib or ImageBoot)
#   2. Downloads all plugin files directly from GitHub
#   3. Prints restart command
# =============================================================================

PLUGIN_NAME="E2ScreenRecorder"
RAW_BASE="https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main"

echo ""
echo "================================================"
echo "  E2ScreenRecorder Installer"
echo "  Author: Ossama Hashim <samo.hossam@gmail.com>"
echo "================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Detect Enigma2 base path
# ---------------------------------------------------------------------------
if [ -d "/usr/lib/enigma2" ]; then
    BASE=""
    echo "[INFO] Detected standard Enigma2 installation"
elif [ -d "/media/hdd/ImageBoot" ]; then
    BASE=$(ls -d /media/hdd/ImageBoot/*/ 2>/dev/null | head -1 | sed 's|/$||')
    if [ -z "$BASE" ]; then
        echo "[ERROR] No ImageBoot image found in /media/hdd/ImageBoot"
        exit 1
    fi
    echo "[INFO] Detected ImageBoot path: $BASE"
else
    echo "[ERROR] Cannot find Enigma2 installation (tried /usr/lib/enigma2 and ImageBoot)"
    exit 1
fi

DEST="$BASE/usr/lib/enigma2/python/Plugins/Extensions/$PLUGIN_NAME"
echo "[INFO] Install destination: $DEST"
echo ""

# ---------------------------------------------------------------------------
# 2. Create directory structure
# ---------------------------------------------------------------------------
mkdir -p "$DEST"
mkdir -p "$DEST/core"
mkdir -p "$DEST/ui"
mkdir -p "$DEST/backends"
mkdir -p "$DEST/utils"
mkdir -p "$DEST/webif"
mkdir -p "$DEST/locale/ar/LC_MESSAGES"

# ---------------------------------------------------------------------------
# 3. Download all plugin files
# ---------------------------------------------------------------------------
download_file() {
    SRC_PATH="$1"
    DEST_PATH="$2"
    wget -q "--no-check-certificate" "$RAW_BASE/$SRC_PATH" -O "$DEST_PATH"
    if [ $? -eq 0 ]; then
        echo "[OK] $SRC_PATH"
    else
        echo "[ERROR] Failed to download: $SRC_PATH"
        exit 1
    fi
}

echo "--- Root files ---"
download_file "__init__.py"              "$DEST/__init__.py"
download_file "plugin.py"               "$DEST/plugin.py"
download_file "ScreenRecorderPlugin.py" "$DEST/ScreenRecorderPlugin.py"

echo ""
echo "--- core/ ---"
download_file "core/__init__.py"   "$DEST/core/__init__.py"
download_file "core/framebuffer.py" "$DEST/core/framebuffer.py"
download_file "core/converter.py"  "$DEST/core/converter.py"
download_file "core/encoder.py"    "$DEST/core/encoder.py"
download_file "core/recorder.py"   "$DEST/core/recorder.py"
download_file "core/storage.py"    "$DEST/core/storage.py"
download_file "core/compat.py"     "$DEST/core/compat.py"

echo ""
echo "--- ui/ ---"
download_file "ui/__init__.py"         "$DEST/ui/__init__.py"
download_file "ui/MainMenu.py"         "$DEST/ui/MainMenu.py"
download_file "ui/Preview.py"          "$DEST/ui/Preview.py"
download_file "ui/StatusBar.py"        "$DEST/ui/StatusBar.py"
download_file "ui/SettingsScreen.py"   "$DEST/ui/SettingsScreen.py"

echo ""
echo "--- backends/ ---"
download_file "backends/__init__.py"       "$DEST/backends/__init__.py"
download_file "backends/GrabberPPM.py"     "$DEST/backends/GrabberPPM.py"
download_file "backends/GrabberPIL.py"     "$DEST/backends/GrabberPIL.py"
download_file "backends/GrabberFFmpeg.py"  "$DEST/backends/GrabberFFmpeg.py"
download_file "backends/GrabberGstreamer.py" "$DEST/backends/GrabberGstreamer.py"
download_file "backends/GrabberOpenCV.py"  "$DEST/backends/GrabberOpenCV.py"

echo ""
echo "--- utils/ ---"
download_file "utils/__init__.py" "$DEST/utils/__init__.py"
download_file "utils/logger.py"   "$DEST/utils/logger.py"
download_file "utils/notify.py"   "$DEST/utils/notify.py"

echo ""
echo "--- webif/ ---"
download_file "webif/__init__.py" "$DEST/webif/__init__.py"
download_file "webif/server.py"   "$DEST/webif/server.py"

echo ""
echo "--- locale/ ---"
download_file "locale/ar/LC_MESSAGES/E2ScreenRecorder.po" \
    "$DEST/locale/ar/LC_MESSAGES/E2ScreenRecorder.po"

# ---------------------------------------------------------------------------
# 4. Set permissions
# ---------------------------------------------------------------------------
chmod -R 755 "$DEST"
echo ""
echo "[INFO] Permissions set on $DEST"

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------
echo ""
echo "================================================"
echo "  Installation Complete!"
echo "================================================"
echo ""
echo "  Plugin installed to:"
echo "    $DEST"
echo ""
echo "  Restart Enigma2 to activate:"
echo "    killall -1 enigma2"
echo ""
echo "  WebIF will be available at:"
echo "    http://<STB-IP>:8765/"
echo ""
echo "  To uninstall:"
echo "    wget -q \"--no-check-certificate\" $RAW_BASE/uninstall.sh -O - | sh"
echo ""
