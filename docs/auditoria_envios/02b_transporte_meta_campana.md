# 02b — Campaña Meta, alta de plantillas y webhook Meta legado

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `campana_meta_habilitada` — `core/meta_waba.py:37`

```python
# core/meta_waba.py:37
def campana_meta_habilitada() -> bool:
    return bool(getattr(settings, 'EKI_CAMPANA_META_ENABLED', True))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_version` — `core/meta_waba.py:41`

```python
# core/meta_waba.py:41
def _version() -> str:
    return (getattr(settings, 'WHATSAPP_API_VERSION', None) or 'v21.0').strip() or 'v21.0'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_token` — `core/meta_waba.py:45`

```python
# core/meta_waba.py:45
def _token() -> str:
    return (getattr(settings, 'WHATSAPP_TOKEN', None) or '').strip()


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_waba` — `core/meta_waba.py:49`

```python
# core/meta_waba.py:49
def _waba() -> str:
    return (getattr(settings, 'WHATSAPP_BUSINESS_ACCOUNT_ID', None) or '').strip()


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_phone_default` — `core/meta_waba.py:53`

```python
# core/meta_waba.py:53
def _phone_default() -> str:
    return (getattr(settings, 'WHATSAPP_PHONE_ID', None) or '').strip()


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_headers` — `core/meta_waba.py:57`

```python
# core/meta_waba.py:57
def _headers() -> dict[str, str] | None:
    token = _token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `firma_meta_ok` — `core/meta_waba.py:67`

```python
# core/meta_waba.py:67
def firma_meta_ok(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """HMAC-SHA256 del body crudo. compare_digest, nunca ==."""
    secret = (secret or '').strip()
    header = (signature_header or '').strip()
    if not secret or not header or raw_body is None:
        return False
    if header.lower().startswith('sha256='):
        header = header.split('=', 1)[1].strip()
    digest = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    if len(digest) != len(header):
        return False
    return hmac.compare_digest(digest, header)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_error_meta` — `core/meta_waba.py:81`

```python
# core/meta_waba.py:81
def _error_meta(data: dict) -> dict:
    err = data.get('error') if isinstance(data, dict) else None
    if not isinstance(err, dict):
        err = {}
    code = err.get('code')
    sub = err.get('error_subcode')
    mensaje = err.get('error_user_msg') or err.get('message') or 'Error de Meta'
    return {
        'code': '' if code is None else str(code),
        'subcode': '' if sub is None else str(sub),
        'message': str(mensaje)[:2000],
    }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_es_rate_limit` — `core/meta_waba.py:95`

```python
# core/meta_waba.py:95
def _es_rate_limit(code: str) -> bool:
    try:
        return int(code) in _RATE_CODES
    except (TypeError, ValueError):
        return False


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `normalizar_estado` — `core/meta_waba.py:102`

```python
# core/meta_waba.py:102
def normalizar_estado(evento: str) -> str:
    bruto = (evento or '').strip().upper()
    if bruto in _ESTADOS_OK:
        return bruto
    if bruto in ('FLAGGED', 'PENDING_DELETION'):
        return 'PAUSED' if bruto == 'FLAGGED' else 'PENDING'
    return 'ERROR'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `armar_componentes_alta` — `core/meta_waba.py:111`

```python
# core/meta_waba.py:111
def armar_componentes_alta(plantilla: PlantillaMeta) -> list[dict]:
    """Payload de creación (Graph message_templates)."""
    componentes: list[dict] = []
    header = (plantilla.header_texto or '').strip()
    if header:
        bloque: dict = {'type': 'HEADER', 'format': 'TEXT', 'text': header}
        if variables_en(header):
            bloque['example'] = {'header_text': [(plantilla.header_ejemplo or '').strip() or 'ejemplo']}
        componentes.append(bloque)

    cuerpo = (plantilla.cuerpo or '').strip()
    body: dict = {'type': 'BODY', 'text': cuerpo}
    n_body = len(set(variables_en(cuerpo)))
    if n_body:
        ejemplos = ejemplos_lista(plantilla.ejemplos_cuerpo)
        body['example'] = {'body_text': [ejemplos[:n_body]]}
    componentes.append(body)

    footer = (plantilla.footer or '').strip()
    if footer:
        componentes.append({'type': 'FOOTER', 'text': footer})

    botones = []
    for n in (1, 2):
        tipo = getattr(plantilla, f'boton_{n}_tipo') or ''
        texto = (getattr(plantilla, f'boton_{n}_texto') or '').strip()
        if not tipo or not texto:
            continue
        if tipo == 'QUICK_REPLY':
            botones.append({'type': 'QUICK_REPLY', 'text': texto})
        elif tipo == 'URL':
            url = (getattr(plantilla, f'boton_{n}_url') or '').strip()
            btn: dict = {'type': 'URL', 'text': texto, 'url': url}
            if variables_en(url):
                btn['example'] = [(getattr(plantilla, f'boton_{n}_ejemplo') or '').strip() or 'x']
            botones.append(btn)
    if botones:
        componentes.append({'type': 'BUTTONS', 'buttons': botones})
    return componentes


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_post` — `core/meta_waba.py:152`

```python
# core/meta_waba.py:152
def _post(url: str, payload: dict) -> tuple[int, dict]:
    headers = _headers()
    if not headers:
        return 0, {'error': {'message': 'WHATSAPP_TOKEN no configurado', 'code': 'NO_TOKEN'}}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.Timeout:
        return 0, {'error': {'message': 'Timeout al hablar con Meta', 'code': 'TIMEOUT'}}
    except requests.RequestException as exc:
        return 0, {'error': {'message': str(exc)[:300], 'code': 'RED'}}
    try:
        data = resp.json()
    except ValueError:
        data = {'error': {'message': (resp.text or '')[:300], 'code': resp.status_code}}
    if not isinstance(data, dict):
        data = {'error': {'message': 'Respuesta no JSON', 'code': resp.status_code}}
    return resp.status_code, data

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_destinatarios` — `core/meta_waba.py:546`

```python
# core/meta_waba.py:546
def _destinatarios(campana: CampanaMeta):
    if campana.grupo_id:
        return campana.grupo.estudiantes.filter(activo=True)
    return campana.destinatarios.filter(activo=True)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_campana_meta` — `core/meta_waba.py:552`

```python
# core/meta_waba.py:552
def ejecutar_campana_meta(campana: CampanaMeta) -> dict:
    if not campana_meta_habilitada():
        raise ValueError('Campaña Meta está apagada (EKI_CAMPANA_META_ENABLED).')
    plantilla = campana.plantilla
    if plantilla.estado != 'APPROVED':
        raise ValueError(
            f'La plantilla «{plantilla.nombre_interno}» está en {plantilla.estado}. '
            f'Solo se envía si está Aprobada.'
        )
    phone_id = (campana.phone_number_id or _phone_default()).strip()
    waba = (plantilla.waba_id or _waba()).strip()
    ok, motivo = phone_pertenece_a_waba(phone_id, waba)
    if not ok:
        raise ValueError(motivo)

    destinatarios = list(_destinatarios(campana))
    enviados = 0
    fallidos = 0
    rate_limit = False
    for estudiante in destinatarios:
        if EnvioCampanaMeta.objects.filter(
            campana=campana, estudiante=estudiante, estado='ENVIADO',
        ).exists():
            continue
        try:
            componentes = _parametros_envio(plantilla, campana, estudiante)
            payload = {
                'messaging_product': 'whatsapp',
                'to': str(estudiante.telefono or '').lstrip('+'),
                'type': 'template',
                'template': {
                    'name': plantilla.meta_name,
                    'language': {'code': plantilla.idioma or 'es'},
                },
            }
            if componentes:
                payload['template']['components'] = componentes
            url = f'https://graph.facebook.com/{_version()}/{phone_id}/messages'
            status, data = _post(url, payload)
            if status in (200, 201) and data.get('messages'):
                wamid = str((data.get('messages') or [{}])[0].get('id') or '')
                EnvioCampanaMeta.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    wamid=wamid,
                    respuesta='sent',
                )
                enviados += 1
            else:
                err = _error_meta(data)
                EnvioCampanaMeta.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='FALLIDO',
                    respuesta=err['message'][:2000],
                )
                fallidos += 1
                if _es_rate_limit(err['code']):
                    rate_limit = True
                    break
        except ValueError as exc:
            EnvioCampanaMeta.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta=str(exc)[:2000],
            )
            fallidos += 1
        time.sleep(0.35)

    campana.total_enviados = EnvioCampanaMeta.objects.filter(
        campana=campana, estado='ENVIADO',
    ).count()
    if not rate_limit:
        campana.ejecutada = True
    campana.save(update_fields=['total_enviados', 'ejecutada'])
    return {
        'total': len(destinatarios),
        'enviados': enviados,
        'fallidos': fallidos,
        'rate_limit': rate_limit,
    }


```

**Contrato**
- Entradas: instancia `CampanaMeta`.
- Salidas: dict total/enviados/fallidos/rate_limit. Lanza `ValueError` si la feature está apagada, la plantilla no está APPROVED o el phone id no pertenece al WABA.
- Efectos: POST template por estudiante a Graph (`timeout` 30s en `_post`). Omite si ya hay `EnvioCampanaMeta` ENVIADO para ese par. `time.sleep(0.35)`. Corta el lote si el código es rate limit (`_RATE_CODES`). Marca `ejecutada` solo si no hubo rate limit.
- Excepciones: `ValueError` de parámetros por estudiante se guarda como FALLIDO y sigue. Errores de red los convierte `_post` en status 0.


### `encolar_campana_meta` — `core/meta_waba.py:637`

```python
# core/meta_waba.py:637
def encolar_campana_meta(campana_id: int) -> str:
    def _fondo():
        try:
            campana = CampanaMeta.objects.select_related('plantilla', 'grupo').get(pk=campana_id)
            ejecutar_campana_meta(campana)
        except Exception:
            logger.exception('campana_meta_background_fail id=%s', campana_id)

    try:
        from core.tasks import ejecutar_campana_meta_async

        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            threading.Thread(target=_fondo, daemon=True, name=f'campana-meta-{campana_id}').start()
            return 'background'
        ejecutar_campana_meta_async.delay(campana_id)
        return 'celery'
    except Exception:
        logger.warning('campana_meta_celery_no id=%s', campana_id)
        threading.Thread(target=_fondo, daemon=True, name=f'campana-meta-{campana_id}').start()
        return 'background'
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `meta_templates` — `core/meta_templates.py:1`

```python
# core/meta_templates.py:1
"""
Utilidades para integración con Meta WhatsApp Business API
Específicamente para gestión de plantillas (templates)
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_plantilla_a_meta` — `core/meta_templates.py:12`

```python
# core/meta_templates.py:12
def enviar_plantilla_a_meta(nombre_plantilla, contenido, categoria='MARKETING', idioma='es'):
    """
    Envía una plantilla a Meta para aprobación.
    
    Args:
        nombre_plantilla: Nombre interno de la plantilla (sin espacios, minúsculas, guiones bajos)
        contenido: Texto de la plantilla
        categoria: MARKETING, UTILITY, o AUTHENTICATION
        idioma: Código de idioma (es, en, etc.)
    
    Returns:
        dict con 'success' (bool), 'template_id' (str), 'status' (str), 'message' (str)
    """
    
    # Validar configuración
    waba_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID
    access_token = settings.WHATSAPP_TOKEN
    
    if not waba_id or not access_token:
        logger.error("❌ WHATSAPP_BUSINESS_ACCOUNT_ID o WHATSAPP_TOKEN no configurados")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': 'Credenciales de Meta no configuradas. Configura WHATSAPP_BUSINESS_ACCOUNT_ID y WHATSAPP_TOKEN'
        }
    
    # Sanitizar nombre de plantilla (Meta requiere formato específico)
    nombre_sanitizado = nombre_plantilla.lower().replace(' ', '_').replace('-', '_')
    nombre_sanitizado = ''.join(c for c in nombre_sanitizado if c.isalnum() or c == '_')
    
    # Construir URL del endpoint
    url = f"https://graph.facebook.com/v19.0/{waba_id}/message_templates"
    
    # Construir payload
    payload = {
        "name": nombre_sanitizado,
        "language": idioma,
        "category": categoria,
        "components": [
            {
                "type": "BODY",
                "text": contenido
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"📤 Enviando plantilla '{nombre_sanitizado}' a Meta para revisión...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Payload: {payload}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response_data = response.json()
        
        logger.debug(f"Respuesta Meta: {response_data}")
        
        if response.status_code == 200 and response_data.get('id'):
            template_id = response_data.get('id')
            status = response_data.get('status', 'PENDING')
            
            logger.info(f"✅ Plantilla enviada exitosamente - ID: {template_id}, Estado: {status}")
            
            return {
                'success': True,
                'template_id': template_id,
                'status': status,
                'message': f'Plantilla enviada a Meta para revisión. ID: {template_id}',
                'nombre_meta': nombre_sanitizado
            }
        else:
            error_message = response_data.get('error', {}).get('message', 'Error desconocido')
            error_code = response_data.get('error', {}).get('code', 'N/A')
            
            logger.error(f"❌ Error de Meta API: {error_message} (Código: {error_code})")
            
            return {
                'success': False,
                'template_id': None,
                'status': 'ERROR',
                'message': f'Error de Meta: {error_message}',
                'error_code': error_code
            }
    
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout al conectar con Meta API")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': 'Timeout al conectar con Meta API'
        }
    
    except Exception as e:
        logger.error(f"❌ Excepción al enviar plantilla a Meta: {str(e)}")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': f'Error: {str(e)}'
        }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `verificar_estado_plantilla_meta` — `core/meta_templates.py:120`

```python
# core/meta_templates.py:120
def verificar_estado_plantilla_meta(template_id):
    """
    Verifica el estado de una plantilla en Meta.
    
    Args:
        template_id: ID de la plantilla en Meta
    
    Returns:
        dict con 'success', 'status', 'quality_score', etc.
    """
    
    access_token = settings.WHATSAPP_TOKEN
    
    if not access_token:
        return {'success': False, 'message': 'Token no configurado'}
    
    url = f"https://graph.facebook.com/v19.0/{template_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            return {
                'success': True,
                'status': data.get('status', 'UNKNOWN'),
                'quality_score': data.get('quality_score', {}),
                'name': data.get('name', ''),
                'language': data.get('language', '')
            }
        else:
            return {
                'success': False,
                'message': data.get('error', {}).get('message', 'Error desconocido')
            }
    
    except Exception as e:
        logger.error(f"Error verificando plantilla: {str(e)}")
        return {'success': False, 'message': str(e)}
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `webhook_meta` — `core/views/webhook_meta.py:1`

```python
# core/views/webhook_meta.py:1
import logging

from django.conf import settings
from django.http import HttpResponse

from ..intent_detector import detect_intent
from ..models import Estudiante, WhatsappLog
from ..response_templates import get_response_for_intent
from ..utils import enviar_whatsapp

logger = logging.getLogger(__name__)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_sandbox_inbound_repetido` — `core/views/webhook_meta.py:13`

```python
# core/views/webhook_meta.py:13
def _sandbox_inbound_repetido(inbound) -> bool:
    """Meta reintenta si tardamos: el mismo wamid no debe responder ni gastar cupo dos veces."""
    sid = str(inbound.get('MessageSid') or '').strip()
    if not sid:
        return False
    try:
        from django.core.cache import cache

        if cache.add(f'sandbox_in:{sid}', 1, timeout=6 * 3600):
            return False
    except Exception:
        logger.exception('sandbox_dedupe_cache_fail')
        return False
    logger.info('sandbox_inbound_duplicado sid=%s', sid)
    return True

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_encolar_sandbox_si_async` — `core/views/webhook_meta.py:29`

```python
# core/views/webhook_meta.py:29
def _encolar_sandbox_si_async(inbound) -> bool:
    """Una tarea Celery por mensaje si SANDBOX_CELERY_ASYNC=true.

    Si Redis no acepta la tarea, la excepción sube. El webhook conserva
    los reclamos ya encolados, suelta el que falló y los que no alcanzó
    a encolarse, y responde 500. No hay fallback síncrono.
    """
    if not getattr(settings, 'SANDBOX_CELERY_ASYNC', False):
        return False
    from core.tasks import procesar_sandbox_meta_async

    procesar_sandbox_meta_async.delay(dict(inbound))
    return True

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_aplicar_sandbox_menu` — `core/views/webhook_meta.py:43`

```python
# core/views/webhook_meta.py:43
def _aplicar_sandbox_menu(data):
    """Menú agentes | cursos del sandbox Meta. No toca WABA Twilio de producción."""
    from core.sandbox_canal import (
        canal_sandbox_si_meta,
        es_inbound_twilio_http,
        sandbox_via_meta,
        to_es_sandbox,
    )
    from core.sandbox_menu import dispatch_sandbox_menu, sandbox_menu_enabled, sandbox_number
    from core.wa_reply_context import reply_from

    if (
        sandbox_menu_enabled()
        and sandbox_via_meta()
        and es_inbound_twilio_http(data)
        and to_es_sandbox(data)
    ):
        logger.info('sandbox_twilio_inbound_ignorado To=%s (canal=meta)', data.get('To', ''))
        return HttpResponse('OK')

    with canal_sandbox_si_meta():
        ruta = dispatch_sandbox_menu(data)
        if ruta is None:
            return None
        if ruta == 'handled':
            return HttpResponse('OK')
        if ruta == 'nat':
            from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

            if not _encolar_bot_comercial_si_async(data, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(data, forzar_canal=True)
            return HttpResponse('OK')
        if ruta == 'cursos':
            sb = sandbox_number()
            with reply_from(sb):
                if _encolar_twilio_edu_si_async(data, reply_from_number=sb):
                    return HttpResponse('OK')
                tw = _procesar_twilio_webhook(data)
                if isinstance(tw, HttpResponse):
                    return tw
            return HttpResponse('OK')
        return None

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_procesar_meta_webhook` — `core/views/webhook_meta.py:86`

```python
# core/views/webhook_meta.py:86
def _procesar_meta_webhook(payload):
    """Procesa webhooks de Meta WhatsApp (mantiene compatibilidad)"""
    try:
        print("🔵 META: Procesando...")
        entries = payload.get('entry', [])
        
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                meta_to = (
                    (value.get('metadata') or {}).get('display_phone_number')
                    or (value.get('metadata') or {}).get('phone_number_id')
                    or ''
                )
                
                # Mensajes entrantes
                messages = value.get('messages', [])
                for m in messages:
                    phone = m.get('from')
                    msg_id = m.get('id')
                    text = ''
                    if 'text' in m and isinstance(m['text'], dict):
                        text = m['text'].get('body', '')
                    
                    # Guardar mensaje
                    WhatsappLog.objects.create(
                        telefono=phone,
                        mensaje=text,
                        mensaje_id=msg_id,
                        tipo='INCOMING'
                    )
                    
                    # Obtener o crear estudiante
                    estudiante, _ = Estudiante.objects.get_or_create(
                        telefono=phone,
                        defaults={'nombre': 'Usuario', 'activo': True, 'cedula': f'META_{phone[-10:]}'}
                    )
                    
                    # Verificar seguridad primero
                    from ..security_handler import verificar_seguridad_completa
                    bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(
                        estudiante,
                        text,
                        telefono=phone,
                        numero_destino=meta_to,
                    )
                    
                    if bloqueado:
                        texto_respuesta = respuesta_seguridad
                    else:
                        # Detectar intent
                        intent = detect_intent(text)
                        
                        if intent != 'desconocido':
                            # Usar template
                            texto_respuesta = get_response_for_intent(
                                intent, 
                                estudiante.nombre,
                                estudiante_id=estudiante.id,
                                mensaje_original=text
                            )
                        else:
                            # Usar IA solo para preguntas
                            try:
                                from ..ai_assistant import responder_con_ia
                                texto_respuesta = responder_con_ia(text, phone)
                            except Exception as e:
                                print(f"Error IA: {e}")
                                texto_respuesta = "Disculpa, tengo problemas técnicos. Vuelve a escribir tu mensaje para continuar."
                    
                    # Enviar respuesta
                    resultado_envio = enviar_whatsapp(phone, texto_respuesta)
                    
                    if resultado_envio.get('success'):
                        WhatsappLog.objects.create(
                            telefono=phone,
                            mensaje=texto_respuesta,
                            mensaje_id=resultado_envio.get('mensaje_id'),
                            tipo='SENT'
                        )
    
    except Exception as e:
        print(f"❌ Error en _procesar_meta_webhook: {str(e)}")
        import traceback
        traceback.print_exc()

from .twilio_transporte import _encolar_twilio_edu_si_async
from .webhook_comercial import _encolar_bot_comercial_si_async
from .webhook_twilio import _procesar_twilio_webhook
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.

