#!/usr/bin/env bash
# =============================================================================
# build.sh — E2ScreenRecorder ipk builder
# Author : Ossama Hashim <samo.hossam@gmail.com>
# Project: https://github.com/SamoTech/E2ScreenRecorder
# Usage  : bash build.sh [VERSION]
#   e.g.   bash build.sh 1.0.1
# Requires: fakeroot, dpkg-deb (apt install fakeroot dpkg)
# =============================================================================
set -euo pipefail

PLUGIN_NAME="enigma2-plugin-extensions-e2screenrecorder"
VERSION="${1:-1.0.0}"
ARCH="all"
BUILD_DIR="./build/${PLUGIN_NAME}_${VERSION}"
INSTALL_DIR="${BUILD_DIR}/usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder"
OUT_IPK="./${PLUGIN_NAME}_${VERSION}_${ARCH}.ipk"

echo "╔══════════════════════════════════════════════════╗"
echo "║  E2ScreenRecorder ipk Builder  v${VERSION}       "
echo "║  Maintainer: samo.hossam@gmail.com               "
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Clean ──────────────────────────────────────────────────────────────────
echo "[1/5] Cleaning build directory..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/CONTROL"
mkdir -p "${INSTALL_DIR}"

# ── Copy source ────────────────────────────────────────────────────────────
echo "[2/5] Copying plugin source..."
cp -r E2ScreenRecorder/* "${INSTALL_DIR}/"

# Remove any stale .pyc / __pycache__ before recompile
find "${INSTALL_DIR}" -name '*.pyc' -delete 2>/dev/null || true
find "${INSTALL_DIR}" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# ── CONTROL file ───────────────────────────────────────────────────────────
echo "[3/5] Writing CONTROL/control..."
cat > "${BUILD_DIR}/CONTROL/control" << EOF
Package: ${PLUGIN_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Section: extra
Priority: optional
Maintainer: Ossama Hashim <samo.hossam@gmail.com>
Description: E2ScreenRecorder - Screenshot & Video Capture for all Enigma2 STBs
 Captures /dev/fb0 on all STB SoC families (BCM, HiSilicon, Amlogic, STi).
 PNG/JPEG/BMP screenshots, MP4/AVI video, built-in WebIF on port 8765.
 Python 2.7-3.12+ compatible. Zero mandatory dependencies.
Depends: enigma2
Recommends: python3-pillow | python-imaging, ffmpeg
EOF

# ── Compile .pyc ───────────────────────────────────────────────────────────
echo "[4/5] Compiling .pyc files (Python 3)..."
python3 -m compileall -q "${INSTALL_DIR}" 2>/dev/null || true

# ── Build ipk ──────────────────────────────────────────────────────────────
echo "[5/5] Building ipk package..."
fakeroot dpkg-deb --build "${BUILD_DIR}" "${OUT_IPK}"

echo ""
echo "══════════════════════════════════════════════════"
echo "  [✓] Built: ${OUT_IPK}"
echo ""
echo "  Install on STB:"
echo "    opkg install ${OUT_IPK}"
echo ""
echo "  Or copy manually:"
echo "    scp ${OUT_IPK} root@<STB-IP>:/tmp/"
echo "    ssh root@<STB-IP> 'opkg install /tmp/$(basename ${OUT_IPK})'"
echo "══════════════════════════════════════════════════"
