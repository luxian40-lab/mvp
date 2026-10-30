"""Charla de entrada a asesoría: cómo está, ficha, y recién ahí la duda.

No llama al agente ni suma el cupo. Quien llama manda el mensaje.
Fuera del ciclo de imports.
"""
from __future__ import annotations

from django.db import IntegrityError

from core.lineas.principal.derivar_asesoria import PIE_ASESORIA
from core.lineas.principal.ficha_negocio import _SALIDAS, _SALTAR, _parece_pregunta

_DUDA = '¿Qué duda tiene, o qué le gustaría hacer?'


def _limpia(texto: str) -> str:
    from core.conocimiento_agentes import _sin_datos_personales

    return ' '.join(_sin_datos_personales(texto or '').split())


def _ficha(telefono: str):
    from core.models import FichaNegocio

    try:
        ficha, _ = FichaNegocio.objects.get_or_create(telefono=telefono)
    except IntegrityError:
        ficha = FichaNegocio.objects.get(telefono=telefono)
    return ficha


def _nombre(telefono: str, ficha) -> str:
    from core.utils_telefono import estudiante_por_telefono

    nombre = ''
    estudiante = estudiante_por_telefono(telefono)
    if estudiante is not None:
        nombre = (estudiante.nombre or '').strip()
        if nombre.lower() == 'usuario':
            nombre = ''
    if not nombre:
        nombre = (ficha.trato or '').strip()
    return nombre.split()[0] if nombre else ''


def _paso_que_falta(telefono: str, ficha) -> str:
    if not (ficha.como_esta or '').strip():
        return 'como_esta'
    if not _nombre(telefono, ficha):
        return 'trato'
    if not (ficha.lugar or '').strip():
        return 'lugar'
    if not (ficha.dedica or '').strip():
        return 'dedica'
    return 'duda'


def _mayus(texto: str) -> str:
    texto = (texto or '').strip()
    if not texto:
        return ''
    return texto[0].upper() + texto[1:]


def _sin_de(texto: str) -> str:
    t = (texto or '').strip()
    bajo = t.lower()
    for prefijo in ('soy de ', 'vivo en ', 'de '):
        if bajo.startswith(prefijo):
            return t[len(prefijo):].strip()
    return t


def _partir(texto: str) -> tuple[str, str]:
    if ',' not in texto:
        return texto, ''
    izquierda, derecha = texto.split(',', 1)
    derecha = derecha.strip(' .')
    izquierda = izquierda.strip()
    if len(derecha) < 3 or not izquierda:
        return texto, ''
    return izquierda, derecha


def _texto_duda(ficha) -> str:
    dedica = (ficha.dedica or '').strip()
    lugar = (ficha.lugar or '').strip()
    if dedica and lugar:
        cabeza = f'{_mayus(dedica)}, en {lugar}.'
    elif dedica:
        cabeza = f'{_mayus(dedica)}.'
    elif lugar:
        cabeza = f'{_mayus(lugar)}.'
    else:
        cabeza = ''
    cuerpo = f'{cabeza} {_DUDA}'.strip()
    return f'{cuerpo}\n\n{PIE_ASESORIA}'


def texto_de(telefono: str, ficha) -> str:
    """Lo que toca decir en el paso actual."""
    paso = ficha.entrada or _paso_que_falta(telefono, ficha)
    if paso == 'como_esta':
        nombre = _nombre(telefono, ficha)
        saludo = f'Hola, {nombre}. ¿Cómo está?' if nombre else 'Hola. ¿Cómo está?'
        return f'{saludo}\n\n{PIE_ASESORIA}'
    if paso == 'trato':
        return '¿Cómo le digo?'
    if paso == 'lugar':
        animo = _mayus(ficha.como_esta)
        return f'{animo}. ¿De dónde es?' if animo else '¿De dónde es?'
    if paso == 'dedica':
        lugar = _mayus(ficha.lugar)
        return f'{lugar}. ¿A qué se dedica?' if lugar else '¿A qué se dedica?'
    return _texto_duda(ficha)


def iniciar(telefono: str) -> str:
    """Cada entrada a asesoría vuelve a preguntar cómo está. El lugar y la dedica se quedan."""
    ficha = _ficha(telefono)
    ficha.entrada = 'como_esta'
    ficha.como_esta = ''
    ficha.pendiente = ''
    ficha.save(update_fields=['entrada', 'como_esta', 'pendiente', 'actualizada_en'])
    return texto_de(telefono, ficha)


def _cerrar(ficha) -> None:
    ficha.entrada = ''
    ficha.save(update_fields=['entrada', 'actualizada_en'])


def _guardar_respuesta(ficha, telefono: str, crudo: str) -> None:
    paso = ficha.entrada
    if paso == 'como_esta':
        ficha.como_esta = crudo[:200]
    elif paso == 'trato':
        ficha.trato = crudo[:40]
    elif paso == 'lugar':
        lugar, resto = _partir(crudo)
        limpio = _sin_de(lugar)
        ficha.lugar = (limpio or lugar)[:80]
        if resto and not (ficha.dedica or '').strip():
            ficha.dedica = resto[:200]
    elif paso == 'dedica':
        ficha.dedica = crudo[:200]
    ficha.entrada = _paso_que_falta(telefono, ficha)
    ficha.save(update_fields=['entrada', 'como_esta', 'trato', 'lugar', 'dedica', 'actualizada_en'])


def responder(telefono: str, texto: str) -> str | None:
    """Texto a enviar, o None si el mensaje sigue su camino (la duda, o no era esta charla)."""
    from core.models import FichaNegocio

    ficha = FichaNegocio.objects.filter(telefono=telefono).first()
    if ficha is None or not ficha.entrada:
        return None
    crudo = _limpia(texto)
    t = crudo.lower()
    if not t:
        return None
    if t in _SALIDAS or t.isdigit():
        _cerrar(ficha)
        return None
    if t in _SALTAR:
        ficha.entrada = 'duda'
        ficha.save(update_fields=['entrada', 'actualizada_en'])
        return _texto_duda(ficha)
    if ficha.entrada == 'duda' or _parece_pregunta(t):
        _cerrar(ficha)
        return None
    _guardar_respuesta(ficha, telefono, crudo)
    return texto_de(telefono, ficha)
