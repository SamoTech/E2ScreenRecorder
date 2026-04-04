#!/bin/sh
# =============================================================================
# uninstall.sh - E2ScreenRecorder Plugin Uninstaller
# Author : Ossama Hashim <samo.hossam@gmail.com>
# Project: https://github.com/SamoTech/E2ScreenRecorder
#
# Usage (run directly on STB):
#   wget -q "--no-check-certificate" https://raw.githubusercontent.com/SamoTech/E2ScreenRecorder/main/uninstall.sh -O - | sh
# =============================================================================

PLUGIN_NAME="E2ScreenRecorder"

echo ""
echo "================================================"
echo "  E2ScreenRecorder Uninstaller"
echo "  Author: Ossama Hashim <samo.hossam@gmail.com>"
echo "================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Detect Enigma2 base path (same logic as install.sh)
# ---------------------------------------------------------------------------
if [ -d "/usr/lib/enigma2" ]; then
    BASE=""
elif [ -d "/media/hdd/ImageBoot" ]; then
    BASE=$(ls -d /media/hdd/ImageBoot/*/ 2>/dev/null | head -1 | sed 's|/$||')
    if [ -z "$BASE" ]; then
        echo "[ERROR] No ImageBoot image found"
        exit 1
    fi
    echo "[INFO] Detected ImageBoot path: $BASE"
else
    echo "[ERROR] Cannot find Enigma2 installation"
    exit 1
fi

DEST="$BASE/usr/lib/enigma2/python/Plugins/Extensions/$PLUGIN_NAME"

# ---------------------------------------------------------------------------
# 2. Remove plugin directory
# ---------------------------------------------------------------------------
if [ -d "$DEST" ]; then
    echo "[INFO] Removing: $DEST"
    rm -rf "$DEST"
    if [ $? -eq 0 ]; then
        echo "[OK] Plugin directory removed"
    else
        echo "[ERROR] Failed to remove $DEST — try: rm -rf \"$DEST\" manually"
        exit 1
    fi
else
    echo "[WARN] Plugin not found at: $DEST"
    echo "       (already uninstalled or installed to a different path)"
fi

# ---------------------------------------------------------------------------
# 3. Clean up log file
# ---------------------------------------------------------------------------
if [ -f "/tmp/E2ScreenRecorder.log" ]; then
    rm -f "/tmp/E2ScreenRecorder.log"
    echo "[OK] Removed log file: /tmp/E2ScreenRecorder.log"
fi

# ---------------------------------------------------------------------------
# 4. Done
# ---------------------------------------------------------------------------
echo ""
echo "================================================"
echo "  Uninstall Complete!"
echo "================================================"
echo ""
echo "  Restart Enigma2 to finish:"
echo "    killall -1 enigma2"
echo ""
