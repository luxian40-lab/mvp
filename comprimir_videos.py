"""
Compresor de videos para WhatsApp (máximo 10 MB @ 360p)
"""
import os
import sys
import subprocess
from pathlib import Path

def comprimir_video(input_path, output_path=None, target_size_mb=10):
    """
    Comprime video a 360p con tamaño máximo especificado.
    
    Args:
        input_path: Ruta del video original
        output_path: Ruta del video comprimido (opcional)
        target_size_mb: Tamaño máximo en MB (default 10)
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"❌ Archivo no encontrado: {input_path}")
        return None
    
    # Tamaño actual
    size_mb = input_path.stat().st_size / (1024 * 1024)
    print(f"📁 Archivo original: {size_mb:.2f} MB")
    
    if size_mb <= target_size_mb:
        print(f"✅ Video ya está por debajo de {target_size_mb} MB")
        return str(input_path)
    
    # Ruta de salida
    if not output_path:
        output_path = input_path.parent / f"{input_path.stem}_360p{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    print(f"\n🎬 Comprimiendo a 360p...")
    print(f"   Destino: {output_path}")
    
    # Calcular bitrate para alcanzar tamaño objetivo
    # Bitrate = (tamaño_objetivo_MB * 8192) / duración_segundos
    # Usamos 500k como seguro (aprox 2 min de video = 10 MB)
    
    # Comando ffmpeg
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-vf', 'scale=640:360',  # 360p
        '-c:v', 'libx264',        # Codec H.264
        '-b:v', '500k',           # Bitrate video 500 kbps
        '-maxrate', '600k',       # Bitrate máximo
        '-bufsize', '1200k',      # Buffer
        '-c:a', 'aac',            # Codec audio
        '-b:a', '96k',            # Bitrate audio 96 kbps
        '-movflags', '+faststart', # Optimizar para streaming
        '-preset', 'medium',      # Velocidad de compresión
        '-y',                     # Sobrescribir si existe
        str(output_path)
    ]
    
    try:
        # Ejecutar ffmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        # Verificar tamaño final
        final_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ Compresión exitosa!")
        print(f"   Tamaño original: {size_mb:.2f} MB")
        print(f"   Tamaño final: {final_size_mb:.2f} MB")
        print(f"   Reducción: {((size_mb - final_size_mb) / size_mb * 100):.1f}%")
        
        if final_size_mb > target_size_mb:
            print(f"\n⚠️ ADVERTENCIA: Video sigue siendo > {target_size_mb} MB")
            print(f"   Recomendación: Reducir duración del video")
        else:
            print(f"\n🎉 Video listo para WhatsApp!")
        
        return str(output_path)
        
    except FileNotFoundError:
        print("\n❌ ERROR: ffmpeg no está instalado")
        print("\n📥 Instalación:")
        print("   1. Descargar: https://ffmpeg.org/download.html")
        print("   2. O con chocolatey: choco install ffmpeg")
        print("   3. O con scoop: scoop install ffmpeg")
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR al comprimir: {e}")
        print(f"\nDetalles:\n{e.stderr}")
        return None


def comprimir_todos_videos_media():
    """Comprime todos los videos en media/videos/lecciones"""
    import django
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
    django.setup()
    
    from django.conf import settings
    
    videos_dir = settings.MEDIA_ROOT / 'videos' / 'lecciones'
    
    if not videos_dir.exists():
        print(f"❌ Carpeta no existe: {videos_dir}")
        return
    
    # Buscar todos los MP4
    videos = list(videos_dir.rglob('*.mp4')) + list(videos_dir.rglob('*.MP4'))
    
    if not videos:
        print(f"ℹ️ No hay videos en {videos_dir}")
        return
    
    print(f"\n📹 Encontrados {len(videos)} video(s)\n")
    
    for i, video in enumerate(videos, 1):
        # Saltar si ya está comprimido
        if '_360p' in video.stem:
            print(f"{i}. ⏭️ Ya comprimido: {video.name}")
            continue
        
        print(f"\n{i}. 🎬 {video.name}")
        print("="*60)
        
        output = video.parent / f"{video.stem}_360p{video.suffix}"
        comprimir_video(video, output)
        
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Modo: comprimir archivo específico
        video_path = sys.argv[1]
        comprimir_video(video_path)
    else:
        # Modo: comprimir todos los videos de media/
        print("="*60)
        print("🎥 COMPRESOR DE VIDEOS PARA WHATSAPP")
        print("="*60)
        comprimir_todos_videos_media()
