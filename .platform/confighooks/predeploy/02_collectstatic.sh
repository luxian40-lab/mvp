#!/bin/bash
# Un setenv redeploya el zip de la app. staticfiles/ está en .gitignore,
# así que no viaja en el zip, y los hooks de aplicación no corren.
# Sin este paso el admin pide CSS y fuentes de Unfold que ya no existen.
set +e
echo "=== confighook collectstatic ==="
if compgen -G "/var/app/venv/*/bin/activate" > /dev/null; then
  # shellcheck disable=SC1090
  source /var/app/venv/*/bin/activate
fi
if [ -f /var/app/staging/manage.py ]; then
  cd /var/app/staging
elif [ -f /var/app/current/manage.py ]; then
  cd /var/app/current
else
  echo "manage.py no encontrado; se omite collectstatic"
  exit 0
fi
python manage.py collectstatic --noinput
echo "collectstatic exit=$?"
exit 0
