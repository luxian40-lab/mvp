"""
Tareas asíncronas de Celery para EKI MVP
Procesa: certificados, campañas, gamificación, reportes, notificaciones
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def reenganche_drip_content_diario():
    """
    Reenganche diario: notifica a estudiantes cuyo próximo módulo ya se desbloqueó.
    """
    try:
        from datetime import timedelta
        from core.models import ProgresoEstudiante
        from core.utils import enviar_whatsapp_twilio
        from core.whatsapp_service import enviar_template_twilio

        ahora = timezone.now()
        template_sid = (getattr(settings, 'TWILIO_TEMPLATE_DRIP_REENGANCHE', '') or '').strip()
        queryset = ProgresoEstudiante.objects.select_related('estudiante', 'curso', 'modulo_actual').filter(
            completado=False,
            curso__dias_espera_entre_modulos__gt=0,
            fecha_ultimo_avance__isnull=False,
            modulo_actual__isnull=False,
        )

        enviados = 0
        for progreso in queryset:
            siguiente = progreso.curso.modulos.filter(numero__gt=progreso.modulo_actual.numero).order_by('numero').first()
            if not siguiente:
                continue

            fecha_desbloqueo = progreso.fecha_ultimo_avance + timedelta(days=progreso.curso.dias_espera_entre_modulos)
            if fecha_desbloqueo.date() == ahora.date():
                if template_sid:
                    # Soporta plantilla HSM aprobada en Twilio para ventanas fuera de sesión.
                    resultado = enviar_template_twilio(
                        progreso.estudiante.telefono,
                        template_sid,
                        variables={'1': progreso.estudiante.nombre or 'estudiante', '2': progreso.curso.nombre}
                    )
                else:
                    msg = (
                        "👋 ¡Hola! Tu nuevo módulo ya está disponible.\n\n"
                        f"Curso: *{progreso.curso.nombre}*\n"
                        "Responde *LISTO* para continuar."
                    )
                    resultado = enviar_whatsapp_twilio(progreso.estudiante.telefono, msg)
                if resultado.get('success'):
                    enviados += 1

        logger.info(f"[Celery] Reenganche drip completado. Notificaciones enviadas: {enviados}")
        return {'enviados': enviados}
    except Exception as e:
        logger.error(f"[Celery] Error en reenganche drip: {e}")
        return {'error': str(e)}


# ==========================================
# TAREAS DE PROCESAMIENTO PRINCIPAL
# ==========================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def procesar_respuesta_estudiante(self, estudiante_id, mensaje, media_url=None):
    """
    Procesa la respuesta de un estudiante de forma asíncrona.
    Llamada desde el webhook de WhatsApp.
    """
    try:
        from core.models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        logger.info(f"[Celery] Procesando respuesta de {estudiante.nombre}: {mensaje[:50]}...")

        # Delegar al handler correspondiente según estado
        from core.onboarding_handler import manejar_mensaje_estudiante
        resultado = manejar_mensaje_estudiante(estudiante, mensaje, media_url=media_url)
        logger.info(f"[Celery] Respuesta procesada para {estudiante.nombre}")
        return resultado

    except Exception as exc:
        logger.error(f"[Celery] Error procesando respuesta estudiante {estudiante_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generar_certificado_async(self, certificado_id):
    """
    Genera un certificado PDF de forma asíncrona.
    """
    try:
        from core.models import Certificado
        certificado = Certificado.objects.select_related(
            'estudiante', 'curso', 'plantilla'
        ).get(id=certificado_id)

        logger.info(f"[Celery] Generando certificado para {certificado.estudiante.nombre} - {certificado.curso.nombre}")

        from core.generador_certificados import generar_certificado_pdf
        resultado = generar_certificado_pdf(certificado, plantilla=certificado.plantilla)

        if resultado:
            certificado.generado = True
            certificado.fecha_generacion = timezone.now()
            certificado.save(update_fields=['generado', 'fecha_generacion'])
            logger.info(f"[Celery] Certificado generado OK: {certificado.id}")
        else:
            logger.error(f"[Celery] Error generando certificado {certificado.id}")

        return resultado

    except Exception as exc:
        logger.error(f"[Celery] Error generando certificado {certificado_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def actualizar_gamificacion_async(self, estudiante_id, puntos, razon):
    """
    Actualiza puntos de gamificación de forma asíncrona.
    """
    try:
        from core.models import Estudiante
        from core.gamificacion import PerfilGamificacion

        estudiante = Estudiante.objects.get(id=estudiante_id)
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        subio_nivel = perfil.agregar_puntos(puntos=puntos, razon=razon)

        logger.info(f"[Celery] Gamificación actualizada: {estudiante.nombre} +{puntos} pts ({razon})")

        if subio_nivel:
            logger.info(f"[Celery] 🎉 {estudiante.nombre} subió a nivel {perfil.nivel}!")

        return {'subio_nivel': subio_nivel, 'nivel': perfil.nivel, 'puntos_totales': perfil.puntos_totales}

    except Exception as exc:
        logger.error(f"[Celery] Error actualizando gamificación para {estudiante_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def enviar_notificacion_async(self, telefono, mensaje, media_url=None):
    """
    Envía una notificación WhatsApp de forma asíncrona.
    """
    try:
        from core.whatsapp_service import enviar_mensaje_whatsapp
        resultado = enviar_mensaje_whatsapp(telefono, mensaje, media_url=media_url)
        logger.info(f"[Celery] Notificación enviada a {telefono}: {mensaje[:50]}...")
        return resultado

    except Exception as exc:
        logger.error(f"[Celery] Error enviando notificación a {telefono}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def enviar_archivo_modulo_async(self, telefono, archivo_id):
    """
    Envía un archivo multimedia de módulo por WhatsApp de forma asíncrona.
    """
    try:
        from core.models_extras import ArchivoModulo
        from core.whatsapp_service import enviar_archivo_modulo_whatsapp

        archivo = ArchivoModulo.objects.get(id=archivo_id)
        resultado = enviar_archivo_modulo_whatsapp(telefono, archivo)

        if resultado.get('success'):
            logger.info(f"[Celery] Archivo '{archivo.titulo}' enviado a {telefono}")
        else:
            logger.error(f"[Celery] Error enviando archivo '{archivo.titulo}': {resultado.get('response')}")

        return resultado

    except Exception as exc:
        logger.error(f"[Celery] Error enviando archivo {archivo_id} a {telefono}: {exc}")
        raise self.retry(exc=exc)


# ==========================================
# TAREAS PROGRAMADAS (Beat)
# ==========================================

@shared_task
def enviar_campanas_programadas():
    """
    Busca campañas programadas pendientes y las ejecuta.
    Se ejecuta cada 5 minutos vía Celery Beat.
    """
    try:
        from core.models import Campana

        ahora = timezone.now()
        campanas_pendientes = Campana.objects.filter(
            estado='programada',
            fecha_programada__lte=ahora
        )

        count = campanas_pendientes.count()
        if count == 0:
            return 'Sin campañas pendientes'

        logger.info(f"[Celery] Procesando {count} campañas programadas")
        for campana in campanas_pendientes:
            ejecutar_campana_async.delay(campana.id)

        return f'{count} campañas encoladas'

    except Exception as e:
        logger.error(f"[Celery] Error procesando campañas programadas: {e}")
        return f'Error: {e}'


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def ejecutar_campana_async(self, campana_id):
    """
    Ejecuta una campaña específica de forma asíncrona.
    """
    try:
        from core.enviar_plantillas import enviar_campana_con_plantilla

        logger.info(f"[Celery] Ejecutando campaña {campana_id}")
        resultado = enviar_campana_con_plantilla(campana_id)
        logger.info(f"[Celery] Campaña {campana_id} completada: {resultado}")
        return resultado

    except Exception as exc:
        logger.error(f"[Celery] Error ejecutando campaña {campana_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def generar_reporte_actividad():
    """
    Genera un reporte de actividad periódico.
    Se ejecuta cada hora vía Celery Beat.
    """
    try:
        from core.models import Estudiante, ProgresoEstudiante, MensajeChat
        from django.db.models import Count

        ahora = timezone.now()
        hace_1h = ahora - timezone.timedelta(hours=1)

        mensajes_hora = MensajeChat.objects.filter(fecha__gte=hace_1h).count()
        estudiantes_activos = Estudiante.objects.filter(
            ultima_interaccion__gte=hace_1h
        ).count()
        progreso_hora = ProgresoEstudiante.objects.filter(
            ultima_actividad__gte=hace_1h
        ).count()

        reporte = {
            'timestamp': ahora.isoformat(),
            'mensajes_hora': mensajes_hora,
            'estudiantes_activos': estudiantes_activos,
            'progreso_actualizado': progreso_hora,
        }

        logger.info(f"[Celery] Reporte actividad: {reporte}")
        return reporte

    except Exception as e:
        logger.error(f"[Celery] Error generando reporte de actividad: {e}")
        return {'error': str(e)}


@shared_task
def limpiar_logs_antiguos():
    """
    Limpia logs de conversación antiguos (> 90 días).
    Se ejecuta a las 2 AM vía Celery Beat.
    """
    try:
        from core.models import MensajeChat

        limite = timezone.now() - timezone.timedelta(days=90)
        eliminados, _ = MensajeChat.objects.filter(fecha__lt=limite).delete()

        logger.info(f"[Celery] Limpieza de logs: {eliminados} mensajes eliminados (> 90 días)")
        return f'{eliminados} mensajes eliminados'

    except Exception as e:
        logger.error(f"[Celery] Error limpiando logs: {e}")
        return f'Error: {e}'


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def enviar_email_org_admin_async(self, estudiante_id, asunto, mensaje_html):
    """
    Envía email al admin de la organización del estudiante, de forma asíncrona.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        from core.models import Estudiante

        estudiante = Estudiante.objects.select_related('cliente').get(id=estudiante_id)
        cliente = estudiante.cliente
        if not cliente or not getattr(cliente, 'email', None):
            return 'Sin email de cliente'

        send_mail(
            subject=f"[eki] {asunto}",
            message='',
            html_message=mensaje_html,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@eki.com'),
            recipient_list=[cliente.email],
            fail_silently=True,
        )
        logger.info(f"[Celery] 📧 Email enviado a {cliente.email}: {asunto}")
        return f'Email enviado a {cliente.email}'

    except Exception as exc:
        logger.error(f"[Celery] Error enviando email para estudiante {estudiante_id}: {exc}")
        raise self.retry(exc=exc)
