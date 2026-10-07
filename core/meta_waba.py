"""Cliente Graph API para plantillas y envío de Campaña Meta.

Crear: POST /{waba-id}/message_templates
Enviar: POST /{phone-number-id}/messages  (type=template)
No usa Content SID de Twilio.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time

import requests
from django.conf import settings
from django.utils import timezone

from core.models_campana_meta import (
    CampanaMeta,
    EnvioCampanaMeta,
    PlantillaMeta,
    TIPOS_ALTA_GRAPH,
    ejemplos_lista,
    sanitizar_nombre_meta,
    variables_en,
)

logger = logging.getLogger(__name__)

_RATE_CODES = {4, 80008, 613, 130429}
_ESTADOS_OK = {
    'PENDING', 'APPROVED', 'REJECTED', 'PAUSED', 'DISABLED', 'IN_APPEAL',
}


def campana_meta_habilitada() -> bool:
    return bool(getattr(settings, 'EKI_CAMPANA_META_ENABLED', True))


def _version() -> str:
    """Solo WHATSAPP_API_VERSION. El default v19.0 vive en settings, no aquí."""
    return str(settings.WHATSAPP_API_VERSION).strip()


def _token() -> str:
    return (getattr(settings, 'WHATSAPP_TOKEN', None) or '').strip()


def _waba() -> str:
    return (getattr(settings, 'WHATSAPP_BUSINESS_ACCOUNT_ID', None) or '').strip()


def _phone_default() -> str:
    return (getattr(settings, 'WHATSAPP_PHONE_ID', None) or '').strip()


def _headers() -> dict[str, str] | None:
    token = _token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


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


def _es_rate_limit(code: str) -> bool:
    try:
        return int(code) in _RATE_CODES
    except (TypeError, ValueError):
        return False


def normalizar_estado(evento: str) -> str:
    bruto = (evento or '').strip().upper()
    if bruto in _ESTADOS_OK:
        return bruto
    if bruto in ('FLAGGED', 'PENDING_DELETION'):
        return 'PAUSED' if bruto == 'FLAGGED' else 'PENDING'
    return 'ERROR'


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


def _get(url: str, params: dict | None = None) -> tuple[int, dict]:
    headers = _headers()
    if not headers:
        return 0, {'error': {'message': 'WHATSAPP_TOKEN no configurado', 'code': 'NO_TOKEN'}}
    try:
        resp = requests.get(url, params=params or {}, headers=headers, timeout=20)
    except requests.RequestException as exc:
        return 0, {'error': {'message': str(exc)[:300], 'code': 'RED'}}
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return resp.status_code, data


def _app_id() -> str:
    return (getattr(settings, 'WHATSAPP_APP_ID', None) or '').strip()


def subir_ejemplo_imagen(url: str) -> str:
    """Resumable Upload de Meta. Devuelve el header_handle de la foto."""
    app_id = _app_id()
    token = _token()
    imagen = (url or '').strip()
    if not app_id or not token:
        raise RuntimeError('Faltan WHATSAPP_APP_ID o WHATSAPP_TOKEN para subir la foto del carrusel.')
    if not imagen.startswith('https://'):
        raise RuntimeError('La foto del carrusel tiene que ser una URL https.')
    try:
        descarga = requests.get(imagen, timeout=20)
        descarga.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f'No se pudo bajar la foto del carrusel: {exc}') from exc
    data = descarga.content or b''
    if not data:
        raise RuntimeError('La foto del carrusel llegó vacía.')
    ctype = (descarga.headers.get('Content-Type') or 'image/jpeg').split(';')[0].strip() or 'image/jpeg'
    nombre = imagen.rsplit('/', 1)[-1].split('?')[0] or 'tarjeta.jpg'
    sesion_url = f'https://graph.facebook.com/{_version()}/{app_id}/uploads'
    try:
        sesion = requests.post(
            sesion_url,
            params={
                'file_name': nombre[:80],
                'file_length': len(data),
                'file_type': ctype,
                'access_token': token,
            },
            timeout=30,
        )
        sesion_data = sesion.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f'No se abrió la subida de la foto: {exc}') from exc
    upload_id = str((sesion_data or {}).get('id') or '').strip()
    if sesion.status_code != 200 or not upload_id:
        raise RuntimeError(_error_meta(sesion_data if isinstance(sesion_data, dict) else {})['message'])
    try:
        subida = requests.post(
            f'https://graph.facebook.com/{_version()}/{upload_id}',
            headers={
                'Authorization': f'OAuth {token}',
                'file_offset': '0',
                'Content-Type': ctype,
            },
            data=data,
            timeout=60,
        )
        subida_data = subida.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f'No se subió la foto del carrusel: {exc}') from exc
    handle = str((subida_data or {}).get('h') or '').strip()
    if subida.status_code != 200 or not handle:
        raise RuntimeError(_error_meta(subida_data if isinstance(subida_data, dict) else {})['message'])
    return handle


def handles_carrusel(plantilla: PlantillaMeta) -> list[str]:
    tarjetas = list(plantilla.tarjetas.order_by('orden', 'id'))
    if len(tarjetas) < 2:
        raise RuntimeError('El carrusel necesita al menos dos tarjetas.')
    if len(tarjetas) > 10:
        raise RuntimeError('El carrusel admite como máximo diez tarjetas.')
    return [subir_ejemplo_imagen(tarjeta.imagen_url) for tarjeta in tarjetas]


def armar_componentes_carrusel(plantilla: PlantillaMeta, handles: list[str]) -> list[dict]:
    """Alta Graph de un media card carousel. Mismos dos quick reply en cada tarjeta."""
    tarjetas = list(plantilla.tarjetas.order_by('orden', 'id'))
    if len(tarjetas) < 2 or len(handles) < len(tarjetas):
        raise RuntimeError('El carrusel está incompleto.')
    cards = []
    for tarjeta, handle in zip(tarjetas, handles):
        ver = (tarjeta.boton_ver_texto or 'Ver curso').strip()[:25]
        info = (tarjeta.boton_info_texto or 'Más información').strip()[:25]
        cuerpo = (tarjeta.cuerpo or '').strip()[:160]
        if not ver or not info or not cuerpo or not handle:
            raise RuntimeError('Cada tarjeta necesita foto, texto y los dos botones.')
        cards.append({
            'components': [
                {
                    'type': 'HEADER',
                    'format': 'IMAGE',
                    'example': {'header_handle': [handle]},
                },
                {'type': 'BODY', 'text': cuerpo},
                {
                    'type': 'BUTTONS',
                    'buttons': [
                        {'type': 'QUICK_REPLY', 'text': ver},
                        {'type': 'QUICK_REPLY', 'text': info},
                    ],
                },
            ],
        })
    return [
        {'type': 'BODY', 'text': (plantilla.cuerpo or '').strip()},
        {'type': 'CAROUSEL', 'cards': cards},
    ]


def _marcar_error_plantilla(plantilla: PlantillaMeta, mensaje: str) -> dict:
    plantilla.estado = 'ERROR'
    plantilla.ultimo_error_mensaje = (mensaje or 'Error de Meta')[:2000]
    plantilla.sincronizada_en = timezone.now()
    plantilla.save()
    return {'success': False, 'message': plantilla.ultimo_error_mensaje}


def crear_plantilla_en_meta(plantilla: PlantillaMeta) -> dict:
    if not campana_meta_habilitada():
        return {'success': False, 'message': 'Campaña Meta está apagada (EKI_CAMPANA_META_ENABLED).'}
    waba = _waba()
    if not waba or not _token():
        return {
            'success': False,
            'message': 'Faltan WHATSAPP_TOKEN o WHATSAPP_BUSINESS_ACCOUNT_ID.',
        }
    if plantilla.meta_template_id and plantilla.estado in ('PENDING', 'APPROVED', 'IN_APPEAL'):
        return {
            'success': False,
            'message': f'Ya está en Meta ({plantilla.meta_template_id}, {plantilla.estado}).',
        }
    plantilla.meta_name = sanitizar_nombre_meta(plantilla.meta_name or plantilla.nombre_interno)
    plantilla.full_clean()
    tipo = getattr(plantilla, 'tipo', 'TEXTO') or 'TEXTO'
    if tipo not in TIPOS_ALTA_GRAPH:
        return {
            'success': False,
            'message': (
                f'{plantilla.get_tipo_display()} queda guardada como registro. '
                'El envío automático a Meta hoy cubre Texto y Carrusel.'
            ),
        }
    if tipo == 'CARRUSEL':
        try:
            componentes = armar_componentes_carrusel(plantilla, handles_carrusel(plantilla))
        except Exception as exc:
            plantilla.waba_id = waba
            logger.warning('plantilla_carrusel_error %s', exc)
            return _marcar_error_plantilla(plantilla, str(exc))
    else:
        componentes = armar_componentes_alta(plantilla)
    payload = {
        'name': plantilla.meta_name,
        'language': plantilla.idioma or 'es',
        'category': plantilla.categoria,
        'components': componentes,
    }
    url = f'https://graph.facebook.com/{_version()}/{waba}/message_templates'
    status, data = _post(url, payload)
    if status == 200 and data.get('id'):
        plantilla.meta_template_id = str(data.get('id'))
        plantilla.waba_id = waba
        plantilla.estado = normalizar_estado(str(data.get('status') or 'PENDING'))
        if plantilla.estado == 'ERROR':
            plantilla.estado = 'PENDING'
        plantilla.ultimo_error_code = ''
        plantilla.ultimo_error_mensaje = ''
        plantilla.enviada_en = timezone.now()
        plantilla.sincronizada_en = timezone.now()
        plantilla.save()
        logger.info('plantilla_meta_creada id=%s estado=%s', plantilla.meta_template_id, plantilla.estado)
        return {'success': True, 'template_id': plantilla.meta_template_id, 'status': plantilla.estado}

    err = _error_meta(data)
    plantilla.estado = 'ERROR'
    plantilla.waba_id = waba
    plantilla.ultimo_error_code = err['subcode'] or err['code']
    plantilla.ultimo_error_mensaje = err['message']
    plantilla.sincronizada_en = timezone.now()
    plantilla.save()
    logger.warning('plantilla_meta_error code=%s', plantilla.ultimo_error_code)
    return {'success': False, 'message': err['message'], 'error_code': plantilla.ultimo_error_code}


def consultar_plantilla(plantilla: PlantillaMeta) -> dict:
    waba = (plantilla.waba_id or _waba()).strip()
    if not waba or not _token():
        return {'success': False, 'message': 'Sin WABA o token.'}
    url = f'https://graph.facebook.com/{_version()}/{waba}/message_templates'
    status, data = _get(url, {'name': plantilla.meta_name, 'limit': 20})
    if status != 200:
        err = _error_meta(data)
        return {'success': False, 'message': err['message'], 'error_code': err['code']}
    idioma = (plantilla.idioma or 'es').lower()
    for item in data.get('data') or []:
        if (item.get('name') or '') != plantilla.meta_name:
            continue
        lang = item.get('language') or ''
        if isinstance(lang, dict):
            lang = lang.get('code') or ''
        if str(lang).lower() != idioma:
            continue
        return {
            'success': True,
            'status': normalizar_estado(str(item.get('status') or '')),
            'id': str(item.get('id') or ''),
            'reason': str(item.get('rejected_reason') or ''),
        }
    return {'success': False, 'message': 'Meta no devolvió esa plantilla.'}


def sincronizar_plantilla(plantilla: PlantillaMeta) -> dict:
    resultado = consultar_plantilla(plantilla)
    plantilla.sincronizada_en = timezone.now()
    if not resultado.get('success'):
        plantilla.save(update_fields=['sincronizada_en'])
        return resultado
    plantilla.estado = resultado['status']
    if resultado.get('id') and not plantilla.meta_template_id:
        plantilla.meta_template_id = resultado['id']
    motivo = (resultado.get('reason') or '').strip()
    if motivo and motivo.upper() != 'NONE':
        plantilla.rejected_reason = motivo[:500]
    plantilla.save()
    return resultado


def sincronizar_pendientes() -> int:
    if not campana_meta_habilitada():
        return 0
    qs = PlantillaMeta.objects.filter(estado__in=('PENDING', 'IN_APPEAL'))
    n = 0
    for plantilla in qs.iterator():
        resultado = sincronizar_plantilla(plantilla)
        if resultado.get('success'):
            n += 1
    return n


def _cuerpo_desde_componentes(componentes) -> str:
    for comp in componentes or []:
        if str(comp.get('type') or '').upper() == 'BODY':
            return str(comp.get('text') or '').strip()
    return ''


def _aplicar_item_catalogo(item: dict, waba: str) -> dict:
    nombre = sanitizar_nombre_meta(str(item.get('name') or ''))
    idioma = item.get('language') or 'es'
    if isinstance(idioma, dict):
        idioma = idioma.get('code') or 'es'
    idioma = str(idioma or 'es')[:10]
    estado = normalizar_estado(str(item.get('status') or ''))
    if estado == 'ERROR':
        estado = 'PENDING'
    motivo = str(item.get('rejected_reason') or '').strip()
    plantilla = PlantillaMeta.objects.filter(meta_name=nombre, idioma=idioma).first()
    creada = False
    if plantilla is None:
        cuerpo = _cuerpo_desde_componentes(item.get('components')) or 'Texto importado desde Meta.'
        plantilla = PlantillaMeta(
            nombre_interno=(nombre or 'plantilla')[:120],
            meta_name=nombre,
            idioma=idioma,
            cuerpo=cuerpo[:1024],
            categoria='UTILITY',
        )
        creada = True
    plantilla.meta_template_id = str(item.get('id') or plantilla.meta_template_id or '')
    plantilla.waba_id = waba
    plantilla.estado = estado
    plantilla.sincronizada_en = timezone.now()
    if motivo and motivo.upper() != 'NONE':
        plantilla.rejected_reason = motivo[:500]
    plantilla.save()
    return {
        'nombre': plantilla.meta_name,
        'idioma': plantilla.idioma,
        'estado': plantilla.estado,
        'creada': creada,
        'motivo': plantilla.rejected_reason,
    }


def sincronizar_catalogo_meta() -> dict:
    """Lee el WABA y deja en cada ficha si Meta aprobó, rechazó o sigue pendiente."""
    waba = _waba()
    if not waba or not _token():
        return {
            'ok': False,
            'message': 'Faltan WHATSAPP_TOKEN o WHATSAPP_BUSINESS_ACCOUNT_ID.',
            'filas': [],
        }
    url = f'https://graph.facebook.com/{_version()}/{waba}/message_templates'
    params = {
        'fields': 'id,name,language,status,rejected_reason,components',
        'limit': '100',
    }
    filas = []
    for _ in range(20):
        status, data = _get(url, params)
        params = None
        if status != 200:
            err = _error_meta(data)
            return {'ok': False, 'message': err['message'], 'filas': filas}
        for item in data.get('data') or []:
            if not isinstance(item, dict) or not item.get('name'):
                continue
            filas.append(_aplicar_item_catalogo(item, waba))
        url = str(((data.get('paging') or {}).get('next') or '')).strip()
        if not url:
            break
    return {'ok': True, 'message': '', 'filas': filas}


def enviar_prueba_meta(campana: CampanaMeta, telefono: str) -> dict:
    """Un solo número. No marca la campaña como ejecutada."""
    from core.utils_telefono import normalizar_e164_co

    plantilla = campana.plantilla
    if plantilla.estado != 'APPROVED':
        motivo = (plantilla.rejected_reason or '').strip()
        texto = f'La plantilla está en {plantilla.estado}.'
        if motivo:
            texto = f'{texto} Motivo: {motivo}.'
        texto = f'{texto} Solo se envía cuando Meta la deja Aprobada.'
        return {'success': False, 'message': texto}
    destino = normalizar_e164_co(telefono)
    if len(destino) < 10:
        return {'success': False, 'message': 'Escriba el número con indicativo, por ejemplo 57300…'}
    phone_id = (campana.phone_number_id or _phone_default()).strip()
    waba = (plantilla.waba_id or _waba()).strip()
    ok, motivo = phone_pertenece_a_waba(phone_id, waba)
    if not ok:
        return {'success': False, 'message': motivo}
    estudiante = type('Est', (), {'nombre': 'Prueba', 'telefono': destino})()
    try:
        componentes = _parametros_envio(plantilla, campana, estudiante)
    except ValueError as exc:
        return {'success': False, 'message': str(exc)}
    payload = {
        'messaging_product': 'whatsapp',
        'to': destino,
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
        return {
            'success': True,
            'message': 'Prueba enviada.',
            'wamid': str((data.get('messages') or [{}])[0].get('id') or ''),
        }
    err = _error_meta(data)
    return {'success': False, 'message': err['message'], 'error_code': err['code']}
    if not campana_meta_habilitada():
        return 0
    qs = PlantillaMeta.objects.filter(estado__in=('PENDING', 'IN_APPEAL'))
    n = 0
    for plantilla in qs.iterator():
        resultado = sincronizar_plantilla(plantilla)
        if resultado.get('success'):
            n += 1
    return n


def aplicar_eventos_plantilla(payload: dict, raw_body: bytes, signature_header: str) -> int:
    """Aplica message_template_status_update solo si la firma Meta es válida."""
    cambios = _cambios_status(payload)
    if not cambios:
        return 0
    secret = (getattr(settings, 'WHATSAPP_APP_SECRET', None) or '').strip()
    if not firma_meta_ok(raw_body or b'', signature_header, secret):
        logger.warning('meta_template_status_firma_invalida')
        return 0
    actualizadas = 0
    for value in cambios:
        evento = normalizar_estado(str(value.get('event') or ''))
        tid = str(value.get('message_template_id') or '').strip()
        nombre = (value.get('message_template_name') or '').strip()
        idioma = str(value.get('message_template_language') or 'es').strip()
        motivo = str(value.get('reason') or '').strip()
        qs = PlantillaMeta.objects.none()
        if tid:
            qs = PlantillaMeta.objects.filter(meta_template_id=tid)
        if not qs.exists() and nombre:
            qs = PlantillaMeta.objects.filter(meta_name=nombre, idioma=idioma)
        for plantilla in qs:
            plantilla.estado = evento
            if motivo and motivo.upper() != 'NONE':
                plantilla.rejected_reason = motivo[:500]
            plantilla.sincronizada_en = timezone.now()
            plantilla.save()
            actualizadas += 1
    return actualizadas


def _cambios_status(payload: dict) -> list[dict]:
    salida = []
    if not isinstance(payload, dict):
        return salida
    for entry in payload.get('entry') or []:
        for change in (entry or {}).get('changes') or []:
            if (change or {}).get('field') != 'message_template_status_update':
                continue
            value = (change or {}).get('value') or {}
            if isinstance(value, dict):
                salida.append(value)
    return salida


def _resolver_valor(token: str, estudiante) -> str:
    clave = (token or '').strip()
    if clave == 'nombre':
        return (getattr(estudiante, 'nombre', None) or 'Estudiante').strip() or 'Estudiante'
    if clave == 'telefono':
        return str(getattr(estudiante, 'telefono', None) or '').strip()
    return clave


def resolver_mapeo(mapeo: str, cantidad: int, estudiante) -> list[str]:
    if cantidad <= 0:
        return []
    partes = [p.strip() for p in (mapeo or '').split('|')]
    partes = [p for p in partes if p]
    if len(partes) < cantidad:
        raise ValueError(
            f'Faltan valores de variables ({len(partes)} de {cantidad}). '
            f'Use nombre, telefono o texto fijo, separados por |.'
        )
    return [_resolver_valor(p, estudiante) for p in partes[:cantidad]]


def _parametros_envio(plantilla: PlantillaMeta, campana: CampanaMeta, estudiante) -> list[dict]:
    componentes = []
    n_header = len(set(variables_en(plantilla.header_texto)))
    if n_header:
        vals = resolver_mapeo(campana.mapeo_header, n_header, estudiante)
        componentes.append({
            'type': 'header',
            'parameters': [{'type': 'text', 'text': v} for v in vals],
        })
    n_body = len(set(variables_en(plantilla.cuerpo)))
    if n_body:
        vals = resolver_mapeo(campana.mapeo_body or 'nombre', n_body, estudiante)
        componentes.append({
            'type': 'body',
            'parameters': [{'type': 'text', 'text': v} for v in vals],
        })
    idx = 0
    for n in (1, 2):
        tipo = getattr(plantilla, f'boton_{n}_tipo') or ''
        texto = (getattr(plantilla, f'boton_{n}_texto') or '').strip()
        if not tipo or not texto:
            continue
        if tipo == 'URL' and variables_en(getattr(plantilla, f'boton_{n}_url') or ''):
            vals = resolver_mapeo(campana.mapeo_boton, 1, estudiante)
            componentes.append({
                'type': 'button',
                'sub_type': 'url',
                'index': str(idx),
                'parameters': [{'type': 'text', 'text': vals[0]}],
            })
        idx += 1
    return componentes


def phone_pertenece_a_waba(phone_id: str, waba_id: str) -> tuple[bool, str]:
    from django.core.cache import cache

    phone_id = (phone_id or '').strip()
    waba_id = (waba_id or '').strip()
    if not phone_id or not waba_id:
        return False, 'Falta phone number ID o WABA.'
    cache_key = f'eki_waba_phones_{waba_id}'
    ids = cache.get(cache_key)
    if not isinstance(ids, list):
        url = f'https://graph.facebook.com/{_version()}/{waba_id}/phone_numbers'
        status, data = _get(url, {'fields': 'id', 'limit': 100})
        if status != 200:
            err = _error_meta(data)
            return False, err['message'] or 'No se pudo verificar el número en el WABA.'
        ids = [str(item.get('id')) for item in (data.get('data') or []) if item.get('id')]
        cache.set(cache_key, ids, 600 if ids else 30)
    if phone_id not in ids:
        return False, 'Ese phone number ID no está en el WABA de la plantilla.'
    return True, ''


def _destinatarios(campana: CampanaMeta):
    if campana.grupo_id:
        return campana.grupo.estudiantes.filter(activo=True)
    return campana.destinatarios.filter(activo=True)


def ejecutar_campana_meta(campana: CampanaMeta) -> dict:
    from core.meta_token import token_invalido

    if token_invalido():
        logger.critical('campana_meta_omitida_token_invalido id=%s', getattr(campana, 'pk', None))
        return {'enviados': 0, 'fallidos': 0, 'omitidos_token': 1}
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
