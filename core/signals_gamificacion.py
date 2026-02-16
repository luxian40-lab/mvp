"""
Señales para integrar Gamificación con el sistema de cursos
Otorga puntos automáticamente cuando el estudiante completa módulos/cursos
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ModuloCompletado, ProgresoEstudiante
from .gamificacion import PerfilGamificacion, Badge, BadgeEstudiante
from .models_extras import ArchivoModulo
from .whatsapp_service import enviar_archivo_modulo_whatsapp
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ModuloCompletado)
def otorgar_puntos_por_modulo(sender, instance, created, **kwargs):
    """Otorga puntos cuando un estudiante completa un módulo"""
    if not created:
        return
    
    try:
        # Obtener o crear perfil de gamificación
        perfil, _ = PerfilGamificacion.objects.get_or_create(
            estudiante=instance.progreso.estudiante
        )
        # Otorgar puntos (50 puntos por módulo)
        subio_nivel = perfil.agregar_puntos(
            puntos=50,
            razon=f"Completó {instance.modulo.titulo}"
        )
        # Actualizar estadísticas
        perfil.modulos_completados += 1
        perfil.save()
        # Actualizar racha
        perfil.actualizar_racha()
        # Si subió de nivel, enviar notificación (opcional)
        if subio_nivel:
            logger.info(f"🎉 {perfil.estudiante.nombre} subió a nivel {perfil.nivel}!")
        logger.info(f"✅ {perfil.estudiante.nombre} ganó 50 puntos por completar módulo")

        # === ENVÍO AUTOMÁTICO DE ARCHIVOS MULTIMEDIA POR WHATSAPP ===
        estudiante = instance.progreso.estudiante
        modulo = instance.modulo
        telefono = estudiante.telefono
        archivos = ArchivoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')
        for archivo in archivos:
            try:
                resultado = enviar_archivo_modulo_whatsapp(telefono, archivo)
                if resultado.get('success'):
                    logger.info(f"[WhatsApp] Archivo '{archivo.titulo}' enviado a {telefono}")
                else:
                    logger.error(f"[WhatsApp] Error enviando '{archivo.titulo}' a {telefono}: {resultado.get('response')}")
            except Exception as e:
                logger.error(f"[WhatsApp] Excepción enviando '{archivo.titulo}' a {telefono}: {e}")

    except Exception as e:
        logger.error(f"❌ Error al otorgar puntos por módulo: {e}")


@receiver(post_save, sender=ProgresoEstudiante)
def otorgar_badge_por_curso_completado(sender, instance, **kwargs):
    """Otorga badge cuando un estudiante completa un curso"""
    if not instance.completado:
        return
    
    try:
        # Obtener perfil de gamificación
        perfil, _ = PerfilGamificacion.objects.get_or_create(
            estudiante=instance.estudiante
        )
        
        # Otorgar puntos bonus por completar curso (200 puntos)
        perfil.agregar_puntos(
            puntos=200,
            razon=f"Completó curso {instance.curso.nombre}"
        )
        
        # Buscar badge específico del curso
        try:
            badge_curso = Badge.objects.filter(
                tipo='CURSO',
                curso_requerido=instance.curso,
                activo=True
            ).first()
            if badge_curso:
                BadgeEstudiante.objects.get_or_create(
                    estudiante=instance.estudiante,
                    badge=badge_curso
                )
                logger.info(f"🏆 {instance.estudiante.nombre} obtuvo badge: {badge_curso.nombre}")
        except Exception:
            pass
        
        # Badge por cantidad de cursos completados
        cursos_completados = ProgresoEstudiante.objects.filter(
            estudiante=instance.estudiante,
            completado=True
        ).count()
        
        # Buscar badges por cantidad de cursos
        for badge in Badge.objects.filter(tipo='CURSO', valor_requerido__isnull=False, activo=True):
            if cursos_completados >= badge.valor_requerido:
                BadgeEstudiante.objects.get_or_create(
                    estudiante=instance.estudiante,
                    badge=badge
                )
        
        logger.info(f"🎉 {instance.estudiante.nombre} completó {instance.curso.nombre} - {cursos_completados} cursos totales")
        
    except Exception as e:
        logger.error(f"❌ Error al otorgar badge por curso: {e}")
