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
        from .drip_schedule import dias_espera_efectivos

        queryset = ProgresoEstudiante.objects.select_related('estudiante', 'curso', 'modulo_actual').filter(
            completado=False,
            fecha_ultimo_avance__isnull=False,
            modulo_actual__isnull=False,
        )

        enviados = 0
        for progreso in queryset:
            dias_drip = dias_espera_efectivos(progreso.estudiante, progreso.curso)
            if dias_drip <= 0:
                continue
            siguiente = progreso.curso.modulos.filter(numero__gt=progreso.modulo_actual.numero).order_by('numero').first()
            if not siguiente:
                continue

            fecha_desbloqueo = progreso.fecha_ultimo_avance + timedelta(days=dias_drip)
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
                    try:
                        from core.models import EstudianteEventoAprendizaje
                        from core.telemetria import registrar_evento

                        registrar_evento(
                            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
                            estudiante=progreso.estudiante,
                            curso=progreso.curso,
                            modulo=siguiente,
                            metadata={
                                'origen': 'reenganche_drip',
                                'template': bool(template_sid),
                                'modulo_desbloqueado_id': siguiente.pk,
                            },
                        )
                    except Exception:
                        pass

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


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def procesar_twilio_webhook_async(self, post_data: dict):
    """
    Procesa webhook Twilio educativo en Celery (libera worker Gunicorn).
    Activar con WEBHOOK_CELERY_ASYNC=true en EB cuando haya picos de mensajes.
    """
    try:
        from core.views import _procesar_twilio_webhook

        logger.info("[Celery] Webhook Twilio educativo | sid=%s", post_data.get('MessageSid', ''))
        return _procesar_twilio_webhook(post_data)
    except Exception as exc:
        logger.error("[Celery] Error webhook Twilio async: %s", exc)
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
        from .models import Campana

        ahora = timezone.now()
        campanas_pendientes = Campana.objects.filter(
            ejecutada=False,
            fecha_programada__isnull=False,
            fecha_programada__lte=ahora,
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


@shared_task(bind=True, max_retries=2, default_retry_delay=60, time_limit=3600, soft_time_limit=3300)
def ejecutar_campana_async(self, campana_id):
    """
    Ejecuta una campaña específica de forma asíncrona (misma lógica que el admin).
    """
    try:
        from .models import Campana
        from .services import ejecutar_campana_servicio

        campana = Campana.objects.get(pk=campana_id)
        logger.info(f"[Celery] Ejecutando campaña {campana_id}")
        resultado = ejecutar_campana_servicio(campana)
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


@shared_task(bind=True, max_retries=2, default_retry_delay=120, time_limit=3600, soft_time_limit=3300)
def indexar_biblioteca_nat_por_id(self, item_id: int):
    """Indexa BibliotecaConocimiento (Nat Knowledge Hub) fuera del request HTTP."""
    from core.biblioteca_nat_service import indexar_item
    from core.models import BibliotecaConocimiento

    try:
        item = BibliotecaConocimiento.objects.get(pk=item_id)
    except BibliotecaConocimiento.DoesNotExist:
        logger.warning('[Celery][BibliotecaNat] ítem id=%s no existe', item_id)
        return {'error': 'not_found'}

    try:
        n = indexar_item(item)
        logger.info('[Celery][BibliotecaNat] Indexado id=%s -> %s chunks', item_id, n)
        return {'chunks': n, 'id': item_id}
    except Exception as exc:
        logger.exception('[Celery][BibliotecaNat] Error indexando id=%s', item_id)
        try:
            item.refresh_from_db()
            if item.estado_rag == 'pendiente':
                item.estado_rag = 'error'
                item.rag_error_detalle = str(exc)[:500]
                item.save(update_fields=['estado_rag', 'rag_error_detalle'])
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120, time_limit=3600, soft_time_limit=3300)
def indexar_documento_rag_por_id(self, app_label: str, model_name: str, object_id: int):
    """
    Indexa un DocumentoRAG o DocumentoRAGComercial fuera del ciclo HTTP del admin.
    Evita 504 cuando el embedding / Chroma tarda más que nginx/ALB/gunicorn.
    """
    from django.apps import apps

    Model = apps.get_model(app_label, model_name)
    try:
        doc = Model.objects.get(pk=object_id)
    except Model.DoesNotExist:
        logger.warning("[Celery][RAG] Documento %s.%s id=%s no existe", app_label, model_name, object_id)
        return {"error": "not_found"}

    if not doc.archivo:
        logger.warning("[Celery][RAG] Documento id=%s sin archivo", object_id)
        return {"skipped": True}

    try:
        n = doc.indexar()
        logger.info("[Celery][RAG] Indexado %s.%s id=%s -> %s chunks", app_label, model_name, object_id, n)
        return {"chunks": n, "id": object_id}
    except Exception as exc:
        logger.exception("[Celery][RAG] Error indexando %s.%s id=%s", app_label, model_name, object_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=300, time_limit=3600, soft_time_limit=3300)
def procesar_zip_rag_comercial(
    self,
    storage_path: str,
    cliente_id,
    canal: str,
    tipo: str,
    descripcion: str,
    user_id,
):
    """
    Extrae un ZIP en el worker Celery y crea DocumentoRAGComercial por archivo válido.
    La indexación de cada doc se encola aparte (no en el request HTTP).
    """
    import os
    import shutil
    import tempfile
    import zipfile

    from django.contrib.auth import get_user_model
    from django.core.files.storage import default_storage

    from core.admin import (
        _extension_archivo_comercial_ok,
        _nombre_documento_desde_nombre_archivo,
        _nombre_rag_comercial_unico,
    )
    from core.models import Cliente, DocumentoRAGComercial

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first() if user_id else None
    cliente = None
    if cliente_id:
        cliente = Cliente.objects.filter(pk=cliente_id).first()

    tmp_dir = tempfile.mkdtemp(prefix="eki_rag_zip_")
    creados = 0
    omitidos = 0
    try:
        with default_storage.open(storage_path, "rb") as src:
            zip_path = os.path.join(tmp_dir, "upload.zip")
            with open(zip_path, "wb") as out:
                shutil.copyfileobj(src, out)

        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [
                m
                for m in zf.namelist()
                if m and not m.endswith("/") and not m.startswith("__MACOSX")
            ]
            if len(members) > 100:
                logger.warning("[Celery][RAG ZIP] ZIP con %s archivos; se procesan solo 100", len(members))
                members = members[:100]

            for member in members:
                base_name = os.path.basename(member)
                if not _extension_archivo_comercial_ok(base_name):
                    omitidos += 1
                    continue
                try:
                    zf.extract(member, tmp_dir)
                except Exception as exc:
                    logger.warning("[Celery][RAG ZIP] No se extrajo %s: %s", member, exc)
                    omitidos += 1
                    continue
                local_path = os.path.join(tmp_dir, member)
                if not os.path.isfile(local_path):
                    omitidos += 1
                    continue
                nombre = _nombre_rag_comercial_unico(
                    cliente,
                    canal,
                    _nombre_documento_desde_nombre_archivo(base_name),
                )
                with open(local_path, "rb") as fh:
                    from django.core.files import File

                    doc = DocumentoRAGComercial(
                        cliente=cliente,
                        canal=canal,
                        nombre=nombre,
                        tipo=tipo,
                        descripcion=descripcion,
                        subido_por=user,
                        estado="pendiente",
                    )
                    doc.archivo.save(base_name, File(fh), save=True)
                indexar_documento_rag_por_id.apply_async(
                    ("core", "DocumentoRAGComercial", doc.pk),
                    countdown=min(creados * 12, 900),
                )
                creados += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            default_storage.delete(storage_path)
        except Exception:
            pass

    logger.info(
        "[Celery][RAG ZIP] Listo: %s documentos, %s omitidos (storage=%s)",
        creados,
        omitidos,
        storage_path,
    )
    return {"creados": creados, "omitidos": omitidos}


def _curso_ia_cache_key(job_id: str) -> str:
    return f'curso_ia_job:{job_id}'


@shared_task(bind=True, max_retries=0, soft_time_limit=300, time_limit=360)
def generar_curso_ia_async(self, job_id: str, texto: str, modelo: str):
    """Genera estructura de curso en Celery (evita 504 en nginx)."""
    from django.core.cache import cache
    from core.utils_ia import generar_estructura_curso_con_ia, validar_estructura_curso

    key = _curso_ia_cache_key(job_id)
    try:
        cache.set(key, {'status': 'running'}, 3600)
        estructura = generar_estructura_curso_con_ia(texto, modelo=modelo)
        ok, errores = validar_estructura_curso(estructura)
        if not ok:
            cache.set(key, {'status': 'error', 'error': ', '.join(errores)}, 3600)
            return {'status': 'error'}
        cache.set(key, {'status': 'ok', 'estructura': estructura}, 3600)
        return {'status': 'ok', 'modulos': len(estructura.get('modulos', []))}
    except Exception as exc:
        logger.exception('[Celery] generar_curso_ia_async job=%s', job_id)
        cache.set(key, {'status': 'error', 'error': str(exc)}, 3600)
        return {'status': 'error', 'error': str(exc)}
