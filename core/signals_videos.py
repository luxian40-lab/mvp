"""
Signals para compresión automática de videos
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='core.Modulo')
def comprimir_video_automaticamente(sender, instance, created, **kwargs):
    """
    Comprime videos automáticamente cuando se sube un módulo con video.
    """
    # Solo procesar si hay video_archivo
    if not instance.video_archivo:
        return
    
    # Solo procesar si el archivo existe
    if not instance.video_archivo.path:
        return
    
    video_path = Path(instance.video_archivo.path)
    
    # Si no existe el archivo, salir
    if not video_path.exists():
        return
    
    # Si ya está comprimido (nombre tiene _360p), salir
    if '_360p' in video_path.stem or '_compressed' in video_path.stem:
        logger.info(f"Video ya comprimido: {video_path.name}")
        return
    
    # Verificar tamaño
    size_mb = video_path.stat().st_size / (1024 * 1024)
    
    # Si es menor a 10 MB, no comprimir
    if size_mb <= 10:
        logger.info(f"Video {video_path.name} ya es pequeño ({size_mb:.2f} MB), no se comprime")
        return
    
    logger.info(f"🎬 Comprimiendo video: {video_path.name} ({size_mb:.2f} MB)")
    
    # Ruta temporal para video comprimido
    output_path = video_path.parent / f"{video_path.stem}_360p{video_path.suffix}"
    
    # Comando ffmpeg
    cmd = [
        'ffmpeg',
        '-i', str(video_path),
        '-vf', 'scale=640:360',
        '-c:v', 'libx264',
        '-b:v', '500k',
        '-maxrate', '600k',
        '-bufsize', '1200k',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-movflags', '+faststart',
        '-preset', 'medium',
        '-y',
        str(output_path)
    ]
    
    try:
        # Ejecutar compresión
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=300  # 5 minutos máximo
        )
        
        # Verificar tamaño final
        final_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Compresión exitosa: {size_mb:.2f} MB → {final_size_mb:.2f} MB")
        
        # Reemplazar archivo original por comprimido
        # Guardar nombre relativo antes de borrar
        from django.core.files import File
        
        # Borrar original
        video_path.unlink()
        
        # Actualizar campo con video comprimido
        with open(output_path, 'rb') as f:
            # Guardar con mismo nombre que tenía (sin _360p para que sea transparente)
            instance.video_archivo.save(
                video_path.name,  # Nombre original
                File(f),
                save=False  # No guardar aún para evitar loop
            )
        
        # Borrar temporal
        if output_path.exists():
            output_path.unlink()
        
        # Guardar sin disparar signal de nuevo
        post_save.disconnect(comprimir_video_automaticamente, sender=sender)
        instance.save(update_fields=['video_archivo'])
        post_save.connect(comprimir_video_automaticamente, sender=sender)
        
        logger.info(f"✅ Video reemplazado automáticamente")
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ Timeout al comprimir {video_path.name}")
        if output_path.exists():
            output_path.unlink()
            
    except FileNotFoundError:
        logger.error("❌ ffmpeg no está instalado")
        
    except Exception as e:
        logger.error(f"❌ Error al comprimir {video_path.name}: {e}")
        if output_path.exists():
            output_path.unlink()
