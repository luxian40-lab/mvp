"""
Script para verificar videos en módulos
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Modulo
from django.conf import settings

print("="*60)
print("🎥 VERIFICANDO VIDEOS EN MÓDULOS")
print("="*60)

# Ver módulos con videos
modulos_con_video = Modulo.objects.exclude(video_archivo='').exclude(video_archivo__isnull=True)
print(f"\n📹 Módulos con video_archivo: {modulos_con_video.count()}")

if modulos_con_video.count() == 0:
    print("\n❌ No hay módulos con videos")
    print("💡 Ve a http://localhost:8000/admin/core/modulo/")
    print("   Edita un módulo → Sección 'Multimedia' → Sube MP4")
else:
    for m in modulos_con_video:
        print(f"\n{m.curso.emoji} {m.titulo}")
        print(f"  📁 Archivo: {m.video_archivo.name if m.video_archivo else 'None'}")
        print(f"  📺 Resolución: {m.video_resolucion}")
        
        # Generar URL
        if m.video_archivo:
            url = f"{settings.MEDIA_URL}{m.video_archivo.name}"
            print(f"  🌐 URL: {url}")
            
            # Verificar archivo físico existe
            ruta_completa = settings.MEDIA_ROOT / m.video_archivo.name
            if ruta_completa.exists():
                tamanio_mb = ruta_completa.stat().st_size / (1024*1024)
                print(f"  ✅ Archivo existe: {tamanio_mb:.2f} MB")
            else:
                print(f"  ❌ Archivo NO existe en: {ruta_completa}")

print("\n" + "="*60)
