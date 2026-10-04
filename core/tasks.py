"""
Tareas asíncronas de Celery para EKI MVP
Procesa: certificados, campañas, gamificación, reportes, notificaciones
"""
from celery import Task, shared_task
from redis.exceptions import LockError
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def correlacionar_alertas_territoriales():
    """Agrupa señales de la ventana en alertas y reintenta el lake si quedó outbox."""
    from core.event_engine import correr_correlacion_territorial

    out = correr_correlacion_territorial()
    logger.info(
        'alertas_territoriales lake_flush=%s alertas=%s',
        out['lake_flush'],
        out['alertas'],
    )
    return out


@shared_task
def reenganche_drip_content_diario():
    """
    Reenganche diario por Graph. Con META_REENGANCHE_ENABLED en false no envía.
    """
    try:
        from core.reenganche_meta import ejecutar

        resultado = ejecutar()
        logger.info('[Celery] Reenganche drip: %s', resultado)
        return resultado
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


def _datos_webhook(args):
    payload = args[0] if args and isinstance(args[0], dict) else {}
    return payload


def _log_fallo_definitivo(canal: str, args) -> None:
    """Sin teléfono en claro y sin mensaje al usuario."""
    from core.locks import telefono_hash
    from core.nati import normalizar_telefono_whatsapp

    from core.webhook_evento import external_id_de_payload

    payload = _datos_webhook(args)
    telefono = normalizar_telefono_whatsapp(str(payload.get('From') or ''))
    logger.error(
        'webhook_tarea_fallo_definitivo canal=%s external_id=%s telefono_hash=%s',
        canal,
        external_id_de_payload(payload),
        telefono_hash(telefono),
    )


def _guardar_webhook_fallido(task, exc, args, kwargs) -> None:
    """Persiste el fallo para poder reprocesarlo. El payload queda solo para staff."""
    import json

    from core.webhook_evento import WebhookFallido, external_id_de_payload

    datos = _datos_webhook(args)
    external_id = external_id_de_payload(datos)
    kwargs_limpios = {}
    if isinstance(kwargs, dict) and 'forzar_canal' in kwargs:
        kwargs_limpios['forzar_canal'] = bool(kwargs.get('forzar_canal'))
    try:
        json.dumps(datos)
        cuerpo = datos
    except TypeError:
        cuerpo = json.loads(json.dumps(datos, default=str))
    try:
        WebhookFallido.objects.create(
            canal=getattr(task, 'canal', '') or '',
            external_id=external_id,
            payload={
                'tarea': getattr(task, 'name', '') or '',
                'datos': cuerpo,
                'kwargs': kwargs_limpios,
            },
            error=str(exc)[:4000],
        )
    except Exception:
        logger.exception(
            'webhook_fallido_no_guardado canal=%s external_id=%s',
            getattr(task, 'canal', ''),
            external_id,
        )


def _cortar_reentregas(task, datos, kwargs=None) -> bool:
    """True en la tercera reentrega del broker: no corre el cuerpo.

    Los retry() por candado no cuentan: solo delivery_info['redelivered'].
    """
    from core.locks import ENTREGA_TOPE, contar_entrega
    from core.webhook_evento import external_id_de_payload

    info = getattr(getattr(task, 'request', None), 'delivery_info', None) or {}
    if not isinstance(info, dict) or info.get('redelivered') is not True:
        return False
    datos = datos if isinstance(datos, dict) else {}
    ext = external_id_de_payload(datos)
    n = contar_entrega(getattr(task, 'canal', '') or '', ext)
    if n < ENTREGA_TOPE:
        return False
    logger.error(
        'webhook_reentregas_excedidas canal=%s external_id=%s entrega=%s',
        getattr(task, 'canal', ''),
        ext,
        n,
    )
    _guardar_webhook_fallido(task, 'reentregas_excedidas', [datos], kwargs or {})
    return True


def _aviso_flood_texto(telefono):
    from core.antiflood import AVISO_FLOOD
    from core.utils import enviar_whatsapp

    enviar_whatsapp(telefono, AVISO_FLOOD)


def _aviso_flood_meta(telefono, inbound):
    from core.antiflood import AVISO_FLOOD
    from core.sandbox_menu import enviar_texto_sandbox

    enviar_texto_sandbox(
        telefono,
        str((inbound or {}).get('To') or ''),
        AVISO_FLOOD,
        agente='antiflood',
    )


def _frenar_flood(telefono, avisar) -> bool:
    from core.antiflood import flood_excedido

    descartar, unico = flood_excedido(telefono)
    if not descartar:
        return False
    if unico:
        try:
            avisar()
        except Exception:
            logger.exception('flood_aviso_no_salio')
    return True


def _reintentar_si_lock(task, exc):
    from celery.exceptions import SoftTimeLimitExceeded

    from core.salida_usuario import mensaje_ya_salio

    if isinstance(exc, SoftTimeLimitExceeded):
        if mensaje_ya_salio():
            logger.error(
                'webhook_soft_timeout_tras_envio canal=%s no_reintenta=1',
                getattr(task, 'canal', ''),
            )
        raise exc
    if not isinstance(exc, LockError):
        raise exc
    espera = min(2 ** task.request.retries, 30)
    raise task.retry(exc=exc, countdown=espera)


class _TareaWebhook(Task):
    canal = 'twilio'
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        _log_fallo_definitivo(self.canal, args)
        _guardar_webhook_fallido(self, exc, args, kwargs)


class _TareaWebhookMeta(_TareaWebhook):
    canal = 'meta'


_WEBHOOK_TASK = dict(
    bind=True,
    max_retries=8,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=45,
    time_limit=60,
)


@shared_task(base=_TareaWebhook, **_WEBHOOK_TASK)
def procesar_bot_comercial_webhook_async(self, post_data: dict, forzar_canal: bool = False):
    """Nat fuera del request. El candado es por teléfono; si no se obtiene, reintenta."""
    from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook
    from core.locks import telefono_lock
    from core.nati import normalizar_telefono_whatsapp

    from core.salida_usuario import reset_mensaje_salio

    reset_mensaje_salio()
    if _cortar_reentregas(self, post_data, {'forzar_canal': forzar_canal}):
        return None
    telefono = normalizar_telefono_whatsapp(str((post_data or {}).get('From') or '')) or 'sin-telefono'
    if _frenar_flood(telefono, lambda: _aviso_flood_texto(telefono)):
        return None
    try:
        with telefono_lock(telefono):
            logger.info(
                "[Celery] Webhook Nat | sid=%s | forzar=%s",
                (post_data or {}).get('MessageSid', ''),
                forzar_canal,
            )
            from core.wa_canal import CANAL_TWILIO, canal_webhook

            with canal_webhook(CANAL_TWILIO):
                return _procesar_bot_comercial_twilio_webhook(post_data, forzar_canal=forzar_canal)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15, acks_late=True, soft_time_limit=20, time_limit=30)
def procesar_statuses_meta_async(self, statuses):
    """Statuses de Meta fuera del request. Varios por mensaje; no se deduplican."""
    from core.meta_estados import aplicar_statuses

    return aplicar_statuses(statuses)


@shared_task(base=_TareaWebhookMeta, **_WEBHOOK_TASK)
def procesar_sandbox_meta_async(self, inbound: dict):
    """Una tarea por mensaje de la línea Meta. time_limit 60 < candado 90."""
    from core.locks import telefono_lock
    from core.nati import normalizar_telefono_whatsapp
    from core.views import _aplicar_sandbox_menu

    from core.salida_usuario import reset_mensaje_salio

    reset_mensaje_salio()
    if _cortar_reentregas(self, inbound):
        return None
    telefono = normalizar_telefono_whatsapp(str((inbound or {}).get('From') or '')) or 'sin-telefono'
    if _frenar_flood(telefono, lambda: _aviso_flood_meta(telefono, inbound)):
        return None
    try:
        with telefono_lock(telefono):
            logger.info("[Celery] Línea Meta | sid=%s", (inbound or {}).get('MessageSid', ''))
            from core.wa_canal import CANAL_META, canal_webhook

            with canal_webhook(CANAL_META):
                return _aplicar_sandbox_menu(inbound)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


@shared_task(base=_TareaWebhook, **_WEBHOOK_TASK)
def procesar_twilio_webhook_async(self, post_data: dict):
    """Webhook Twilio educativo en Celery. No toca el cuerpo del procesador."""
    from core.locks import telefono_lock
    from core.nati import normalizar_telefono_whatsapp
    from core.views import _procesar_twilio_webhook

    from core.salida_usuario import reset_mensaje_salio

    reset_mensaje_salio()
    if _cortar_reentregas(self, post_data):
        return None
    telefono = normalizar_telefono_whatsapp(str((post_data or {}).get('From') or '')) or 'sin-telefono'
    if _frenar_flood(telefono, lambda: _aviso_flood_texto(telefono)):
        return None
    try:
        with telefono_lock(telefono):
            logger.info("[Celery] Webhook Twilio educativo | sid=%s", (post_data or {}).get('MessageSid', ''))
            from core.wa_canal import CANAL_TWILIO, canal_webhook

            with canal_webhook(CANAL_TWILIO):
                return _procesar_twilio_webhook(post_data)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


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
        from core.webhook_evento import purgar_eventos_procesados, purgar_webhooks_fallidos

        limite = timezone.now() - timezone.timedelta(days=90)
        eliminados, _ = MensajeChat.objects.filter(fecha__lt=limite).delete()
        eventos = purgar_eventos_procesados(10)
        fallidos = purgar_webhooks_fallidos(10)

        logger.info(
            "[Celery] Limpieza de logs: %s mensajes (> 90 días), %s eventos webhook (> 10 días), %s fallidos (> 10 días)",
            eliminados,
            eventos,
            fallidos,
        )
        return f'{eliminados} mensajes eliminados; {eventos} eventos webhook; {fallidos} fallidos'

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
                    countdown=min(creados * 12, 540),
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


@shared_task(bind=True, max_retries=1, default_retry_delay=60, soft_time_limit=900, time_limit=1200)
def encode_paso_modulo_media(
    self,
    job_id: str,
    paso_id: int,
    temp_s3_path: str,
    filename: str,
    carpeta: str,
    prefix: str,
):
    """
    Descarga MP4 incoming, ffmpeg en worker, actualiza PasoModulo (evita 504 en Gunicorn).
    """
    from django.core.exceptions import ValidationError
    from django.core.files.storage import default_storage

    from core.admin._common import guardar_bytes_admin_media_resultado
    from core.media_encode_async import _set_encode_state, _clear_encode_state
    from core.models import PasoModulo

    _set_encode_state(job_id=job_id, paso_id=paso_id, status='running')
    try:
        paso = PasoModulo.objects.get(pk=paso_id)
    except PasoModulo.DoesNotExist:
        logger.warning('[Celery][MediaEncode] paso_id=%s no existe', paso_id)
        _clear_encode_state(job_id=job_id, paso_id=paso_id)
        return {'error': 'paso_not_found'}

    try:
        with default_storage.open(temp_s3_path, 'rb') as fh:
            raw = fh.read()
        resultado = guardar_bytes_admin_media_resultado(
            raw,
            filename,
            carpeta=carpeta,
            prefix=prefix,
            validar_video=True,
        )
        from core.media_pasos_listos import aplicar_resultado_encode_a_paso

        aplicar_resultado_encode_a_paso(paso, resultado)
        try:
            default_storage.delete(temp_s3_path)
        except Exception:
            logger.debug('[Celery][MediaEncode] no se pudo borrar incoming %s', temp_s3_path)
        _clear_encode_state(job_id=job_id, paso_id=paso_id)
        logger.info(
            '[Celery][MediaEncode] paso_id=%s apto=%s activo=%s bytes=%s',
            paso_id,
            paso.media_wa_apto,
            paso.activo,
            resultado.get('bytes'),
        )
        return {'status': 'ok', 'paso_id': paso_id, 'apto': paso.media_wa_apto}
    except ValidationError as exc:
        err = str(exc)
        if hasattr(exc, 'messages'):
            msgs = getattr(exc, 'messages', None)
            if msgs:
                err = msgs[0] if len(msgs) == 1 else ', '.join(msgs)
        logger.warning('[Celery][MediaEncode] paso_id=%s validation: %s', paso_id, err)
        _set_encode_state(job_id=job_id, paso_id=paso_id, status='error', error=err)
        try:
            paso.refresh_from_db()
            paso.media_wa_apto = False
            paso.save(update_fields=['media_wa_apto'])
        except Exception:
            pass
        return {'status': 'error', 'error': err}
    except Exception as exc:
        logger.exception('[Celery][MediaEncode] paso_id=%s job=%s', paso_id, job_id)
        err = str(exc)
        if hasattr(exc, 'messages'):
            msgs = getattr(exc, 'messages', None)
            if msgs:
                err = msgs[0] if len(msgs) == 1 else ', '.join(msgs)
        _set_encode_state(job_id=job_id, paso_id=paso_id, status='error', error=err)
        try:
            paso.refresh_from_db()
            paso.media_wa_apto = False
            paso.save(update_fields=['media_wa_apto'])
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    queue='course_engine',
    soft_time_limit=900,
    time_limit=1200,
    max_retries=0,
)
def generar_video_course_engine_async(
    self,
    run_id: str,
    cliente_id: int,
    curso_id: int,
    modulo_id: int | None,
    brief: str,
    foco: str = '',
    modo_demo: bool = False,
):
    """Genera MP4 Course Engine (Platzi 16:9) — portal admin."""
    from django.core.cache import cache

    from core.course_engine.portal_api import STUDIO_DEMO_MAX_SEC
    from core.course_engine.video_pilot_generator import FOCO_PILOTO_ERROR1, VideoPilotGenerator

    key = f'ce_video_job:{run_id}'
    cache.set(key, {'status': 'running', 'run_id': run_id, 'modo_demo': modo_demo}, 7200)
    try:
        gen = VideoPilotGenerator()
        target_sec = STUDIO_DEMO_MAX_SEC if modo_demo else 14.0
        runway_dur = 4 if modo_demo else 5
        out = gen.generar(
            cliente_id=cliente_id,
            curso_id=curso_id,
            modulo_id=modulo_id,
            brief=brief,
            foco=foco or FOCO_PILOTO_ERROR1,
            dry_run=False,
            generar_video=True,
            target_sec=target_sec,
            runway_duration_sec=runway_dur,
            modo_demo=modo_demo,
            max_duracion_seg=STUDIO_DEMO_MAX_SEC if modo_demo else None,
        )
        payload = {
            'status': 'ok' if out.paso_wa and out.paso_wa.media_url else 'error',
            'run_id': out.run_id,
            'media_url': (out.paso_wa.media_url if out.paso_wa else '') or '',
            'video_url': (out.paso_wa.media_url if out.paso_wa else '') or '',
            'caption': (out.paso_wa.caption if out.paso_wa else '') or '',
            'errors': out.errors,
            'pasos': out.pasos[-8:],
            'costo_usd': out.costo_real_usd,
            'modo_demo': modo_demo,
            'max_seg': target_sec,
        }
        if payload['status'] != 'ok':
            payload['error'] = '; '.join(out.errors) or 'Generación incompleta'
        cache.set(key, payload, 7200)
        return payload
    except Exception as exc:
        logger.exception('[CE] generar_video_course_engine_async run=%s', run_id)
        cache.set(key, {'status': 'error', 'run_id': run_id, 'error': str(exc)}, 7200)
        raise


@shared_task
def sincronizar_plantillas_meta():
    """Poll de plantillas Meta en PENDING / IN_APPEAL. No toca Twilio."""
    from core.meta_waba import sincronizar_pendientes

    n = sincronizar_pendientes()
    logger.info('plantillas_meta_sync n=%s', n)
    return n


@shared_task(bind=True, max_retries=1, default_retry_delay=60, time_limit=3600, soft_time_limit=3300)
def ejecutar_campana_meta_async(self, campana_id):
    from core.meta_waba import ejecutar_campana_meta
    from core.models_campana_meta import CampanaMeta

    try:
        campana = CampanaMeta.objects.select_related('plantilla', 'grupo').get(pk=campana_id)
        return ejecutar_campana_meta(campana)
    except Exception as exc:
        logger.error('campana_meta_async_fail id=%s err=%s', campana_id, exc)
        raise self.retry(exc=exc)
