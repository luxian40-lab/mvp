# 02c — Tareas Celery, Beat y campaña Twilio

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `reenganche_drip_content_diario` — `core/tasks.py:28`

```python
# core/tasks.py:28
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
            from core.modulo_publicacion import siguiente_modulo_publicado_wa

            siguiente = siguiente_modulo_publicado_wa(progreso.curso, progreso.modulo_actual)
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

```

**Contrato**
- Entradas: ninguna (Beat 08:00, `mvp_project/celery.py:49`).
- Salidas: dict `enviados` o `error`.
- Efectos: recorre progresos no completados. Si el desbloqueo por días cae hoy, envía plantilla `TWILIO_TEMPLATE_DRIP_REENGANCHE` o texto libre. No usa `select_for_update`. No marca que ya notificó (un segundo run el mismo día puede reenviar).
- Excepciones: el `except` exterior loguea y devuelve `{'error': ...}` sin propagar.


### `procesar_respuesta_estudiante` — `core/tasks.py:107`

```python
# core/tasks.py:107
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_datos_webhook` — `core/tasks.py:129`

```python
# core/tasks.py:129
def _datos_webhook(args):
    payload = args[0] if args and isinstance(args[0], dict) else {}
    return payload


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_log_fallo_definitivo` — `core/tasks.py:134`

```python
# core/tasks.py:134
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_guardar_webhook_fallido` — `core/tasks.py:151`

```python
# core/tasks.py:151
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_cortar_reentregas` — `core/tasks.py:186`

```python
# core/tasks.py:186
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_reintentar_si_lock` — `core/tasks.py:212`

```python
# core/tasks.py:212
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_TareaWebhook` — `core/tasks.py:230`

```python
# core/tasks.py:230
class _TareaWebhook(Task):
    canal = 'twilio'
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        _log_fallo_definitivo(self.canal, args)
        _guardar_webhook_fallido(self, exc, args, kwargs)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_TareaWebhookMeta` — `core/tasks.py:239`

```python
# core/tasks.py:239
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `procesar_bot_comercial_webhook_async` — `core/tasks.py:253`

```python
# core/tasks.py:253
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
    try:
        with telefono_lock(telefono):
            logger.info(
                "[Celery] Webhook Nat | sid=%s | forzar=%s",
                (post_data or {}).get('MessageSid', ''),
                forzar_canal,
            )
            return _procesar_bot_comercial_twilio_webhook(post_data, forzar_canal=forzar_canal)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `procesar_sandbox_meta_async` — `core/tasks.py:278`

```python
# core/tasks.py:278
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
    try:
        with telefono_lock(telefono):
            logger.info("[Celery] Línea Meta | sid=%s", (inbound or {}).get('MessageSid', ''))
            return _aplicar_sandbox_menu(inbound)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `procesar_twilio_webhook_async` — `core/tasks.py:299`

```python
# core/tasks.py:299
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
    try:
        with telefono_lock(telefono):
            logger.info("[Celery] Webhook Twilio educativo | sid=%s", (post_data or {}).get('MessageSid', ''))
            return _procesar_twilio_webhook(post_data)
    except Exception as exc:
        _reintentar_si_lock(self, exc)


```

**Contrato**
- Entradas: dict del POST (puede incluir `_eki_reply_from`; esta tarea no lo lee).
- Salidas: el retorno de `_procesar_twilio_webhook` o None si se cortan reentregas.
- Efectos: candado Redis `telefono_lock` (timeout 90s, espera 10s). `acks_late`, `reject_on_worker_lost`, soft 45s / hard 60s, `max_retries=8`. A la 3.ª entrega persiste `WebhookFallido` y no corre el cuerpo.
- Excepciones: `LockError` reintenta con backoff `min(2**retries, 30)`. `SoftTimeLimitExceeded` se relanza siempre (si ya salió mensaje, solo se loguea `no_reintenta` pero igual se relanza). Otros errores los captura Celery (`on_failure` → log + `WebhookFallido`).


### `generar_certificado_async` — `core/tasks.py:320`

```python
# core/tasks.py:320
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `actualizar_gamificacion_async` — `core/tasks.py:351`

```python
# core/tasks.py:351
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_notificacion_async` — `core/tasks.py:376`

```python
# core/tasks.py:376
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_archivo_modulo_async` — `core/tasks.py:392`

```python
# core/tasks.py:392
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

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_campanas_programadas` — `core/tasks.py:420`

```python
# core/tasks.py:420
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


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_campana_async` — `core/tasks.py:451`

```python
# core/tasks.py:451
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
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `sincronizar_plantillas_meta` — `core/tasks.py:907`

```python
# core/tasks.py:907
@shared_task
def sincronizar_plantillas_meta():
    """Poll de plantillas Meta en PENDING / IN_APPEAL. No toca Twilio."""
    from core.meta_waba import sincronizar_pendientes

    n = sincronizar_pendientes()
    logger.info('plantillas_meta_sync n=%s', n)
    return n


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_campana_meta_async` — `core/tasks.py:917`

```python
# core/tasks.py:917
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
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_campana_servicio` — `core/services.py:1`

```python
# core/services.py:1
import time
import logging
import threading

from django.conf import settings

from .models import EnvioLog
from .utils import enviar_whatsapp_twilio

logger = logging.getLogger(__name__)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_campana_servicio` — `core/services.py:12`

```python
# core/services.py:12
def ejecutar_campana_servicio(campana):
    """
    Ejecuta el envío real de mensajes WhatsApp a los destinatarios de la campaña.
    Soporta:
      - template_twilio_id: Envío directo con Content Template de Twilio
      - plantilla Django: Envío con texto personalizado (cuerpo_mensaje)
    """
    if getattr(campana, 'es_campana_curso', False) and getattr(campana, 'curso_destino', None):
        from core.modulo_publicacion import curso_listo_para_campana_wa

        ok, msg = curso_listo_para_campana_wa(campana.curso_destino)
        if not ok:
            raise ValueError(msg)

    # Determinar destinatarios según tipo de audiencia
    if hasattr(campana, 'tipo_audiencia') and campana.tipo_audiencia == 'grupo' and campana.grupo:
        destinatarios = campana.grupo.estudiantes.filter(activo=True)
        logger.info(f"Campana grupal: {campana.grupo.nombre} ({destinatarios.count()} estudiantes)")
    else:
        destinatarios = campana.destinatarios.filter(activo=True)
        logger.info(f"Campana individual: {destinatarios.count()} destinatarios")
    
    # Determinar modo de envío
    usa_template_twilio = bool(campana.template_twilio_id)
    usa_plantilla_django = (
        not usa_template_twilio 
        and campana.plantilla 
        and (
            getattr(campana.plantilla, 'content_sid', None) 
            or getattr(campana.plantilla, 'cuerpo_mensaje', None)
        )
    )
    
    if usa_template_twilio:
        content_sid = campana.template_twilio_id.strip()
        logger.info(f"Modo: Content Template de Twilio ({content_sid})")
    elif usa_plantilla_django and getattr(campana.plantilla, 'content_sid', None):
        content_sid = campana.plantilla.content_sid.strip()
        logger.info(f"Modo: Plantilla Django con content_sid ({content_sid})")
    elif usa_plantilla_django and getattr(campana.plantilla, 'cuerpo_mensaje', None):
        content_sid = None
        mensaje_base = campana.plantilla.cuerpo_mensaje
        logger.info(f"Modo: Plantilla Django con cuerpo_mensaje")
    else:
        raise ValueError(
            f"La campana '{campana.nombre}' no tiene un Content SID de Twilio "
            f"ni una plantilla Django con contenido configurado."
        )
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    if resultados["total"] == 0:
        logger.info('Campaña sin destinatarios: %s — no se envía a nadie', campana.nombre)

    logger.info(f"INICIANDO CAMPANA: {campana.nombre} - {resultados['total']} destinatarios")
    
    for estudiante in destinatarios:
        try:
            curso_dest = getattr(campana, 'curso_destino', None)
            # Inscripción siempre que haya curso destino (10x aviso o WA clásico).
            if curso_dest is not None:
                from core.inscripcion_curso import inscribir_estudiante_en_curso

                inscribir_estudiante_en_curso(estudiante, curso_dest)

            # Solo el flujo clásico reinicia Habeas / onboarding.
            if getattr(campana, 'es_campana_curso', False):
                estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
                estudiante.acepto_terminos = False
                estudiante.estado_onboarding = 'nuevo'
                estudiante.save(
                    update_fields=['estado_chat', 'acepto_terminos', 'estado_onboarding']
                )
            
            if content_sid:
                # Envío con Content Template de Twilio
                from .whatsapp_service import enviar_template_twilio
                variables = {'1': estudiante.nombre or 'Estudiante'}
                resultado = enviar_template_twilio(
                    telefono=estudiante.telefono,
                    content_sid=content_sid,
                    variables=variables
                )
            else:
                # Envío con texto personalizado de plantilla Django
                mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre or '')
                mensaje_personalizado = mensaje_personalizado.replace("{telefono}", estudiante.telefono or '')
                resultado = enviar_whatsapp_twilio(
                    telefono=estudiante.telefono,
                    texto=mensaje_personalizado
                )
            
            if resultado.get('success'):
                EnvioLog.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    respuesta_api=f"Message SID: {resultado.get('mensaje_id', 'N/A')}"
                )
                resultados["exitosos"] += 1
                logger.info(f"Enviado a {estudiante.nombre} ({estudiante.telefono})")
            else:
                raise Exception(resultado.get('response', 'Error desconocido'))

        except Exception as e:
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            logger.error(f"Fallo {estudiante.nombre}: {str(e)}")
        
        # Delay para no saturar la API
        time.sleep(0.5)

    # Marcar campaña como ejecutada y guardar stats
    campana.ejecutada = True
    campana.total_enviados = resultados["exitosos"]
    campana.save()
    
    logger.info(f"CAMPANA COMPLETADA: {resultados['exitosos']} exitosos, {resultados['fallidos']} fallidos")
    
    return resultados


```

**Contrato**
- Entradas: instancia `Campana` (Twilio).
- Salidas: dict total/exitosos/fallidos. `ValueError` si el curso no está listo o no hay plantilla.
- Efectos: bucle secuencial, `time.sleep(0.5)` entre destinos. Plantilla vía `enviar_template_twilio` o texto vía `enviar_whatsapp_twilio`. Crea `EnvioLog` ENVIADO o FALLIDO. Pone `ejecutada=True` al final aunque haya fallidos. No salta destinatarios ya enviados.
- Excepciones: por estudiante se capturan y se registran FALLIDO. No hay reintento.


### `encolar_ejecutar_campana` — `core/services.py:143`

```python
# core/services.py:143
def encolar_ejecutar_campana(campana_id: int) -> str:
    """
    Encola el envío masivo fuera del request HTTP del admin.
    Evita 504 cuando hay muchos destinatarios (nginx/ALB ~60s).
    Retorna: 'celery' | 'background'
    """
    def _ejecutar_en_background():
        try:
            from .models import Campana
            campana = Campana.objects.get(pk=campana_id)
            ejecutar_campana_servicio(campana)
        except Exception:
            logger.exception('[Campana] Error en envío background id=%s', campana_id)

    try:
        from core.tasks import ejecutar_campana_async

        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            threading.Thread(
                target=_ejecutar_en_background,
                daemon=True,
                name=f'campana-{campana_id}',
            ).start()
            return 'background'

        ejecutar_campana_async.delay(campana_id)
        return 'celery'
    except Exception:
        logger.warning('[Campana] Celery no disponible; envío en hilo background id=%s', campana_id)
        threading.Thread(
            target=_ejecutar_en_background,
            daemon=True,
            name=f'campana-{campana_id}',
        ).start()
        return 'background'
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `beat_schedule` — `mvp_project/celery.py:27`

```python
# mvp_project/celery.py:27
app.conf.beat_schedule = {
    # Enviar campañas programadas cada 5 minutos
    'enviar-campanhas-programadas': {
        'task': 'core.tasks.enviar_campanas_programadas',
        'schedule': 300.0,  # cada 5 minutos
    },
    # Estado PENDING/IN_APPEAL de Plantilla Meta (Graph). No toca campañas Twilio.
    'sincronizar-plantillas-meta': {
        'task': 'core.tasks.sincronizar_plantillas_meta',
        'schedule': 600.0,
    },
    # Generar reporte de actividad cada hora
    'reporte-actividad-hora': {
        'task': 'core.tasks.generar_reporte_actividad',
        'schedule': 3600.0,  # cada hora
    },
    # Limpiar logs antiguos a las 2 AM
    'limpiar-logs-antiguos': {
        'task': 'core.tasks.limpiar_logs_antiguos',
        'schedule': crontab(hour=2, minute=0),
    },
    # Reenganche de módulos drip (diario 8:00 AM). Plantilla HSM opcional: TWILIO_TEMPLATE_DRIP_REENGANCHE en settings.
    'reenganche-drip-diario': {
        'task': 'core.tasks.reenganche_drip_content_diario',
        'schedule': crontab(hour=8, minute=0),
    },
    # Advisor de infra (reglas): snapshot + email si overall → ACTUAR.
    'revisar-infra-advisor': {
        'task': 'core.tasks_infra.revisar_infra_advisor',
        'schedule': crontab(minute=15),  # cada hora a :15
    },
    # Cluster territorial v0 + reintento del data lake (outbox sin published_at).
    'correlacionar-alertas-territoriales': {
        'task': 'core.tasks.correlacionar_alertas_territoriales',
        'schedule': crontab(minute=20),
    },
}
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.

