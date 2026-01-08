"""
Script de prueba para verificar la funcionalidad de videos.

Uso:
    python test_video_funcionalidad.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from django.conf import settings
from core.response_templates import obtener_video_url


def verificar_configuracion():
    """Verifica que la configuración de videos esté correcta."""
    print("="*60)
    print("🎥 VERIFICACIÓN DE CONFIGURACIÓN DE VIDEOS")
    print("="*60)
    
    # 1. MEDIA_ROOT y MEDIA_URL
    print("\n1️⃣ Configuración Django:")
    print(f"   MEDIA_ROOT: {settings.MEDIA_ROOT}")
    print(f"   MEDIA_URL: {settings.MEDIA_URL}")
    
    if not settings.MEDIA_ROOT:
        print("   ❌ ERROR: MEDIA_ROOT no configurado")
        return False
    
    if not settings.MEDIA_URL:
        print("   ❌ ERROR: MEDIA_URL no configurado")
        return False
    
    print("   ✅ Configuración correcta")
    
    # 2. Carpeta media existe
    print("\n2️⃣ Estructura de carpetas:")
    if settings.MEDIA_ROOT.exists():
        print(f"   ✅ {settings.MEDIA_ROOT} existe")
    else:
        print(f"   ⚠️ Creando carpeta: {settings.MEDIA_ROOT}")
        settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    
    videos_dir = settings.MEDIA_ROOT / 'videos' / 'lecciones'
    if videos_dir.exists():
        print(f"   ✅ {videos_dir} existe")
    else:
        print(f"   ⚠️ Creando carpeta: {videos_dir}")
        videos_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Función obtener_video_url
    print("\n3️⃣ Función obtener_video_url:")
    try:
        from core.response_templates import obtener_video_url
        print("   ✅ Función importada correctamente")
    except ImportError as e:
        print(f"   ❌ ERROR importando: {e}")
        return False
    
    # 4. Función enviar_whatsapp_twilio con media_url
    print("\n4️⃣ Función enviar_whatsapp_twilio:")
    try:
        from core.utils import enviar_whatsapp_twilio
        import inspect
        sig = inspect.signature(enviar_whatsapp_twilio)
        params = list(sig.parameters.keys())
        print(f"   Parámetros: {params}")
        
        if 'media_url' in params:
            print("   ✅ Parámetro 'media_url' presente")
        else:
            print("   ❌ ERROR: Parámetro 'media_url' NO encontrado")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # 5. Modelo Modulo tiene campos de video
    print("\n5️⃣ Modelo Modulo:")
    try:
        from core.models import Modulo
        
        campos = [f.name for f in Modulo._meta.get_fields()]
        
        if 'video_archivo' in campos:
            print("   ✅ Campo 'video_archivo' existe")
        else:
            print("   ❌ ERROR: Campo 'video_archivo' NO existe")
            return False
        
        if 'video_resolucion' in campos:
            print("   ✅ Campo 'video_resolucion' existe")
        else:
            print("   ⚠️ AVISO: Campo 'video_resolucion' NO existe")
        
        if 'video_url' in campos:
            print("   ✅ Campo 'video_url' existe")
        else:
            print("   ⚠️ AVISO: Campo 'video_url' NO existe")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    return True


def verificar_lecciones_con_video():
    """Verifica si hay módulos con videos."""
    print("\n6️⃣ Módulos con videos:")
    try:
        from core.models import Modulo
        
        modulos_con_archivo = Modulo.objects.exclude(video_archivo='').count()
        modulos_con_url = Modulo.objects.exclude(video_url='').count()
        
        print(f"   📹 Módulos con video_archivo: {modulos_con_archivo}")
        print(f"   🔗 Módulos con video_url: {modulos_con_url}")
        
        if modulos_con_archivo > 0:
            print("\n   📋 Módulos con archivos:")
            for modulo in Modulo.objects.exclude(video_archivo='')[:5]:
                video_url = obtener_video_url(modulo)
                print(f"      - {modulo.titulo}: {video_url}")
        
        if modulos_con_url > 0:
            print("\n   📋 Módulos con URLs:")
            for modulo in Modulo.objects.exclude(video_url='')[:5]:
                print(f"      - {modulo.titulo}: {modulo.video_url}")
        
        if modulos_con_archivo == 0 and modulos_con_url == 0:
            print("   ℹ️ No hay módulos con videos todavía")
            print("   💡 Sube un video en Admin → Módulos")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    return True


def main():
    """Ejecuta todas las verificaciones."""
    try:
        if not verificar_configuracion():
            print("\n❌ Configuración incompleta - revisa los errores arriba")
            return
        
        verificar_lecciones_con_video()
        
        print("\n" + "="*60)
        print("✅ VERIFICACIÓN COMPLETA")
        print("="*60)
        print("\n💡 Próximos pasos:")
        print("   1. Subir video de prueba en Admin → Módulos")
        print("   2. Probar 'continuar' por WhatsApp")
        print("   3. Verificar que aparece el link del video")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
