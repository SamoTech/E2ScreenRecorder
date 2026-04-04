#!/bin/bash
# build.sh — builds enigma2-plugin-extensions-e2screenrecorder_1.0.0_all.ipk

set -e

PLUGIN_NAME="enigma2-plugin-extensions-e2screenrecorder"
VERSION="1.0.0"
ARCH="all"
BUILD_DIR="./build/${PLUGIN_NAME}_${VERSION}"
INSTALL_DIR="${BUILD_DIR}/usr/lib/enigma2/python/Plugins/Extensions/E2ScreenRecorder"

echo "[*] Cleaning build dir..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/CONTROL"
mkdir -p "${INSTALL_DIR}"

echo "[*] Copying plugin source..."
cp -r E2ScreenRecorder/* "${INSTALL_DIR}/"

echo "[*] Writing CONTROL/control..."
cat > "${BUILD_DIR}/CONTROL/control" << EOF
Package: ${PLUGIN_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Section: extra
Priority: optional
Maintainer: Ossama Hashim <samo.hossam@gmail.com>
Description: E2ScreenRecorder - Screenshot & Video Capture for all Enigma2 STBs
 Captures /dev/fb0 on all STB SoC families (BCM, HiSilicon, Amlogic, STi).
 PNG/JPEG/BMP screenshots, MP4/AVI video, built-in WebIF.
 Python 2.7-3.12+ compatible. Zero mandatory dependencies.
Depends: enigma2
Recommends: python3-pillow | python-imaging, ffmpeg
EOF

echo "[*] Compiling .pyc files (py3)..."
python3 -m compileall "${INSTALL_DIR}" 2>/dev/null || true

echo "[*] Building ipk..."
fakeroot dpkg-deb --build "${BUILD_DIR}" \
  "./${PLUGIN_NAME}_${VERSION}_${ARCH}.ipk"

echo ""
echo "[\u2713] Built: ${PLUGIN_NAME}_${VERSION}_${ARCH}.ipk"
echo "    Install on STB:"
echo "    opkg install ${PLUGIN_NAME}_${VERSION}_${ARCH}.ipk"
