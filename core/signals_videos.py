"""
Signals para compresión automática de videos (sin bloqueo)
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from pathlib import Path
import subprocess
import logging
import threading

logger = logging.getLogger(__name__)


def comprimir_en_background(video_path, modulo_id):
    """Comprime video en background sin bloquear"""
    try:
        video_path = Path(video_path)
        
        if not video_path.exists():
            logger.warning(f"Video no encontrado: {video_path}")
            return
        
        size_mb = video_path.stat().st_size / (1024 * 1024)
        
        if size_mb <= 10:
            logger.info(f"Video ya pequeño: {video_path.name} ({size_mb:.2f} MB)")
            return
        
        logger.info(f"🎬 [BG] Comprimiendo: {video_path.name} ({size_mb:.2f} MB)")
        
        output_path = video_path.parent / f"{video_path.stem}_360p{video_path.suffix}"
        
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
            '-loglevel', 'error',  # Menos logs
            '-y',
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=300
        )
        
        final_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ [BG] Compresión exitosa: {size_mb:.2f}MB → {final_size_mb:.2f}MB")
        
        # Reemplazar original
        video_path.unlink()
        output_path.rename(video_path)
        
        logger.info(f"✅ [BG] Video reemplazado: {video_path.name}")
        
    except Exception as e:
        logger.error(f"❌ [BG] Error comprimiendo: {e}")


@receiver(post_save, sender='core.Modulo')
def comprimir_video_automaticamente(sender, instance, created, **kwargs):
    """
    Lanza compresión de video en background (NO BLOQUEA).
    """
    if not instance.video_archivo:
        return
    
    if not instance.video_archivo.path:
        return
    
    video_path = instance.video_archivo.path
    modulo_id = instance.id
    
    # Lanzar en thread separado para NO bloquear
    thread = threading.Thread(
        target=comprimir_en_background,
        args=(video_path, modulo_id),
        daemon=True
    )
    thread.start()
    logger.info(f"🚀 Compresión lanzada en background para módulo {modulo_id}")
