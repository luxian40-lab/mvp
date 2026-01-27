#!/usr/bin/env python
"""
Script de verificación rápida antes de la demo
"""

import os
import django
import logging
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, Curso, Modulo, ProgresoEstudiante
from django.conf import settings

def verificar_sistema():
    try:
        print("=" * 60)
        print("✅ VERIFICACIÓN DEL SISTEMA EKI MVP")
        print("=" * 60)
        # 1. Base de datos
        print("\n📊 BASE DE DATOS:")
        estudiantes = Estudiante.objects.count()
        cursos = Curso.objects.count()
        modulos = Modulo.objects.count()
        progresos = ProgresoEstudiante.objects.count()
        print(f"   Estudiantes: {estudiantes}")
        print(f"   Cursos: {cursos}")
        print(f"   Módulos: {modulos}")
        print(f"   Progresos activos: {progresos}")
        if estudiantes == 0:
            print("   ⚠️  WARNING: No hay estudiantes de prueba")
        if cursos == 0:
            print("   ❌ ERROR: No hay cursos creados")
        else:
            print("   ✅ Datos OK")
        # 2. Cursos
        print("\n📚 CURSOS DISPONIBLES:")
        for curso in Curso.objects.all():
            modulos_curso = curso.modulos.count()
            print(f"   - {curso.nombre} ({modulos_curso} módulos)")
        # 3. Videos
        print("\n🎥 VIDEOS:")
        modulos_con_video = Modulo.objects.filter(video_url__isnull=False).exclude(video_url='')
        if modulos_con_video.exists():
            for modulo in modulos_con_video:
                size_mb = modulo.video_size / (1024 * 1024) if modulo.video_size else 0
                print(f"   ✅ {modulo.curso.nombre} - {modulo.titulo}")
                print(f"      Tamaño: {size_mb:.2f} MB")
                print(f"      URL: {modulo.video_url}")
        else:
            print("   ⚠️  No hay videos cargados")
        # 4. Configuración Twilio
        print("\n📱 CONFIGURACIÓN TWILIO:")
        print(f"   Account SID: {settings.TWILIO_ACCOUNT_SID[:10]}...")
        print(f"   Número WhatsApp: {settings.TWILIO_WHATSAPP_NUMBER}")
        logging.info("Verificación del sistema ejecutada correctamente.")
    except Exception as e:
        logging.exception("Error en la verificación del sistema")
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    verificar_sistema()
    
    # 5. OpenAI
    print("\n🤖 CONFIGURACIÓN IA:")
    if settings.OPENAI_API_KEY:
        print(f"   OpenAI: Configurado ({settings.OPENAI_API_KEY[:10]}...)")
    else:
        print("   ⚠️  OpenAI: No configurado")
    
    if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
        print(f"   Gemini: Configurado")
    else:
        print("   ⚠️  Gemini: No configurado")
    
    # 6. Archivos media
    print("\n📁 ARCHIVOS MEDIA:")
    media_root = settings.MEDIA_ROOT
    print(f"   MEDIA_ROOT: {media_root}")
    
    if os.path.exists(media_root):
        videos_dir = os.path.join(media_root, 'videos', 'lecciones')
        if os.path.exists(videos_dir):
            archivos = []
            for root, dirs, files in os.walk(videos_dir):
                for file in files:
                    if file.endswith(('.mp4', '.avi', '.mov', '.webm')):
                        full_path = os.path.join(root, file)
                        size = os.path.getsize(full_path)
                        size_mb = size / (1024 * 1024)
                        archivos.append((file, size_mb))
            
            if archivos:
                print(f"   ✅ {len(archivos)} archivo(s) de video encontrado(s):")
                for nombre, size in archivos:
                    print(f"      - {nombre} ({size:.2f} MB)")
            else:
                print("   ⚠️  No se encontraron archivos de video")
        else:
            print("   ⚠️  Directorio de videos no existe")
    else:
        print("   ❌ MEDIA_ROOT no existe")
    
    # 7. Resumen
    print("\n" + "=" * 60)
    print("📋 RESUMEN:")
    print("=" * 60)
    
    errores = []
    warnings = []
    
    if cursos == 0:
        errores.append("No hay cursos creados")
    if estudiantes == 0:
        warnings.append("No hay estudiantes de prueba")
    if not modulos_con_video.exists():
        warnings.append("No hay videos cargados")
    
    if errores:
        print("\n❌ ERRORES CRÍTICOS:")
        for error in errores:
            print(f"   - {error}")
        print("\n   🚨 SISTEMA NO LISTO PARA DEMO")
    elif warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   - {warning}")
        print("\n   ⚡ Sistema funcional pero con limitaciones")
    else:
        print("\n✅ SISTEMA 100% LISTO PARA DEMO")
    
    print("\n" + "=" * 60)
    print("💡 SIGUIENTE PASO:")
    print("   1. Iniciar servidor: python manage.py runserver")
    print("   2. Iniciar ngrok: ngrok http 8000")
    print("   3. Actualizar webhook en Twilio")
    print("=" * 60)

if __name__ == '__main__':
    verificar_sistema()
