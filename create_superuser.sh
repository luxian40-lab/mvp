#!/bin/bash
# Script para crear superusuario en Django

cd /var/app/current
source /var/app/venv/*/bin/activate

python manage.py shell << END
from django.contrib.auth.models import User
import os

username = 'admin'
email = 'admin@ekisolutions.com'
password = 'Eki@Admin2025'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✓ Superusuario '{username}' creado exitosamente")
    print(f"✓ Contraseña: {password}")
else:
    print(f"✓ El usuario '{username}' ya existe")
END
