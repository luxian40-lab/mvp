#!/bin/bash
# Fuentes sans para láminas Course Engine (Pillow drawtext / infográficas).
set -e
if command -v dnf >/dev/null 2>&1; then
  dnf install -y google-noto-sans-fonts dejavu-sans-fonts 2>/dev/null || true
elif command -v yum >/dev/null 2>&1; then
  yum install -y google-noto-sans-fonts dejavu-sans-fonts 2>/dev/null || true
fi
