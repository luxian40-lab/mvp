#!/bin/bash
set -euo pipefail

# Ensure the application logs directory exists so Django's file handler can write to it
mkdir -p /var/app/current/logs
chmod 755 /var/app/current/logs || true

exit 0
