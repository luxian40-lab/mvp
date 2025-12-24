#!/bin/bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Crear superusuario automáticamente si no existe
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@eki.com', 'Jul14n123')
    print('✅ Superusuario "admin" creado')
else:
    print('ℹ️ Superusuario "admin" ya existe')
EOF
