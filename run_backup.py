#!/usr/bin/env python
"""
Script helper para ejecutar el backup automáticamente
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from backup_certificados import crear_backup_certificados

# Crear backup sin interacción
crear_backup_certificados()
