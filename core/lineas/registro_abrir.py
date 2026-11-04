"""Abre el Flow de registro cuando escriben la frase de la línea 3.

En otra línea no hace nada: la principal y la línea 2 siguen igual.
Si el Flow no está en Meta, lo publica en la WABA de esta línea.
Los datos siguen siendo los del JSON: habeas, nombre, cédula y municipio.
"""
from __future__ import annotations

import json
import logging

from core.lineas.perfil import USO_REGISTRO
from core.lineas.registro_enlace import leer_frase, token_de_cliente
from core.lineas.registro_flow import NOMBRE_FLOW, PANTALLA, flow_registro

logger = logging.getLogger(__name__)

TEXTO_FLOW = (
    'Para crear su registro necesitamos su nombre y su cédula. '
    'El municipio puede dejarlo vacío. Su número de WhatsApp ya lo tenemos.'
)
TEXTO_OTRA_FRASE = (
    'Para registrarse envíe *HOLA EKI* o la frase del enlace. '
    'El formulario pide el nombre, la cédula y, si quiere, el municipio.'
)
TEXTO_SIN_FLOW = (
    'El formulario de registro no está listo. Envíe de nuevo *HOLA EKI* en un momento.'
)
TEXTO_REINTENTO = 'No pude abrir el formulario. Envíe de nuevo *HOLA EKI*.'
CTA = 'Registrarme'


def es_turno_registro() -> bool:
    """True solo si la salida de este turno es la línea de registro."""
    from core.lineas.variante import perfil_de

    return perfil_de().uso == USO_REGISTRO


def flow_id_registro() -> str:
    """Id ya configurado, o el publicado en la WABA. Vacío si no hay credenciales."""
    from django.conf import settings

    fijo = (getattr(settings, 'EKI_LINEA_REGISTRO_FLOW_ID', '') or '').strip()
    if fijo:
        return fijo
    return publicar_flow_registro()


def publicar_flow_registro() -> str:
    """Busca eki_registro en la WABA de la línea 3. Si no está, lo crea y lo publica."""
    import requests
    from django.conf import settings

    from core.lineas.envio import _graph_headers
    from core.meta_waba import _version

    waba = (getattr(settings, 'EKI_LINEA_REGISTRO_WABA_ID', '') or '').strip()
    headers = _graph_headers()
    if not waba or not headers:
        return ''
    url = f'https://graph.facebook.com/{_version()}/{waba}/flows'
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        data = resp.json() if resp.content else {}
    except requests.RequestException:
        logger.exception('registro_flow_listar')
        return ''
    if not isinstance(data, dict):
        data = {}
    elegido = _id_existente(data.get('data') or [])
    if elegido:
        return elegido
    cuerpo = {
        'name': NOMBRE_FLOW,
        'categories': ['OTHER'],
        'flow_json': json.dumps(flow_registro(), ensure_ascii=False),
        'publish': True,
    }
    try:
        alta = requests.post(url, json=cuerpo, headers=headers, timeout=20)
        creado = alta.json() if alta.content else {}
    except requests.RequestException:
        logger.exception('registro_flow_publicar')
        return ''
    flow_id = str((creado or {}).get('id') or '').strip()
    if alta.status_code not in (200, 201) or not flow_id:
        logger.warning('registro_flow_publicar_fallo %s', creado)
        return ''
    return flow_id


def abrir_registro(telefono: str, body: str) -> str | None:
    """'handled' si este turno es de la línea 3. None en cualquier otra."""
    if not es_turno_registro():
        return None
    destino = leer_frase(body)
    if destino is None:
        _avisar(telefono, TEXTO_OTRA_FRASE)
        return 'handled'
    flow_id = flow_id_registro()
    if not flow_id:
        _avisar(telefono, TEXTO_SIN_FLOW)
        return 'handled'
    from core.lineas.envio import enviar_meta_flow

    resultado = enviar_meta_flow(
        telefono,
        TEXTO_FLOW,
        flow_id,
        pantalla=PANTALLA,
        flow_token=token_de_cliente(destino[1]),
        cta=CTA,
        agente_evento='registro_flow',
        modo='published',
        con_datos=False,
    )
    if not resultado.get('success'):
        _avisar(telefono, TEXTO_REINTENTO)
    return 'handled'


def _avisar(telefono: str, texto: str) -> None:
    from core.sandbox_menu import enviar_texto_sandbox, sandbox_number

    from django.db import DatabaseError
    from requests import RequestException

    try:
        enviar_texto_sandbox(telefono, sandbox_number(), texto, agente='registro_flow')
    except (DatabaseError, RequestException, OSError):
        logger.exception('registro_flow_aviso')


def _id_existente(items) -> str:
    publicados = []
    otros = []
    for item in items:
        if not isinstance(item, dict) or item.get('name') != NOMBRE_FLOW:
            continue
        flow_id = str(item.get('id') or '').strip()
        if not flow_id:
            continue
        if str(item.get('status') or '').upper() == 'PUBLISHED':
            publicados.append(flow_id)
        else:
            otros.append(flow_id)
    if publicados:
        return publicados[0]
    if otros:
        return otros[0]
    return ''
