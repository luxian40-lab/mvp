#!/bin/bash
# Install static ffmpeg/ffprobe on AL2023 when dnf packages are unavailable.
# Required so admin upload re-encodes to H.264 Main + AAC (WhatsApp 63021).
set -euo pipefail

if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "ffmpeg already present: $(command -v ffmpeg)"
  ffmpeg -version | head -1 || true
  exit 0
fi

ARCH=$(uname -m)
case "$ARCH" in
  x86_64|amd64) ASSET="ffmpeg-release-amd64-static.tar.xz" ;;
  aarch64|arm64) ASSET="ffmpeg-release-arm64-static.tar.xz" ;;
  *)
    echo "Unsupported arch for static ffmpeg: $ARCH"
    exit 0
    ;;
esac

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
URL="https://johnvansickle.com/ffmpeg/releases/${ASSET}"
echo "Downloading $URL"
curl -fsSL -o "$TMP/ffmpeg.tar.xz" "$URL"
tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP"
BIN_DIR=$(find "$TMP" -maxdepth 1 -type d -name 'ffmpeg-*-static' | head -1)
if [ -z "$BIN_DIR" ] || [ ! -x "$BIN_DIR/ffmpeg" ]; then
  echo "ffmpeg static extract failed"
  exit 1
fi

sudo install -m 755 "$BIN_DIR/ffmpeg" /usr/local/bin/ffmpeg
sudo install -m 755 "$BIN_DIR/ffprobe" /usr/local/bin/ffprobe
echo "Installed:"
/usr/local/bin/ffmpeg -version | head -1
/usr/local/bin/ffprobe -version | head -1
