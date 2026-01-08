#!/usr/bin/env python
"""
Asociar video existente al módulo 1 de Plátano
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo
from django.conf import settings

# Buscar el módulo 1 de Plátano
curso_platano = Curso.objects.filter(nombre__icontains='plátano').first()

if not curso_platano:
    print("❌ No se encontró el curso de Plátano")
    exit(1)

modulo_1 = curso_platano.modulos.filter(numero=1).first()

if not modulo_1:
    print("❌ No se encontró el módulo 1 del curso de Plátano")
    exit(1)

# Video que existe
video_path = 'videos/lecciones/2026/01/prueba_1_8nbpnCI.mp4'
video_full_path = os.path.join(settings.MEDIA_ROOT, video_path)

if not os.path.exists(video_full_path):
    print(f"❌ El archivo de video no existe: {video_full_path}")
    exit(1)

# Asociar video al módulo
modulo_1.video_url = video_path
modulo_1.video_size = os.path.getsize(video_full_path)
modulo_1.save()

print("✅ Video asociado correctamente al módulo 1 de Plátano Hartón")
print(f"   Módulo: {modulo_1.titulo}")
print(f"   Video: {video_path}")
print(f"   Tamaño: {modulo_1.video_size / (1024*1024):.2f} MB")
