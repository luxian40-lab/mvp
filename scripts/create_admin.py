import os
import sys

# Ajusta el módulo de settings si tu proyecto usa otro nombre
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
sys.path.append(os.getcwd())

import django
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email = 'admin@example.com'
password = 'admin123'

if User.objects.filter(username=username).exists():
    print('admin_exists')
else:
    User.objects.create_superuser(username, email, password)
    print('admin_created')
