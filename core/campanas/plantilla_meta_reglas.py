"""Reglas de alta e importación de plantillas Meta.

No envía mensajes ni llama a Graph. La creación en Meta sigue en meta_waba.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from core.models_campana_meta import (
    CAMPOS_ORIGEN_VARIABLE,
    _NOMBRE_META_RE,
    ejemplos_lista,
    sanitizar_nombre_meta,
    validar_variables_secuenciales,
    variables_en,
)

_COMPONENTES_CONOCIDOS = frozenset({'BODY', 'HEADER', 'FOOTER', 'BUTTONS', 'CAROUSEL'})
_FORMATOS_HEADER = {
    'TEXT': '',
    'IMAGE': 'IMAGEN',
    'VIDEO': 'VIDEO',
    'DOCUMENT': 'DOCUMENTO',
    'LOCATION': 'UBICACION',
}
_BOTONES_CONOCIDOS = frozenset({'QUICK_REPLY', 'URL', 'PHONE_NUMBER'})
_CATEGORIAS = frozenset({'MARKETING', 'UTILITY', 'AUTHENTICATION'})
_CALIDAD_ETIQUETA = {
    'GREEN': 'Alta',
    'YELLOW': 'Media',
    'RED': 'Baja',
    'UNKNOWN': 'Sin dato',
}
ORIGENES_VARIABLE = {clave for clave, _etiqueta in CAMPOS_ORIGEN_VARIABLE}


def etiqueta_calidad(valor: str) -> str:
    bruto = (valor or '').strip().upper()
    if not bruto:
        return 'Sin dato'
    return _CALIDAD_ETIQUETA.get(bruto, bruto)


def puntaje_calidad(item: dict) -> str:
    """Solo el score que manda Meta. Vacío si no vino."""
    dato = item.get('quality_score') if isinstance(item, dict) else None
    if isinstance(dato, dict):
        return str(dato.get('score') or '').strip().upper()[:32]
    if isinstance(dato, str):
        return dato.strip().upper()[:32]
    return ''


def categoria_meta(item: dict) -> str:
    bruto = str((item or {}).get('category') or '').strip().upper()
    if bruto in _CATEGORIAS:
        return bruto
    return ''


def tipo_desde_componentes(componentes, categoria: str = '') -> str:
    """Mapea componentes de Graph. Lo desconocido queda en Otro y no rompe el lote."""
    try:
        if str(categoria or '').strip().upper() == 'AUTHENTICATION':
            return 'AUTENTICACION'
        if not isinstance(componentes, list):
            return 'OTRO' if componentes else 'TEXTO'
        tipos = []
        for comp in componentes:
            if not isinstance(comp, dict):
                return 'OTRO'
            tipos.append(str(comp.get('type') or '').strip().upper())
        if 'CAROUSEL' in tipos:
            return 'CARRUSEL'
        for comp in componentes:
            tipo = str(comp.get('type') or '').strip().upper()
            if tipo not in _COMPONENTES_CONOCIDOS:
                return 'OTRO'
            if tipo == 'BUTTONS':
                for boton in comp.get('buttons') or []:
                    if not isinstance(boton, dict):
                        return 'OTRO'
                    if str(boton.get('type') or '').strip().upper() not in _BOTONES_CONOCIDOS:
                        return 'OTRO'
            if tipo == 'HEADER':
                formato = str(comp.get('format') or 'TEXT').strip().upper()
                if formato not in _FORMATOS_HEADER:
                    return 'OTRO'
        for comp in componentes:
            if str(comp.get('type') or '').strip().upper() != 'HEADER':
                continue
            formato = str(comp.get('format') or 'TEXT').strip().upper()
            mapeado = _FORMATOS_HEADER.get(formato, '')
            if mapeado:
                return mapeado
        return 'TEXTO'
    except Exception:
        return 'OTRO'


def cuerpo_desde_componentes(componentes) -> str:
    if not isinstance(componentes, list):
        return ''
    for comp in componentes:
        if isinstance(comp, dict) and str(comp.get('type') or '').upper() == 'BODY':
            return str(comp.get('text') or '').strip()
    return ''


def _mensajes(exc: ValidationError) -> list[str]:
    if getattr(exc, 'message_dict', None):
        salida = []
        for lista in exc.message_dict.values():
            salida.extend(lista)
        return salida
    return list(exc.messages)


def errores_de_alta(datos) -> list[str]:
    """Reglas de Meta para el asistente. No guarda."""
    errores: list[str] = []
    nombre = (datos.get('nombre_interno') or '').strip()
    meta = (datos.get('meta_name') or '').strip()
    if not nombre:
        errores.append('Escriba el nombre visible.')
    if meta and not _NOMBRE_META_RE.match(meta):
        errores.append('El nombre técnico solo admite minúsculas, números y guion bajo.')
    elif nombre and not sanitizar_nombre_meta(meta or nombre):
        errores.append('El nombre técnico solo admite minúsculas, números y guion bajo.')

    cuerpo = datos.get('cuerpo') or ''
    if not str(cuerpo).strip():
        errores.append('Escriba el mensaje.')
    elif len(cuerpo) > 1024:
        errores.append('El mensaje supera 1024 caracteres.')
    else:
        try:
            validar_variables_secuenciales(cuerpo, 'cuerpo')
        except ValidationError as exc:
            errores.extend(_mensajes(exc))

    footer = datos.get('footer') or ''
    if len(footer) > 60:
        errores.append('El pie supera 60 caracteres.')

    for n in (1, 2):
        texto = (datos.get(f'boton_{n}_texto') or '').strip()
        if len(texto) > 25:
            errores.append(f'El botón {n} supera 25 caracteres.')
        tipo_b = (datos.get(f'boton_{n}_tipo') or '').strip()
        if tipo_b and not texto:
            errores.append(f'El botón {n} necesita un texto.')

    nums = []
    for texto in (
        cuerpo,
        datos.get('header_texto') or '',
        datos.get('boton_1_url') or '',
        datos.get('boton_2_url') or '',
    ):
        nums.extend(variables_en(texto))
    unicos = sorted(set(nums))
    ejemplos = datos.get('ejemplos_por_variable')
    if not isinstance(ejemplos, dict):
        partes = ejemplos_lista(datos.get('ejemplos_cuerpo') or '')
        ejemplos = {str(i + 1): partes[i] for i in range(len(partes))}
    for numero in unicos:
        if not str(ejemplos.get(str(numero)) or '').strip():
            errores.append(f'Falta el ejemplo de la variable {{{{{numero}}}}}.')

    tipo = (datos.get('tipo') or 'TEXTO').upper()
    if tipo == 'CARRUSEL':
        tarjetas = datos.get('tarjetas') or []
        if not isinstance(tarjetas, list) or not (2 <= len(tarjetas) <= 10):
            errores.append('El carrusel necesita entre 2 y 10 tarjetas.')
        else:
            claves = []
            for tarjeta in tarjetas:
                if not isinstance(tarjeta, dict):
                    errores.append('Una tarjeta del carrusel no tiene la estructura esperada.')
                    break
                claves.append(tuple(sorted(tarjeta.keys())))
                if not (tarjeta.get('titulo') or '').strip():
                    errores.append('Cada tarjeta necesita un título.')
                    break
                if not (tarjeta.get('cuerpo') or '').strip():
                    errores.append('Cada tarjeta necesita un texto.')
                    break
            if len(set(claves)) > 1:
                errores.append('Todas las tarjetas deben tener la misma estructura.')
    return errores


def numeros_de_variables(*textos: str) -> list[int]:
    vistos = []
    for texto in textos:
        for numero in variables_en(texto or ''):
            if numero not in vistos:
                vistos.append(numero)
    return vistos


_VAR_CHIP = re.compile(r'\{\{(\d+)\}\}')


def html_con_variables(texto: str) -> str:
    """Escapa el texto y marca {{n}} como chip. Para la vista previa."""
    from django.utils.html import escape

    partes = []
    cursor = 0
    bruto = texto or ''
    for match in _VAR_CHIP.finditer(bruto):
        partes.append(escape(bruto[cursor:match.start()]))
        partes.append(f'<span class="pm-var-chip">{escape(match.group(0))}</span>')
        cursor = match.end()
    partes.append(escape(bruto[cursor:]))
    return ''.join(partes)


def bloqueo_envio(plantilla) -> str:
    """Vacío si se puede enviar. Si no, el motivo en español."""
    if plantilla is None:
        return 'No se encontró la plantilla.'
    if plantilla.estado == 'APPROVED':
        return ''
    motivo = (plantilla.rejected_reason or '').strip()
    texto = (
        f'La plantilla está en {plantilla.get_estado_display()}. '
        'Solo se envía cuando Meta la deja Aprobada.'
    )
    if motivo and motivo.upper() != 'NONE':
        texto = f'{texto} Motivo: {motivo}.'
    return texto
