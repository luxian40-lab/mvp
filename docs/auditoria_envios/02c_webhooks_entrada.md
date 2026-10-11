# 02c — HTTP, firmas, idempotencia y enrutado

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `whatsapp_webhook` — `core/views/entrada.py:1`

```python
# core/views/entrada.py:1
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

from core.webhook_evento import (
    CANAL_META,
    CANAL_TWILIO,
    firma_meta_invalida,
    liberar_eventos,
    preparar_payload_meta,
    reclamar_twilio,
)

from .twilio_transporte import _encolar_twilio_edu_si_async, _es_status_callback_twilio
from .webhook_comercial import _encolar_bot_comercial_si_async
from .webhook_meta import (
    _aplicar_sandbox_menu,
    _encolar_sandbox_si_async,
    _procesar_meta_webhook,
    _sandbox_inbound_repetido,
)
from .webhook_twilio import _procesar_twilio_webhook

logger = logging.getLogger(__name__)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_sid_de` — `core/views/entrada.py:32`

```python
# core/views/entrada.py:32
def _sid_de(data) -> str:
    return str((data or {}).get('MessageSid') or '').strip()[:128]


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_error_sincronico` — `core/views/entrada.py:36`

```python
# core/views/entrada.py:36
def _error_sincronico(canal, external_id):
    """La lógica de negocio ya arrancó: el reclamo se queda."""
    logger.error(
        'webhook_proceso_sincrono canal=%s external_id=%s',
        canal,
        external_id,
    )
    return HttpResponse('Error', status=500)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_error_encolado` — `core/views/entrada.py:46`

```python
# core/views/entrada.py:46
def _error_encolado(canal, external_ids):
    """Redis no aceptó la tarea: se suelta el reclamo para que el proveedor reintente."""
    logger.exception(
        'webhook_encolar_fail canal=%s external_ids=%s',
        canal,
        list(external_ids or []),
    )
    liberar_eventos(canal, external_ids)
    return HttpResponse('Error', status=500)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_payload_un_mensaje` — `core/views/entrada.py:57`

```python
# core/views/entrada.py:57
def _payload_un_mensaje(payload, message_id: str) -> dict:
    import copy

    clon = copy.deepcopy(payload)
    for entry in clon.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            value = change.get('value')
            if not isinstance(value, dict) or 'messages' not in value:
                continue
            value['messages'] = [
                mensaje
                for mensaje in (value.get('messages') or [])
                if isinstance(mensaje, dict)
                and str(mensaje.get('id') or '').strip()[:128] == message_id
            ]
    return clon


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_procesar_meta_por_mensaje` — `core/views/entrada.py:79`

```python
# core/views/entrada.py:79
def _procesar_meta_por_mensaje(payload):
    """Cada mensaje se encola o se procesa solo. Un fallo no suelta los anteriores."""
    from core.sandbox_canal import iter_mensajes_inbound_meta, sandbox_via_meta
    from core.sandbox_menu import es_destino_sandbox

    inbounds = list(iter_mensajes_inbound_meta(payload))
    if not inbounds:
        _procesar_meta_webhook(payload)
        return None

    def _posteriores(desde: int) -> list[str]:
        return [_sid_de(inbounds[j]) for j in range(desde, len(inbounds)) if _sid_de(inbounds[j])]

    if sandbox_via_meta() and any(es_destino_sandbox(item) for item in inbounds):
        last_sb = None
        for indice, inbound in enumerate(inbounds):
            if not es_destino_sandbox(inbound):
                continue
            sid = _sid_de(inbound)
            if _sandbox_inbound_repetido(inbound):
                continue
            try:
                encolado = _encolar_sandbox_si_async(inbound)
            except Exception:
                return _error_encolado(CANAL_META, [sid, *_posteriores(indice + 1)])
            if encolado:
                continue
            try:
                last_sb = _aplicar_sandbox_menu(inbound)
            except Exception:
                liberar_eventos(CANAL_META, _posteriores(indice + 1))
                return _error_sincronico(CANAL_META, sid)
        if isinstance(last_sb, HttpResponse):
            return last_sb
        return HttpResponse('OK')

    for indice, inbound in enumerate(inbounds):
        sid = _sid_de(inbound)
        try:
            _procesar_meta_webhook(_payload_un_mensaje(payload, sid) if sid else payload)
        except Exception:
            liberar_eventos(CANAL_META, _posteriores(indice + 1))
            return _error_sincronico(CANAL_META, sid)
    return None


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_procesar_twilio_reclamado` — `core/views/entrada.py:125`

```python
# core/views/entrada.py:125
def _procesar_twilio_reclamado(data, ids, es_comercial):
    sid = ids[0] if ids else _sid_de(data)
    try:
        sb = _aplicar_sandbox_menu(data)
    except Exception:
        return _error_sincronico(CANAL_TWILIO, sid)
    if sb is not None:
        return sb
    try:
        if es_comercial(data):
            encolado = _encolar_bot_comercial_si_async(data)
        else:
            encolado = _encolar_twilio_edu_si_async(data)
    except Exception:
        return _error_encolado(CANAL_TWILIO, ids or ([sid] if sid else []))
    if encolado:
        return None
    try:
        if es_comercial(data):
            logger.info("🧭 Router webhook: Twilio destino comercial/agro detectado")
            _procesar_bot_comercial_twilio_webhook(data)
            return None
        logger.info("🧭 Router webhook: Twilio destino educativo detectado")
        return _procesar_twilio_webhook(data)
    except Exception:
        return _error_sincronico(CANAL_TWILIO, sid)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `whatsapp_webhook` — `core/views/entrada.py:153`

```python
# core/views/entrada.py:153
@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook universal para WhatsApp (Meta + Twilio)
    GET: Verificación del token
    POST: Procesa mensajes entrantes de ambos proveedores
    """
    if request.method == 'GET':
        # Verificación para Meta WhatsApp
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'eki_webhook_verify_token')
        if verify_token and expected and verify_token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        import sys
        print("🔵 WEBHOOK RECIBIÓ POST", flush=True)
        logger.info("🔵 WEBHOOK RECIBIÓ POST")

        # Raw body → firma Twilio (HMAC/compare_digest) antes de procesar inbound Twilio.
        # Meta Cloud API (JSON con entry) no usa X-Twilio-Signature.
        from core.twilio_webhook_security import (
            looks_like_meta_whatsapp_payload,
            validate_twilio_request,
        )
        raw_body = request.body
        if not looks_like_meta_whatsapp_payload(raw_body):
            denied = validate_twilio_request(request)
            if denied is not None:
                return denied

        def _es_destino_bot_comercial(data):
            from core.bot_comercial_routing import es_destino_bot_comercial
            return es_destino_bot_comercial(data)

        try:
            # Intentar parsear como JSON (Meta)
            payload = json.loads(request.body.decode('utf-8'))
            print(f"🔵 Payload (JSON): {payload}", flush=True)
            logger.info(f"🔵 Payload (JSON): {payload}")
            
            # Detectar si es Meta o Twilio
            if 'entry' in payload:
                logger.info("📍 Detectado: META WhatsApp")
                if firma_meta_invalida(
                    raw_body,
                    request.META.get('HTTP_X_HUB_SIGNATURE_256', ''),
                ):
                    logger.warning('meta_webhook_firma_invalida')
                    return HttpResponse('Forbidden', status=403)
                payload, ids_meta, seguir = preparar_payload_meta(payload)
                if not seguir:
                    return HttpResponse('OK')

                try:
                    from core.meta_waba import aplicar_eventos_plantilla

                    aplicar_eventos_plantilla(
                        payload,
                        raw_body,
                        request.META.get('HTTP_X_HUB_SIGNATURE_256', ''),
                    )
                except Exception:
                    logger.exception('meta_template_status_update_fail')
                resultado_meta = _procesar_meta_por_mensaje(payload)
                if isinstance(resultado_meta, HttpResponse):
                    return resultado_meta
            else:
                # Podría ser Twilio con JSON — intentar procesarlo como Twilio también
                print("⚠️ JSON recibido pero no es Meta — intentando como Twilio", flush=True)
                logger.info("⚠️ JSON recibido pero no es Meta, verificando si tiene datos Twilio")
                # Algunos webhooks de Twilio pueden llegar como JSON
                if 'Body' in payload or 'From' in payload or 'MessageStatus' in payload:
                    print("🔵 JSON con datos Twilio detectado — procesando", flush=True)
                    logger.info(
                        "🧪 Twilio JSON inbound | path=%s | from=%s | to=%s | sid=%s",
                        request.path,
                        payload.get('From', ''),
                        payload.get('To', ''),
                        payload.get('MessageSid', ''),
                    )
                    seguir_tw, ids_tw = reclamar_twilio(
                        payload,
                        es_status=_es_status_callback_twilio(payload),
                    )
                    if not seguir_tw:
                        return HttpResponse('OK')

                    resultado_tw = _procesar_twilio_reclamado(
                        payload, ids_tw, _es_destino_bot_comercial,
                    )
                    if isinstance(resultado_tw, HttpResponse):
                        return resultado_tw
                else:
                    print("⚠️ JSON desconocido — ignorando", flush=True)
                return HttpResponse('OK')
                
        except json.JSONDecodeError:
            # Podría ser Twilio (form-data)
            print("🔵 Payload (Form-Data) - Probablemente Twilio", flush=True)
            print(f"POST keys: {list(request.POST.keys())}", flush=True)
            logger.info("🔵 Payload (Form-Data) - Probablemente Twilio")
            logger.info(
                "🧪 Twilio Form inbound | path=%s | from=%s | to=%s | sid=%s",
                request.path,
                request.POST.get('From', ''),
                request.POST.get('To', ''),
                request.POST.get('MessageSid', ''),
            )
            seguir_tw, ids_tw = reclamar_twilio(
                request.POST,
                es_status=_es_status_callback_twilio(request.POST),
            )
            if not seguir_tw:
                return HttpResponse('OK')

            twilio_result = _procesar_twilio_reclamado(
                request.POST, ids_tw, _es_destino_bot_comercial,
            )
            if isinstance(twilio_result, HttpResponse):
                return twilio_result
        
        except Exception as e:
            print(f"❌ Error en webhook: {str(e)}", flush=True)
            logger.error(f"❌ Error en webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse('Error', status=500)

        return HttpResponse('OK')
```

**Contrato**
- Entradas: request HTTP GET (verify Meta) o POST (Meta JSON o Twilio form/JSON).
- Salidas: `HttpResponse` 200/403/405/500.
- Efectos: valida firma Twilio si el body no parece Meta. Valida firma Meta si `entry` y `firma_meta_invalida`. Reclama ids (`preparar_payload_meta` / `reclamar_twilio`) antes de procesar. Encola Celery o procesa en el request. Loguea el payload JSON completo (`print` y `logger.info`).
- Excepciones: JSON inválido se trata como form Twilio. Cualquier otra excepción → 500.


### `webhook_comercial` — `core/views/webhook_comercial.py:1`

```python
# core/views/webhook_comercial.py:1
import json

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

# legacy lo sustituye al cargar webhook_meta (la llamada vive en este módulo).
_aplicar_sandbox_menu = None

from .legacy import logger
from .twilio_transporte import (
    _es_status_callback_twilio,
    _twilio_post_plano,
)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_encolar_bot_comercial_si_async` — `core/views/webhook_comercial.py:18`

```python
# core/views/webhook_comercial.py:18
def _encolar_bot_comercial_si_async(post_data, *, forzar_canal: bool = False) -> bool:
    """Encola Nat (RAG/LLM) en Celery si NAT_WEBHOOK_CELERY_ASYNC=true."""
    if not getattr(settings, 'NAT_WEBHOOK_CELERY_ASYNC', False):
        return False
    if _es_status_callback_twilio(post_data):
        return False
    from core.tasks import procesar_bot_comercial_webhook_async

    try:
        procesar_bot_comercial_webhook_async.delay(
            _twilio_post_plano(post_data),
            forzar_canal=forzar_canal,
        )
    except Exception:
        logger.exception(
            "❌ No se pudo encolar Nat (Redis/Celery) | sid=%s — fallback síncrono",
            post_data.get('MessageSid', ''),
        )
        return False
    logger.info(
        "📤 Webhook Nat encolado en Celery | sid=%s | forzar=%s",
        post_data.get('MessageSid', ''),
        forzar_canal,
    )
    return True

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `bot_comercial_webhook` — `core/views/webhook_comercial.py:44`

```python
# core/views/webhook_comercial.py:44
@csrf_exempt
def bot_comercial_webhook(request):
    """Webhook dedicado para el número de WhatsApp del bot comercial."""
    if request.method != 'POST':
        return HttpResponse('Method Not Allowed', status=405)

    from core.twilio_webhook_security import validate_twilio_request

    denied = validate_twilio_request(request)
    if denied is not None:
        return denied

    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
            sb = _aplicar_sandbox_menu(payload)
            if sb is not None:
                return sb
            if not _encolar_bot_comercial_si_async(payload, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(payload, forzar_canal=True)
        except json.JSONDecodeError:
            sb = _aplicar_sandbox_menu(request.POST)
            if sb is not None:
                return sb
            if not _encolar_bot_comercial_si_async(request.POST, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(request.POST, forzar_canal=True)
        return HttpResponse('OK')
    except Exception as e:
        logger.error(f"❌ Error webhook bot comercial: {e}")
        return HttpResponse('Error', status=500)
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `twilio_webhook_security` — `core/twilio_webhook_security.py:1`

```python
# core/twilio_webhook_security.py:1
"""
Validación de firma Twilio en webhooks WhatsApp.

Orden: bytes crudos (request.body) → HMAC vía RequestValidator
(usa hmac.compare_digest) → recién entonces el caller parsea/procesa.
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `twilio_signature_validation_enabled` — `core/twilio_webhook_security.py:20`

```python
# core/twilio_webhook_security.py:20
def twilio_signature_validation_enabled() -> bool:
    return bool(getattr(settings, 'TWILIO_VALIDATE_SIGNATURE', False))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `looks_like_meta_whatsapp_payload` — `core/twilio_webhook_security.py:24`

```python
# core/twilio_webhook_security.py:24
def looks_like_meta_whatsapp_payload(raw_body: bytes) -> bool:
    """True si el body JSON parece webhook Meta Cloud API (entry/object)."""
    if not raw_body:
        return False
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False
    return isinstance(payload, dict) and ('entry' in payload or payload.get('object') == 'whatsapp_business_account')


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_public_webhook_url` — `core/twilio_webhook_security.py:35`

```python
# core/twilio_webhook_security.py:35
def _public_webhook_url(request: HttpRequest) -> str:
    """
    URL absoluta que Twilio firmó. Respeta override y X-Forwarded-Proto (EB/ALB).
    """
    override = (getattr(settings, 'TWILIO_WEBHOOK_PUBLIC_URL', '') or '').strip()
    if override:
        base = override.rstrip('/')
        path = request.path
        if not path.startswith('/'):
            path = '/' + path
        qs = request.META.get('QUERY_STRING', '')
        url = f'{base}{path}'
        if qs:
            url = f'{url}?{qs}'
        return url

    url = request.build_absolute_uri()
    forwarded = (request.META.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip().lower()
    if forwarded == 'https' and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    elif getattr(settings, 'SECURE_SSL_REDIRECT', False) and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]

    # Normalizar sin fragment
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `validate_twilio_request` — `core/twilio_webhook_security.py:63`

```python
# core/twilio_webhook_security.py:63
def validate_twilio_request(request: HttpRequest) -> Optional[HttpResponse]:
    """
    Valida X-Twilio-Signature. Retorna HttpResponse 403 si falla, None si OK / skip.
    """
    if not twilio_signature_validation_enabled():
        return None

    # Touch raw body primero (canon: bytes crudos antes de confiar en el request)
    raw_body = request.body

    signature = (request.META.get('HTTP_X_TWILIO_SIGNATURE') or '').strip()
    if not signature:
        logger.warning(
            'twilio_webhook_rejected',
            extra={'reason': 'missing_signature', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    auth_token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not auth_token:
        logger.error(
            'twilio_webhook_rejected',
            extra={'reason': 'missing_auth_token', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    from twilio.request_validator import RequestValidator

    url = _public_webhook_url(request)
    validator = RequestValidator(auth_token)
    content_type = (request.content_type or '').lower()

    if 'application/json' in content_type or (
        raw_body[:1] in (b'{', b'[') and 'application/x-www-form-urlencoded' not in content_type
    ):
        # JSON: body string (soporta bodySHA256 en query si aplica)
        params = raw_body.decode('utf-8') if raw_body else ''
        ok = validator.validate(url, params, signature)
    else:
        # form-urlencoded típico de Twilio WhatsApp
        ok = validator.validate(url, request.POST, signature)

    if not ok:
        logger.warning(
            'twilio_webhook_rejected',
            extra={'reason': 'invalid_signature', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    return None
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `webhook_evento` — `core/webhook_evento.py:1`

```python
# core/webhook_evento.py:1
"""Idempotencia del webhook: un wamid o MessageSid se reclama una sola vez."""
from __future__ import annotations

import copy
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db import models

logger = logging.getLogger(__name__)

CANAL_META = 'meta'
CANAL_TWILIO = 'twilio'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `WebhookEventoProcesado` — `core/webhook_evento.py:17`

```python
# core/webhook_evento.py:17
class WebhookEventoProcesado(models.Model):
    canal = models.CharField(max_length=10)
    external_id = models.CharField(max_length=128)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        constraints = [
            models.UniqueConstraint(
                fields=['canal', 'external_id'],
                name='uniq_webhook_evento',
            ),
        ]

    def __str__(self):
        return f'{self.canal}:{self.external_id}'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `external_id_de_payload` — `core/webhook_evento.py:35`

```python
# core/webhook_evento.py:35
def external_id_de_payload(datos) -> str:
    """Id del mensaje en las tres tareas del webhook.

    Twilio educativo y Nat: MessageSid del POST.
    Meta sandbox: inbound_desde_meta_message copia message['id'] (wamid) a MessageSid.
    Si el dict solo trae id, se usa ese valor.
    """
    if not isinstance(datos, dict):
        return ''
    return str(datos.get('MessageSid') or datos.get('id') or '').strip()[:128]


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `reclamar_evento` — `core/webhook_evento.py:47`

```python
# core/webhook_evento.py:47
def reclamar_evento(canal, external_id) -> bool:
    try:
        with transaction.atomic():
            WebhookEventoProcesado.objects.create(canal=canal, external_id=external_id)
        return True
    except IntegrityError:
        return False


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `WebhookFallido` — `core/webhook_evento.py:56`

```python
# core/webhook_evento.py:56
class WebhookFallido(models.Model):
    """Mensaje que la tarea no pudo terminar. El payload tiene teléfono: solo staff, purga a 10 días."""

    canal = models.CharField(max_length=16)
    external_id = models.CharField(max_length=128, db_index=True)
    payload = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'webhook fallido'
        verbose_name_plural = 'webhooks fallidos'

    def __str__(self):
        return f'{self.canal}:{self.external_id}'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `purgar_webhooks_fallidos` — `core/webhook_evento.py:74`

```python
# core/webhook_evento.py:74
def purgar_webhooks_fallidos(dias: int = 10) -> int:
    """Borra fallos más viejos que `dias`. La usa limpiar_logs_antiguos."""
    from django.utils import timezone

    limite = timezone.now() - timezone.timedelta(days=dias)
    eliminados, _ = WebhookFallido.objects.filter(creado__lt=limite).delete()
    return eliminados


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `purgar_eventos_procesados` — `core/webhook_evento.py:83`

```python
# core/webhook_evento.py:83
def purgar_eventos_procesados(dias: int = 10) -> int:
    """Borra reclamos más viejos que `dias`. La usa limpiar_logs_antiguos."""
    from django.utils import timezone

    limite = timezone.now() - timezone.timedelta(days=dias)
    eliminados, _ = WebhookEventoProcesado.objects.filter(creado__lt=limite).delete()
    return eliminados


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `liberar_eventos` — `core/webhook_evento.py:92`

```python
# core/webhook_evento.py:92
def liberar_eventos(canal, external_ids) -> None:
    ids = [str(item) for item in (external_ids or []) if item]
    if not ids:
        return
    WebhookEventoProcesado.objects.filter(canal=canal, external_id__in=ids).delete()
    if canal == CANAL_META:
        try:
            from django.core.cache import cache

            cache.delete_many([f'sandbox_in:{sid}' for sid in ids])
        except Exception:
            logger.exception('webhook_liberar_cache_fail')


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `firma_meta_invalida` — `core/webhook_evento.py:106`

```python
# core/webhook_evento.py:106
def firma_meta_invalida(raw_body: bytes, signature_header: str) -> bool:
    """True si hay que rechazar el POST de mensajes antes de reclamar.

    Con WHATSAPP_REQUIRE_SIGNATURE=False (default), un secreto vacío no rechaza.
    Con el flag en True, secreto vacío o firma inválida rechazan.
    """
    secret = (getattr(settings, 'WHATSAPP_APP_SECRET', None) or '').strip()
    exigir = bool(getattr(settings, 'WHATSAPP_REQUIRE_SIGNATURE', False))
    if not secret:
        return exigir
    from core.meta_waba import firma_meta_ok

    return not firma_meta_ok(raw_body or b'', signature_header or '', secret)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `preparar_payload_meta` — `core/webhook_evento.py:121`

```python
# core/webhook_evento.py:121
def preparar_payload_meta(payload: dict) -> tuple[dict, list[str], bool]:
    """Reclama cada messages[].id. No toca statuses.

    Devuelve (payload filtrado, ids reclamados, seguir).
    seguir es False cuando todos los mensajes ya estaban reclamados
    y el payload no trae statuses ni otro tipo de cambio.
    """
    payload = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    reclamados: list[str] = []
    vio_mensajes = False
    quedo_alguno = False
    hay_otro_trabajo = False

    for entry in payload.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            field = change.get('field')
            value = change.get('value')
            if not isinstance(value, dict):
                if field and field != 'messages':
                    hay_otro_trabajo = True
                continue
            if value.get('statuses'):
                hay_otro_trabajo = True
            if field and field != 'messages':
                hay_otro_trabajo = True
            messages = value.get('messages') or []
            if not isinstance(messages, list):
                continue
            kept = []
            for message in messages:
                if not isinstance(message, dict):
                    vio_mensajes = True
                    quedo_alguno = True
                    kept.append(message)
                    continue
                mid = str(message.get('id') or '').strip()[:128]
                vio_mensajes = True
                if not mid:
                    quedo_alguno = True
                    kept.append(message)
                    continue
                if reclamar_evento(CANAL_META, mid):
                    reclamados.append(mid)
                    quedo_alguno = True
                    kept.append(message)
            value['messages'] = kept

    if vio_mensajes and not quedo_alguno and not hay_otro_trabajo:
        return payload, reclamados, False
    return payload, reclamados, True


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `reclamar_twilio` — `core/webhook_evento.py:177`

```python
# core/webhook_evento.py:177
def reclamar_twilio(data, *, es_status: bool) -> tuple[bool, list[str]]:
    """Status callbacks no se deduplican. Un MessageSid nuevo se reclama."""
    if es_status:
        return True, []
    sid = str((data or {}).get('MessageSid') or '').strip()[:128]
    if not sid:
        return True, []
    if not reclamar_evento(CANAL_TWILIO, sid):
        return False, []
    return True, [sid]
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `locks` — `core/locks.py:1`

```python
# core/locks.py:1
"""Candado Redis por teléfono para los webhooks de WhatsApp.

El orden estricto entre mensajes del mismo teléfono no está garantizado:
si uno agota la espera y reintenta, otro que llegó después puede tomar el
candado primero. El candado evita que se procesen a la vez, no que salgan
en el orden de llegada.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from contextlib import contextmanager

from django.conf import settings

logger = logging.getLogger(__name__)

LOCK_TIMEOUT = 90
LOCK_BLOCKING = 10
ENTREGA_TTL_SEG = 3600
ENTREGA_TOPE = 3


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `telefono_hash` — `core/locks.py:25`

```python
# core/locks.py:25
def telefono_hash(telefono_normalizado: str) -> str:
    """HMAC-SHA256(SECRET_KEY, teléfono) en 16 hex. No es reversible por fuerza bruta."""
    secreto = str(getattr(settings, 'SECRET_KEY', '') or '').encode('utf-8')
    base = (telefono_normalizado or '').encode('utf-8')
    return hmac.new(secreto, base, hashlib.sha256).hexdigest()[:16]


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `clave_entrega` — `core/locks.py:32`

```python
# core/locks.py:32
def clave_entrega(canal: str, external_id: str) -> str:
    return f'eki:wa:entrega:{canal}:{external_id}'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `contar_entrega` — `core/locks.py:36`

```python
# core/locks.py:36
def contar_entrega(canal: str, external_id: str) -> int:
    """Cuenta reentregas del broker por (canal, external_id). TTL de 1 h.

    Sin external_id no hay clave estable: devuelve 1 y no escribe.
    El TTL se pone en la primera entrega y, si faltara, en la siguiente.
    El caller solo llama esto cuando delivery_info['redelivered'] es True.
    """
    ext = (external_id or '').strip()
    if not ext:
        return 1
    clave = clave_entrega(canal, ext)
    cliente = _cliente_redis()
    try:
        n = int(cliente.incr(clave))
        if n == 1 or int(cliente.ttl(clave)) < 0:
            cliente.expire(clave, ENTREGA_TTL_SEG)
        return n
    finally:
        try:
            cliente.close()
        except Exception:
            pass


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `borrar_entrega` — `core/locks.py:60`

```python
# core/locks.py:60
def borrar_entrega(canal: str, external_id: str) -> None:
    """Quita el contador para que un reproceso staff no herede reentregas viejas."""
    ext = (external_id or '').strip()
    if not ext:
        return
    clave = clave_entrega(canal or '', ext)
    try:
        cliente = _cliente_redis()
        try:
            pool = cliente.connection_pool
            pool.connection_kwargs['socket_connect_timeout'] = 1
            pool.connection_kwargs['socket_timeout'] = 1
            cliente.delete(clave)
        finally:
            try:
                cliente.close()
            except Exception:
                pass
    except Exception:
        logger.exception(
            'webhook_entrega_no_borrada canal=%s external_id=%s',
            canal,
            ext,
        )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_cliente_redis` — `core/locks.py:86`

```python
# core/locks.py:86
def _cliente_redis():
    from redis import Redis

    url = (
        getattr(settings, 'CELERY_BROKER_URL', None)
        or 'redis://localhost:6379/0'
    )
    return Redis.from_url(url)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `wa_reply_context` — `core/wa_reply_context.py:1`

```python
# core/wa_reply_context.py:1
"""From sticky para replies WhatsApp (sandbox menú dual).

Cuando el usuario escribe al sandbox Twilio, las respuestas deben salir
del mismo número aunque el modo sea «cursos» (edu no pasa from_number).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_reply_from: ContextVar[str | None] = ContextVar('wa_reply_from', default=None)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `get_reply_from_override` — `core/wa_reply_context.py:14`

```python
# core/wa_reply_context.py:14
def get_reply_from_override() -> str | None:
    return _reply_from.get()


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `reply_from` — `core/wa_reply_context.py:18`

```python
# core/wa_reply_context.py:18
@contextmanager
def reply_from(numero: str | None):
    token = _reply_from.set((numero or '').strip() or None)
    try:
        yield
    finally:
        _reply_from.reset(token)
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `bot_comercial_routing` — `core/bot_comercial_routing.py:1`

```python
# core/bot_comercial_routing.py:1
"""Enrutado WhatsApp: Nat comercial vs bot educativo.

    El webhook compartido (`/webhook/whatsapp/`) decide el canal por el número destino (To).
Debe incluir la línea global y cada `Cliente.numero_whatsapp_nat`.
El sandbox de agentes/cursos-menú corre por Meta (`SANDBOX_PROVEEDOR=meta`) y no entra aquí.
"""

from __future__ import annotations

from django.conf import settings

from core.nati import normalizar_telefono_whatsapp


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_sandbox_number` — `core/bot_comercial_routing.py:15`

```python
# core/bot_comercial_routing.py:15
def _sandbox_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '[REDACTADO]') or '[REDACTADO]'
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_global_comercial_number` — `core/bot_comercial_routing.py:21`

```python
# core/bot_comercial_routing.py:21
def _global_comercial_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_WHATSAPP_NUMBER', '') or ''
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `numeros_destino_comercial` — `core/bot_comercial_routing.py:27`

```python
# core/bot_comercial_routing.py:27
def numeros_destino_comercial(*, incluir_orgs: bool = True) -> set[str]:
    """
    Conjunto de números (solo dígitos) que deben ir a Nat comercial (Twilio).
    """
    out: set[str] = set()
    global_n = _global_comercial_number()
    if global_n:
        out.add(global_n)
    sandbox = _sandbox_number()
    if sandbox:
        from core.sandbox_canal import sandbox_via_meta

        if not sandbox_via_meta():
            out.add(sandbox)

    if incluir_orgs:
        from core.models import Cliente

        for raw in (
            Cliente.objects.filter(activo=True)
            .exclude(numero_whatsapp_nat='')
            .values_list('numero_whatsapp_nat', flat=True)
        ):
            n = normalizar_telefono_whatsapp(raw)
            if n:
                out.add(n)
    return out


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `es_destino_bot_comercial` — `core/bot_comercial_routing.py:56`

```python
# core/bot_comercial_routing.py:56
def es_destino_bot_comercial(to_or_payload) -> bool:
    """
    True si el mensaje debe procesarse como Nat (no educativo).

    Acepta el string `To` o un mapping estilo Twilio (dict / QueryDict) con clave `To`.
    """
    if bool(getattr(settings, 'BOT_COMERCIAL_FORCE_ROUTING', False)):
        return True

    if isinstance(to_or_payload, str):
        to_raw = to_or_payload
    elif to_or_payload is None:
        to_raw = ''
    else:
        try:
            to_raw = to_or_payload.get('To', '')  # type: ignore[union-attr]
        except Exception:
            to_raw = ''

    to_limpio = normalizar_telefono_whatsapp(to_raw)
    if not to_limpio:
        return False

    return to_limpio in numeros_destino_comercial(incluir_orgs=True)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `es_numero_comercial_conocido` — `core/bot_comercial_routing.py:82`

```python
# core/bot_comercial_routing.py:82
def es_numero_comercial_conocido(to: str) -> bool:
    """Defensa en profundidad dentro del processor (incluye org + sandbox + global)."""
    to_limpio = normalizar_telefono_whatsapp(to)
    if not to_limpio:
        return False
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.

