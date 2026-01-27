#!/bin/sh
set -e
LOGFILE=/tmp/pip-install.log
echo "Trying strict install from requirements.docker.txt" > "$LOGFILE"
if pip install --no-cache-dir -r requirements.docker.txt >> "$LOGFILE" 2>&1; then
  echo "Installed from requirements.docker.txt" >> "$LOGFILE"
  exit 0
else
  echo "Strict install failed, see $LOGFILE" >&2
  echo "Falling back to loose requirements (requirements.loose.txt)" >> "$LOGFILE"
  if [ -f requirements.loose.txt ]; then
    if pip install --no-cache-dir -r requirements.loose.txt >> "$LOGFILE" 2>&1; then
      echo "Installed from requirements.loose.txt" >> "$LOGFILE"
      exit 0
    else
      echo "Loose install also failed, inspect $LOGFILE" >&2
      cat "$LOGFILE" >&2
      exit 1
    fi
  else
    echo "requirements.loose.txt not found" >> "$LOGFILE"
    cat "$LOGFILE" >&2
    exit 1
  fi
fi
