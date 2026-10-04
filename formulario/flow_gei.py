"""Formulario de Preserva como WhatsApp Flow, armado desde los pasos del admin.

Si Meta no publica o no entrega el Flow, la persona sigue contestando
pregunta por pregunta en el chat. Las respuestas del Flow caen en la misma ficha.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

MARCA_FLOW = '[FLOW_GEI]'
CAMPOS_POR_PANTALLA = 3
_NOMBRE_CAMPO = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,40}$')


def es_respuesta_flow(texto: str) -> bool:
    return (texto or '').startswith(MARCA_FLOW)


def datos_respuesta_flow(texto: str) -> dict:
    crudo = (texto or '')[len(MARCA_FLOW):].strip() or '{}'
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _etiqueta(pregunta) -> str:
    texto = ' '.join((pregunta.pregunta_texto or pregunta.campo_destino or 'Dato').split())
    return (texto[:20] or 'Dato')


def _campo(pregunta) -> str:
    return (pregunta.campo_destino or '').strip()


def _opciones(pregunta) -> list[str]:
    return [o.strip() for o in (pregunta.opciones_choice or '').split('|') if o.strip()]


def _control(pregunta) -> dict | None:
    nombre = _campo(pregunta)
    if not _NOMBRE_CAMPO.match(nombre):
        return None
    base = {
        'name': nombre,
        'label': _etiqueta(pregunta),
        'required': not pregunta.es_opcional,
    }
    if pregunta.tipo_dato == 'bool':
        return {
            **base,
            'type': 'RadioButtonsGroup',
            'data-source': [
                {'id': 'si', 'title': 'Sí'},
                {'id': 'no', 'title': 'No'},
            ],
        }
    if pregunta.tipo_dato == 'choice':
        opciones = _opciones(pregunta)[:20]
        if not opciones:
            return None
        return {
            **base,
            'type': 'Dropdown',
            'data-source': [
                {'id': opcion[:80], 'title': opcion[:30]}
                for opcion in opciones
            ],
        }
    control = {
        **base,
        'type': 'TextInput',
        'input-type': 'number' if pregunta.tipo_dato == 'float' else 'text',
    }
    return control


def flow_json(pasos) -> dict | None:
    """Un Flow de varias pantallas. None si algún paso no cabe en un control."""
    pasos = list(pasos)
    if not pasos:
        return None
    controles = []
    for pregunta in pasos:
        control = _control(pregunta)
        if control is None:
            return None
        controles.append((pregunta, control))

    pantallas = []
    acumulado: list[str] = []
    chunks = [
        controles[i:i + CAMPOS_POR_PANTALLA]
        for i in range(0, len(controles), CAMPOS_POR_PANTALLA)
    ]
    for indice, chunk in enumerate(chunks):
        ultima = indice == len(chunks) - 1
        sid = f'S{indice + 1}'
        payload = {nombre: f'${{data.{nombre}}}' for nombre in acumulado}
        hijos = []
        for pregunta, control in chunk:
            hijos.append({
                'type': 'TextBody',
                'text': ' '.join((pregunta.pregunta_texto or '').split())[:400] or control['label'],
            })
            hijos.append(control)
            payload[control['name']] = f"${{form.{control['name']}}}"
        if ultima:
            accion = {'name': 'complete', 'payload': payload}
            boton = 'Enviar ficha'
        else:
            accion = {
                'name': 'navigate',
                'next': {'type': 'screen', 'name': f'S{indice + 2}'},
                'payload': payload,
            }
            boton = 'Seguir'
        hijos.append({
            'type': 'Footer',
            'label': boton,
            'on-click-action': accion,
        })
        pantalla = {
            'id': sid,
            'title': f'Datos {indice + 1}'[:20],
            'data': {
                nombre: {'type': 'string', '__example__': ''}
                for nombre in acumulado
            },
            'layout': {
                'type': 'SingleColumnLayout',
                'children': [{
                    'type': 'Form',
                    'name': 'form',
                    'children': hijos,
                }],
            },
        }
        pantallas.append(pantalla)
        acumulado.extend(control['name'] for _, control in chunk)
    return {'version': '7.0', 'screens': pantallas}


def _texto_intro(tipo, n: int) -> str:
    from formulario.gei_flujos import es_formulario_balance_gei

    if es_formulario_balance_gei(tipo):
        return (
            f"Para cerrar su balance GEI necesitamos {n} datos "
            "(combustible, residuos y bosque). Toque *Llenar ficha*."
        )
    return (
        f"Datos de su finca: {n} preguntas para seguir el módulo. "
        "Toque *Llenar ficha*."
    )


def publicar_flow(tipo) -> str:
    """Crea o actualiza el Flow en Meta y guarda el id. Vacío si no hay credenciales."""
    import requests
    from django.conf import settings

    from core.sandbox_canal import _graph_headers

    waba = (getattr(settings, 'WHATSAPP_BUSINESS_ACCOUNT_ID', '') or '').strip()
    headers = _graph_headers()
    from core.meta_waba import _version

    version = _version()
    if not waba or not headers:
        return ''
    from formulario.agent import _pasos_ordenados

    documento = flow_json(_pasos_ordenados(tipo))
    if documento is None:
        return ''
    url = f'https://graph.facebook.com/{version}/{waba}/flows'
    cuerpo = {
        'name': f'eki_gei_{tipo.pk}'[:64],
        'categories': ['OTHER'],
        'flow_json': json.dumps(documento, ensure_ascii=False),
        'publish': True,
    }
    if (tipo.meta_flow_id or '').strip():
        cuerpo['clone_flow_id'] = tipo.meta_flow_id
    try:
        resp = requests.post(url, json=cuerpo, headers=headers, timeout=20)
        data = resp.json() if resp.content else {}
    except Exception:
        logger.exception('flow_gei_publicar')
        return ''
    flow_id = str(data.get('id') or '').strip()
    if resp.status_code not in (200, 201) or not flow_id:
        logger.warning('flow_gei_publicar_fallo %s', data)
        return (tipo.meta_flow_id or '').strip()
    if flow_id != (tipo.meta_flow_id or ''):
        tipo.meta_flow_id = flow_id
        tipo.save(update_fields=['meta_flow_id'])
    return flow_id


def intentar_enviar_flow(estudiante, tipo, sesion) -> bool:
    from core.sandbox_canal import enviar_meta_flow, sandbox_meta_activo

    if not sandbox_meta_activo():
        return False
    documento = None
    from formulario.agent import _pasos_ordenados

    pasos = _pasos_ordenados(tipo)
    documento = flow_json(pasos)
    if documento is None:
        return False
    flow_id = (tipo.meta_flow_id or '').strip() or publicar_flow(tipo)
    if not flow_id:
        return False
    intro = _texto_intro(tipo, len(pasos))
    resultado = enviar_meta_flow(
        estudiante.telefono,
        intro,
        flow_id,
        pantalla=documento['screens'][0]['id'],
        flow_token=f'gei-{sesion.pk}',
    )
    return bool(resultado.get('success'))


def aplicar_respuestas_flow(sesion, datos: dict) -> str:
    """Guarda el formulario completo. Si falta un dato obligatorio, sigue en el chat."""
    from formulario.agent import (
        _ajuste_valor_ficha,
        _cerrar_sesion,
        _formatear_pregunta,
        _pasos_ordenados,
        _validar_rango,
        guardar_en_destino,
        parsear_respuesta,
    )

    pasos = _pasos_ordenados(sesion.formulario)
    for idx, pregunta in enumerate(pasos):
        crudo = datos.get(_campo(pregunta))
        if crudo is None or str(crudo).strip() == '':
            if pregunta.es_opcional:
                continue
            sesion.paso_actual = idx
            sesion.reintentos_paso = 0
            sesion.save(update_fields=['paso_actual', 'reintentos_paso', 'fecha_update'])
            return (
                "Faltó un dato del formulario. Lo seguimos aquí.\n\n"
                + _formatear_pregunta(idx + 1, len(pasos), pregunta)
            )
        valor = parsear_respuesta(str(crudo).strip(), pregunta)
        if pregunta.tipo_dato == 'float' and isinstance(valor, (int, float)):
            ok, _err = _validar_rango(pregunta, float(valor))
            if not ok:
                valor = None
        valido = valor is not None and not (pregunta.tipo_dato == 'text' and not str(valor).strip())
        if pregunta.tipo_dato == 'bool':
            valido = isinstance(valor, bool)
        if not valido:
            sesion.paso_actual = idx
            sesion.save(update_fields=['paso_actual', 'fecha_update'])
            return (
                "Un dato no se pudo leer. Lo seguimos aquí.\n\n"
                + _formatear_pregunta(idx + 1, len(pasos), pregunta)
            )
        if pregunta.tipo_dato == 'text':
            guardar_en_destino(sesion, pregunta.campo_destino, str(valor).strip()[:500])
        else:
            guardar_en_destino(sesion, pregunta.campo_destino, _ajuste_valor_ficha(pregunta, valor))
    sesion.paso_actual = len(pasos)
    sesion.save(update_fields=['paso_actual', 'fecha_update'])
    return _cerrar_sesion(sesion, pasos)
