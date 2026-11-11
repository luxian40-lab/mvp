"""La línea 3 saluda y abre el registro con cualquier palabra.

En otra línea no hace nada: la principal y la línea 2 siguen igual.
La frase EKI C{id} solo guarda la organización del enlace.
AgriCapital (EKI_AGRICAPITAL_CLIENTE_ID): abre el Flow de una vez con copy
propio. Sin FAQ. El botón viejo de bienvenida sigue abriendo el Flow.
Si el Flow no está en Meta, lo publica en la WABA de esta línea.
"""
from __future__ import annotations

import json
import logging

from core.lineas.perfil import USO_REGISTRO
from core.lineas.registro_agricapital import (
    CTA_BIENVENIDA,
    TEXTO_BIENVENIDA,
    destino_frase_agri,
    es_boton_registrarme,
    es_cliente_agricapital,
    es_enlace_agricapital,
)
from core.lineas.registro_enlace import leer_frase, token_de_cliente
from core.lineas.registro_flow import NOMBRE_FLOW, PANTALLA, flow_registro

logger = logging.getLogger(__name__)

SALUDO = (
    'Hola, soy eki. Aquí se aprende por WhatsApp, en mensajes cortos, '
    'sin descargar una aplicación.'
)
COMO_FUNCIONA = (
    'Este mismo WhatsApp es la clase. Primero deja su nombre y su cédula. '
    'Después las lecciones llegan aquí. Escribe *listo* y recibe la siguiente parte.'
)
TUTO = (
    'Así se usa:\n'
    '1. Toque *Registrarme* y deje su nombre y su cédula.\n'
    '2. En este mismo chat escriba *listo*.\n'
    '3. Cuando termine esa parte, vuelva a escribir *listo*.\n'
    'Si hay una pregunta con letras, responda A, B, C o D.'
)
MINIMO = (
    'Necesita WhatsApp en este celular, su nombre, su cédula y aceptar el uso de sus datos. '
    'No necesita computador ni correo.'
)
TEXTOS_ENTRADA = (SALUDO, COMO_FUNCIONA, TUTO, MINIMO)
TEXTO_FLOW = (
    'Toque Registrarme y deje su nombre, su cédula y su municipio. '
    'Su número de WhatsApp ya lo tenemos.'
)
TEXTO_SIN_FLOW = 'El formulario de registro no está listo. Escriba de nuevo en un momento.'
TEXTO_REINTENTO = 'No pude abrir el formulario. Escriba de nuevo.'
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
    """Busca eki_registro_v2 en la WABA de la línea 3. Si no está, lo crea y lo publica."""
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
        alta = requests.post(url, headers=headers, json=cuerpo, timeout=20)
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
    cliente_id = _cliente_de_turno(telefono, body)
    ficha = _ficha(telefono)
    if ficha is not None:
        if _cede_al_menu(telefono, body):
            return None
        from core.lineas.registro_cursos import atender_cursos

        atender_cursos(telefono, body, ficha.cliente_id or cliente_id)
        return 'handled'

    cliente_boton = es_boton_registrarme(body)
    if cliente_boton is not None:
        _enviar_flow(
            telefono, cliente_boton, texto=TEXTO_BIENVENIDA, cta=CTA_BIENVENIDA,
        )
        return 'handled'

    if es_enlace_agricapital(cliente_id, body):
        destino = cliente_id
        if destino is None:
            agri = destino_frase_agri(body)
            destino = agri[1] if agri else None
        if destino is None:
            return 'handled'
        _enviar_flow(
            telefono, destino, texto=TEXTO_BIENVENIDA, cta=CTA_BIENVENIDA,
        )
        return 'handled'

    if es_cliente_agricapital(cliente_id):
        _enviar_flow(
            telefono, cliente_id, texto=TEXTO_BIENVENIDA, cta=CTA_BIENVENIDA,
        )
        return 'handled'

    for texto in TEXTOS_ENTRADA:
        _avisar(telefono, texto)
    _enviar_flow(telefono, cliente_id)
    return 'handled'


def _cede_al_menu(telefono: str, body: str) -> bool:
    """True si el menú/asesoría de la línea deben atender este turno."""
    from core.lineas.variante import perfil_de

    perfil = perfil_de()
    if not (perfil.menu or perfil.asesores):
        return False
    if _es_avance_de_curso(body):
        return False
    if _modo_sandbox_activo(telefono):
        return True
    from core.sandbox_menu import _normalizar_eleccion_raiz

    return _normalizar_eleccion_raiz(body) is not None


def _es_avance_de_curso(body: str) -> bool:
    texto = (body or '').strip()
    if texto.startswith(('ver_curso_', 'info_curso_')):
        return True
    from core.conversacion.response_templates import _es_mensaje_listo_avance_curso

    return bool(_es_mensaje_listo_avance_curso(texto))


def _modo_sandbox_activo(telefono: str) -> bool:
    from django.db import DatabaseError

    from core.lineas.sesion import sesion_de
    from core.sandbox_menu import (
        MODO_AGENTES,
        MODO_ASESORIA,
        MODO_CAFE,
        MODO_COACH,
        MODO_CURSOS,
        MODO_FINANZAS,
        MODO_FORMACION,
        MODO_IA_CAMPO,
        MODO_MENU,
        MODO_NAT,
        MODO_VENTAS,
    )

    modos = {
        MODO_MENU, MODO_FORMACION, MODO_ASESORIA, MODO_AGENTES, MODO_CURSOS,
        MODO_NAT, MODO_COACH, MODO_IA_CAMPO, MODO_VENTAS, MODO_FINANZAS, MODO_CAFE,
    }
    try:
        modo = (sesion_de(telefono).modo or '').strip()
    except DatabaseError:
        logger.exception('registro_modo_sesion')
        return False
    return modo in modos


def _enviar_flow(
    telefono: str,
    cliente_id: int | None,
    texto: str | None = None,
    cta: str | None = None,
) -> None:
    flow_id = flow_id_registro()
    if not flow_id:
        _avisar(telefono, TEXTO_SIN_FLOW)
        return
    from core.lineas.envio import enviar_meta_flow

    resultado = enviar_meta_flow(
        telefono,
        (texto or TEXTO_FLOW).strip() or TEXTO_FLOW,
        flow_id,
        pantalla=PANTALLA,
        flow_token=token_de_cliente(cliente_id),
        cta=(cta or CTA),
        agente_evento='registro_flow',
        modo='published',
        con_datos=False,
    )
    if not resultado.get('success'):
        _avisar(telefono, TEXTO_REINTENTO)


def _cliente_de_turno(telefono: str, body: str) -> int | None:
    """La organización del enlace, la guardada, o la de la ficha."""
    destino = leer_frase(body)
    if destino and destino[0] == 'cliente':
        _recordar(telefono, destino[1])
        return destino[1]
    agri = destino_frase_agri(body)
    if agri:
        _recordar(telefono, agri[1])
        return agri[1]
    guardado = _cliente_guardado(telefono)
    if guardado:
        return guardado
    ficha = _ficha(telefono)
    if ficha is not None and ficha.cliente_id:
        return ficha.cliente_id
    return None


def _ficha(telefono: str):
    """Ficha usable. Sin cédula real, sigue en el registro."""
    from django.db import DatabaseError

    from core.utils_telefono import estudiante_por_telefono

    try:
        est = estudiante_por_telefono(telefono)
    except DatabaseError:
        logger.exception('registro_ficha')
        return None
    if est is None or not est.acepto_terminos:
        return None
    cedula = est.cedula or ''
    if cedula.startswith(('TEMP_', 'GEN')) or not (est.nombre or '').strip():
        return None
    return est


def _recordar(telefono: str, cliente_id: int) -> None:
    from django.db import DatabaseError

    from core.lineas.sesion import sesion_de

    try:
        sesion = sesion_de(telefono)
        if sesion.registro_cliente_id != cliente_id:
            sesion.registro_cliente_id = cliente_id
            sesion.save(update_fields=['registro_cliente_id', 'actualizado_en'])
    except DatabaseError:
        logger.exception('registro_cliente_sesion')


def _cliente_guardado(telefono: str) -> int | None:
    from django.db import DatabaseError

    from core.lineas.sesion import sesion_de

    try:
        sesion = sesion_de(telefono)
    except DatabaseError:
        logger.exception('registro_cliente_leido')
        return None
    return sesion.registro_cliente_id or None


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
