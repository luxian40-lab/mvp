"""Bienvenida opcional del alta. Usa plantillas Meta ya aprobadas.

No afloja el opt-in ni el opt-out. Si Meta responde con un error reintentable,
se intenta una vez más en la misma petición. El estudiante ya está guardado.
"""
from __future__ import annotations

from core.plantilla_meta_editor import es_bienvenida, sugerir_mapeo


def plantillas_bienvenida_aprobadas():
    from core.models_campana_meta import PlantillaMeta

    filas = PlantillaMeta.objects.filter(estado='APPROVED', activa=True).order_by('id')
    return [fila for fila in filas if es_bienvenida(fila)]


def hay_plantilla_bienvenida() -> bool:
    return bool(plantillas_bienvenida_aprobadas())


def elegir_bienvenida(organizacion, curso):
    aprobadas = plantillas_bienvenida_aprobadas()
    if not aprobadas:
        return None

    def nombre(fila) -> str:
        return f'{fila.meta_name} {fila.nombre_interno}'.casefold()

    if curso is not None:
        con_curso = [fila for fila in aprobadas if 'curso' in nombre(fila)]
        if con_curso:
            return con_curso[0]
    if organizacion is None:
        genericas = [
            fila for fila in aprobadas
            if any(clave in nombre(fila) for clave in ('generic', 'b2c', 'sin_org'))
        ]
        if genericas:
            return genericas[0]
    return aprobadas[0]


class _Mapeo:
    def __init__(self, mapeo: dict):
        self.mapeo_header = mapeo.get('mapeo_header') or ''
        self.mapeo_body = mapeo.get('mapeo_body') or ''
        self.mapeo_boton = mapeo.get('mapeo_boton') or ''


def enviar_bienvenida_alta(estudiante, cursos=None) -> dict:
    """Devuelve ok y un motivo en español. No lanza si el envío falla."""
    from django.conf import settings

    from core.campana_meta_v2 import clasificar_respuesta
    from core.consentimiento_wa import puede_recibir_plantilla
    from core.meta_waba import _parametros_envio, _phone_default, _post, _version

    if not puede_recibir_plantilla(estudiante):
        if getattr(estudiante, 'wa_optout_fecha', None):
            return {'ok': False, 'motivo': 'Pidió no recibir más mensajes.'}
        return {
            'ok': False,
            'motivo': 'No tiene aceptación de datos (opt-in). No se envía la plantilla.',
        }
    curso = None
    if cursos:
        curso = list(cursos)[0]
    plantilla = elegir_bienvenida(getattr(estudiante, 'cliente', None), curso)
    if plantilla is None:
        return {'ok': False, 'motivo': 'No hay una plantilla de bienvenida aprobada.'}
    try:
        componentes = _parametros_envio(plantilla, _Mapeo(sugerir_mapeo(plantilla)), estudiante)
    except ValueError as exc:
        return {'ok': False, 'motivo': str(exc)}
    phone_id = (_phone_default() or '').strip()
    if not phone_id:
        return {'ok': False, 'motivo': 'Falta el número de la línea Meta.'}
    base = str(getattr(settings, 'WHATSAPP_GRAPH_BASE_URL', 'https://graph.facebook.com')).rstrip('/')
    url = f'{base}/{_version()}/{phone_id}/messages'
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
    status, data = _post(url, payload)
    estado, motivo = clasificar_respuesta(status, data if isinstance(data, dict) else {})
    if estado == 'ERROR_REINTENTABLE':
        status, data = _post(url, payload)
        estado, motivo = clasificar_respuesta(status, data if isinstance(data, dict) else {})
    if estado == 'ENVIADO':
        return {'ok': True, 'motivo': ''}
    return {'ok': False, 'motivo': motivo or 'Meta no aceptó el envío.'}
