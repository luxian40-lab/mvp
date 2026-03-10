"""
Señales para integrar Gamificación con el sistema de cursos
Otorga puntos automáticamente cuando el estudiante completa módulos/cursos
+ Anti-abuse IA reset + Email notificación a org admin
+ Integración con Celery para envíos asíncronos
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ModuloCompletado, ProgresoEstudiante
from .gamificacion import PerfilGamificacion, Badge, BadgeEstudiante
# ArchivoModulo y enviar_archivo_modulo_whatsapp ya NO se usan aquí (v1.9.3)
# Los videos se envían via MULTI_MSG en response_templates.py / views.py
import logging

logger = logging.getLogger(__name__)


def _celery_disponible():
    """Verifica si Celery está disponible y configurado."""
    try:
        from django.conf import settings
        return not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
    except Exception:
        return False


def _notificar_org_admin(estudiante, asunto, mensaje_html):
    """Enviar email al admin de la organización del estudiante (async si Celery disponible)."""
    try:
        if _celery_disponible():
            from core.tasks import enviar_email_org_admin_async
            enviar_email_org_admin_async.delay(estudiante.id, asunto, mensaje_html)
            logger.info(f"📧 Email encolado en Celery para {estudiante.cliente.email if estudiante.cliente else 'N/A'}: {asunto}")
            return

        # Fallback síncrono
        from django.core.mail import send_mail
        from django.conf import settings
        cliente = estudiante.cliente
        if not cliente or not getattr(cliente, 'email', None):
            return
        send_mail(
            subject=f"[eki] {asunto}",
            message='',
            html_message=mensaje_html,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@eki.com',
            recipient_list=[cliente.email],
            fail_silently=True,
        )
        logger.info(f"📧 Email enviado (sync) a {cliente.email}: {asunto}")
    except Exception as e:
        logger.warning(f"📧 No se pudo enviar email al admin: {e}")


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
        # v1.9.8: Puntos reducidos (10 por módulo) para balance real
        subio_nivel = perfil.agregar_puntos(
            puntos=10,
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
            # Auto-assign level badge
            _asignar_badge_nivel(perfil)
            # Si nivel máximo (10) → notificar org admin
            if perfil.nivel >= 10:
                _notificar_org_admin(
                    perfil.estudiante,
                    f"🏆 {perfil.estudiante.nombre} alcanzó nivel máximo",
                    f"<p>El estudiante <strong>{perfil.estudiante.nombre}</strong> "
                    f"ha alcanzado el <strong>nivel {perfil.nivel} (Leyenda del Campo)</strong> "
                    f"con {perfil.puntos_totales} puntos.</p>"
                )
        logger.info(f"✅ {perfil.estudiante.nombre} ganó 10 puntos por completar módulo")

        # === RESET ANTI-ABUSE IA (preguntas_ia_restantes) ===
        estudiante = instance.progreso.estudiante
        if hasattr(estudiante, 'preguntas_ia_restantes'):
            estudiante.preguntas_ia_restantes = 3
            estudiante.save(update_fields=['preguntas_ia_restantes'])
            logger.info(f"🔄 Reset preguntas_ia_restantes=3 para {estudiante.nombre}")

        # === ENVÍO AUTOMÁTICO DE ARCHIVOS MULTIMEDIA POR WHATSAPP ===
        # ⛔ DESACTIVADO v1.9.3: Los videos ya se envían dentro del [MULTI_MSG]
        # en response_templates.py y views.py. Este envío DUPLICABA los videos
        # porque el signal enviaba archivos del módulo completado (ya vistos)
        # ANTES de que el MULTI_MSG enviara el contenido del siguiente módulo.
        # Resultado: el estudiante veía videos duplicados y "escribe listo"
        # aparecía entre los videos del signal y los del MULTI_MSG.
        logger.info(f"📋 Signal: módulo completado por {instance.progreso.estudiante.nombre} - videos se envían via MULTI_MSG (no signal)")

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
        
        # v1.9.8: Puntos reducidos (15 por curso) para balance real
        perfil.agregar_puntos(
            puntos=15,
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

        # Notificar org admin del logro
        _notificar_org_admin(
            instance.estudiante,
            f"📜 {instance.estudiante.nombre} completó {instance.curso.nombre}",
            f"<p>El estudiante <strong>{instance.estudiante.nombre}</strong> "
            f"(cédula: {instance.estudiante.cedula}) ha completado exitosamente "
            f"el curso <strong>{instance.curso.nombre}</strong>.</p>"
            f"<p>Cursos completados en total: <strong>{cursos_completados}</strong></p>"
        )

    except Exception as e:
        logger.error(f"❌ Error al otorgar badge por curso: {e}")


def _asignar_badge_nivel(perfil):
    """Auto-assign badge por nivel alcanzado."""
    try:
        badge_nivel = Badge.objects.filter(
            tipo='NIVEL',
            valor_requerido__lte=perfil.nivel,
            activo=True
        ).order_by('-valor_requerido').first()
        if badge_nivel:
            _, created = BadgeEstudiante.objects.get_or_create(
                estudiante=perfil.estudiante,
                badge=badge_nivel
            )
            if created:
                logger.info(f"🏅 {perfil.estudiante.nombre} obtuvo badge de nivel: {badge_nivel.nombre}")
    except Exception as e:
        logger.warning(f"No se pudo asignar badge de nivel: {e}")
