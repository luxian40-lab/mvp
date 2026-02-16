"""
Señales para actualizar automáticamente la base de conocimientos
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import Curso, Modulo
from .base_conocimientos import actualizar_base_conocimientos

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Curso)
def curso_actualizado(sender, instance, created, **kwargs):
    """Actualiza la base de conocimientos cuando se crea o modifica un curso"""
    accion = "creado" if created else "actualizado"
    logger.info(f"📚 Curso {accion}: {instance.nombre} - Actualizando base de conocimientos...")
    try:
        actualizar_base_conocimientos()
        logger.info("✅ Base de conocimientos actualizada")
    except Exception as e:
        logger.error(f"❌ Error actualizando base de conocimientos: {e}")


@receiver(post_delete, sender=Curso)
def curso_eliminado(sender, instance, **kwargs):
    """Actualiza la base de conocimientos cuando se elimina un curso"""
    logger.info(f"🗑️ Curso eliminado: {instance.nombre} - Actualizando base de conocimientos...")
    try:
        actualizar_base_conocimientos()
        logger.info("✅ Base de conocimientos actualizada")
    except Exception as e:
        logger.error(f"❌ Error actualizando base de conocimientos: {e}")


@receiver(post_save, sender=Modulo)
def modulo_actualizado(sender, instance, created, **kwargs):
    """Actualiza la base de conocimientos cuando se crea o modifica un módulo"""
    accion = "creado" if created else "actualizado"
    logger.info(f"📖 Módulo {accion}: {instance.titulo} - Actualizando base de conocimientos...")
    try:
        actualizar_base_conocimientos()
        logger.info("✅ Base de conocimientos actualizada")
    except Exception as e:
        logger.error(f"❌ Error actualizando base de conocimientos: {e}")


@receiver(post_delete, sender=Modulo)
def modulo_eliminado(sender, instance, **kwargs):
    """Actualiza la base de conocimientos cuando se elimina un módulo"""
    logger.info(f"🗑️ Módulo eliminado: {instance.titulo} - Actualizando base de conocimientos...")
    try:
        actualizar_base_conocimientos()
        logger.info("✅ Base de conocimientos actualizada")
    except Exception as e:
        logger.error(f"❌ Error actualizando base de conocimientos: {e}")
