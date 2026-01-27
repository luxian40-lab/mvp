
#!/bin/bash
set -e
# Activate virtualenv if exists
VENV_ACTIVATE=$(ls /var/app/venv/*/bin/activate 2>/dev/null | head -n 1 || true)
if [ -n "$VENV_ACTIVATE" ] && [ -f "$VENV_ACTIVATE" ]; then
  . "$VENV_ACTIVATE"
fi

cd /var/app/current || exit 0
echo "Running migrations and collectstatic"
python manage.py migrate --noinput
python manage.py collectstatic --noinput
