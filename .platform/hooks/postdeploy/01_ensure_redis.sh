#!/bin/bash
# Tras cada deploy: asegurar que Redis esté arriba antes de worker/beat.
set -e
if systemctl list-unit-files 2>/dev/null | grep -q '^redis6\.service'; then
  systemctl start redis6 || true
elif systemctl list-unit-files 2>/dev/null | grep -q '^redis\.service'; then
  systemctl start redis || true
fi
