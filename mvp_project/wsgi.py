"""
WSGI config for mvp_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

# Ensure `logs` directory exists so file-based logging handlers won't fail on startup
BASE_DIR = Path(__file__).resolve().parent.parent
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

application = get_wsgi_application()
