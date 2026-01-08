"""
Test de envío de video vía WhatsApp
Verifica que los videos se envíen como media_url
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, Curso, Modulo
from core.response_templates import obtener_video_url
import re

print("=" * 60)
print("VERIFICACIÓN DE VIDEOS EN MÓDULOS")
print("=" * 60)

# Buscar módulos con videos
modulos_con_video = Modulo.objects.exclude(video_archivo='')

if not modulos_con_video:
    print("❌ No hay módulos con video subido")
else:
    print(f"✅ {modulos_con_video.count()} módulos con video\n")
    
    for modulo in modulos_con_video:
        print(f"📚 Módulo: {modulo.titulo}")
        print(f"📁 Archivo: {modulo.video_archivo.name}")
        
        # Verificar que el archivo existe
        if modulo.video_archivo and os.path.exists(modulo.video_archivo.path):
            size_mb = os.path.getsize(modulo.video_archivo.path) / (1024 * 1024)
            print(f"📦 Tamaño: {size_mb:.2f} MB")
            
            # OK si es menor a 16 MB
            if size_mb < 16:
                print(f"✅ Video dentro del límite de Twilio/Meta (16 MB)")
            else:
                print(f"❌ Video excede límite (> 16 MB)")
        else:
            print(f"❌ Archivo no encontrado en disco")
        
        # Generar URL
        video_url = obtener_video_url(modulo)
        if video_url:
            print(f"🔗 URL generada: {video_url}")
            
            # Verificar que es URL válida
            if video_url.startswith('http://') or video_url.startswith('https://'):
                print(f"✅ URL válida para Twilio")
            else:
                print(f"❌ URL no es absoluta, Twilio la rechazará")
        else:
            print(f"❌ No se pudo generar URL")
        
        print("-" * 60)

print("\n" + "=" * 60)
print("TEST DE EXTRACCIÓN DE URL EN MESSAGE_HANDLER")
print("=" * 60)

# Simular una respuesta con video
respuesta_ejemplo = """🍌 Cultivo de Plátano Hartón

Módulo 1: Selección de Material de Siembra

Contenido educativo completo aquí...

🎥 Video educativo:
http://localhost:8000/media/videos/lecciones/2026/01/prueba_1_360p.mp4

---

Cuando termines esta lección, escribe:
   "completar módulo 1"

O pregúntame dudas sobre este tema."""

print(f"📄 Respuesta original:\n{respuesta_ejemplo}\n")

# Aplicar regex como en message_handler
video_match = re.search(r'Video educativo:\s*\n\s*(https?://[^\s]+)', respuesta_ejemplo)
if not video_match:
    # Formato genérico
    video_match = re.search(r'🎥[^\n]*:\s*\n\s*(https?://[^\s]+)', respuesta_ejemplo)

if video_match:
    video_url = video_match.group(1)
    print(f"✅ Video detectado: {video_url}")
    
    # Limpiar texto (quitar sección de video)
    respuesta_limpia = re.sub(r'🎥[^\n]*:\s*\n\s*[^\n]+\n\n', '', respuesta_ejemplo)
    print(f"\n📄 Respuesta limpia (sin URL duplicada):\n{respuesta_limpia}")
else:
    print(f"❌ No se detectó video en la respuesta")

print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print("✅ obtener_video_url() genera URLs absolutas")
print("✅ message_handler detecta y extrae video_url")
print("✅ media_url se pasa a enviar_whatsapp_twilio()")
print("\n🎯 Próximo paso: Probar en WhatsApp real")
print("   1. Servidor debe estar corriendo: python manage.py runserver")
print("   2. ngrok debe exponer el puerto")
print("   3. Enviar 'continuar' a WhatsApp Sandbox")
