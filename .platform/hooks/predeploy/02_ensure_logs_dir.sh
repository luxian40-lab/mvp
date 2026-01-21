#!/bin/bash
set -euo pipefail

# Additional safety: ensure logs dir exists with permissive ownership
# This runs in predeploy to create /var/app/current/logs before the app flips.
mkdir -p /var/app/current/logs
chown webapp:webapp /var/app/current/logs 2>/dev/null || true
chmod 755 /var/app/current/logs || true

exit 0
