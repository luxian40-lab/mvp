"""Charla de entrada a asesoría: cómo está, ficha, y qué quiere entender.

No llama al agente ni suma el cupo. Quien llama manda el mensaje.
Fuera del ciclo de imports. No repite lo que la persona acaba de escribir.
"""
from __future__ import annotations

import re

from django.db import IntegrityError

from core.lineas.principal.derivar_asesoria import PIE_ASESORIA
from core.lineas.principal.ficha_negocio import _SALIDAS, _SALTAR, _parece_pregunta

_CONTEXTO = 'Cuénteme de usted: de dónde es y a qué se dedica.'
_ENTENDER = '¿qué quiere entender mejor?'
_VERBOS = re.compile(
    r'((?:vendo|cultivo|produzco|siembro|trabajo en|me dedico a)\s+.+)',
    re.IGNORECASE,
)
_VENDEDOR = re.compile(r'vendedor(?:a)? de\s+(\S+)', re.IGNORECASE)


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
    if not (ficha.lugar or '').strip() and not (ficha.dedica or '').strip():
        return 'contexto'
    if not (ficha.lugar or '').strip():
        return 'lugar'
    if not (ficha.dedica or '').strip():
        return 'dedica'
    return 'indaga1'


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


def _oficio_corto(dedica: str) -> str:
    """Una palabra de lo que hace, para la pregunta. Vacío si no hay una clara."""
    texto = (dedica or '').strip()
    m = re.search(
        r'(?:vendo|cultivo|produzco|siembro|trabajo en|me dedico a)\s+(\S+)',
        texto,
        re.IGNORECASE,
    )
    palabra = m.group(1) if m else ''
    if not palabra:
        hallado = _VENDEDOR.search(texto)
        palabra = hallado.group(1) if hallado else ''
    palabra = palabra.strip('.,').lower()
    if not palabra or palabra in {'con', 'en', 'para', 'de', 'y', 'que', 'mi', 'el', 'la'}:
        return ''
    return palabra


def _sacar_contexto(texto: str) -> tuple[str, str]:
    """(lugar, a qué se dedica) si la frase abierta ya los trae."""
    lugar = ''
    m = re.search(r'(?:soy de|vivo en|estoy en)\s+(.+)', texto, re.IGNORECASE)
    if not m and texto.lower().startswith('de '):
        m = re.search(r'^de\s+(.+)', texto, re.IGNORECASE)
    if m:
        trozo = re.split(r'\s+y\s+|,', m.group(1).strip(), maxsplit=1, flags=re.IGNORECASE)[0]
        lugar = ' '.join(trozo.strip(' .').split()[:3])
    dedica = ''
    hecho = _VERBOS.search(texto)
    if hecho:
        dedica = hecho.group(1).strip(' .')
    if not lugar and not dedica:
        if len(texto.split()) <= 3:
            lugar = texto.strip(' .')
        else:
            dedica = texto.strip(' .')
    return lugar[:80], dedica[:200]


def _numero_indaga(entrada: str) -> int:
    resto = (entrada or '').removeprefix('indaga')
    return int(resto) if resto.isdigit() else 0


def _con_pie(pregunta: str) -> str:
    return f'{pregunta}\n\n{PIE_ASESORIA}'


def _pregunta_de(salida: str) -> str:
    """La pregunta del modelo, o vacío si toca derivar o la respuesta no sirve."""
    texto = ' '.join((salida or '').split())
    if not texto or texto.upper().startswith('DERIVAR'):
        return ''
    if '?' in texto:
        texto = texto[:texto.find('?') + 1].strip()
    if '?' not in texto or len(texto) > 320:
        return ''
    return texto


def _llamar(telefono: str, mensajes: list) -> str:
    from django.conf import settings

    from core.presupuesto_llm import debe_degradar

    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key or debe_degradar():
        return ''
    from core.openai_compat import cliente_openai, completar_chat, contexto_uso_llm

    marca = contexto_uso_llm(telefono=telefono, agente='entrada_asesoria')
    try:
        return completar_chat(
            cliente_openai(api_key),
            getattr(settings, 'EKI_ASESORIA_ENTRADA_MODELO', 'gpt-6-luna'),
            mensajes,
            120,
        )
    finally:
        marca.var.reset(marca)


def _mensajes_primera(ficha) -> list:
    sistema = (
        'Habla por WhatsApp con una persona en Colombia. De usted. '
        'Una sola pregunta, corta, sobre qué se le está complicando en lo que hace. '
        'No suponga que el problema es el cultivo: puede ser la venta o la plata. '
        'No nombre asesores ni dé consejos. No repita la frase completa. Solo la pregunta.'
    )
    datos = f"Lugar: {(ficha.lugar or '').strip()}\nSe dedica a: {(ficha.dedica or '').strip()}"
    return [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': datos[:500]}]


def _mensajes_sigue(ficha, dicho: str) -> list:
    sistema = (
        'Responda DERIVAR si la última frase ya dice el problema '
        '(la mata, quién compra, el precio, la ganancia, las cuentas, el ánimo o la tecnología). '
        'Si solo nombra el oficio, o dice que se queda sin plata sin aclarar si no se vende '
        'o si entra y no cubre lo que gasta, haga una sola pregunta de usted para distinguirlo. '
        'Sin asesores, sin consejos, sin repetir la frase completa. DERIVAR o la pregunta, nada más.'
    )
    datos = (
        f"Se dedica a: {(ficha.dedica or '').strip()}\n"
        f"Lugar: {(ficha.lugar or '').strip()}\n"
        f"Última frase: {dicho}"
    )
    return [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': datos[:700]}]


def _texto_entender(ficha) -> str:
    oficio = _oficio_corto(ficha.dedica)
    if oficio:
        cuerpo = f'Del {oficio}, {_ENTENDER}'
    else:
        cuerpo = f'De lo que me contó, {_ENTENDER}'
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
    if paso == 'contexto':
        return _CONTEXTO
    if paso == 'lugar':
        return '¿De dónde es?'
    if paso == 'dedica':
        return '¿A qué se dedica?'
    return _texto_entender(ficha)


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
    elif paso == 'contexto':
        lugar, dedica = _sacar_contexto(crudo)
        if lugar and not (ficha.lugar or '').strip():
            ficha.lugar = lugar[:80]
        if dedica and not (ficha.dedica or '').strip():
            ficha.dedica = dedica[:200]
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
        return _texto_entender(ficha)
    if ficha.entrada == 'duda' or _parece_pregunta(t):
        _cerrar(ficha)
        return None
    n = _numero_indaga(ficha.entrada)
    if n:
        if n >= 3:
            _cerrar(ficha)
            return None
        pregunta = _pregunta_de(_llamar(telefono, _mensajes_sigue(ficha, crudo)))
        if not pregunta:
            _cerrar(ficha)
            return None
        ficha.entrada = f'indaga{n + 1}'
        ficha.save(update_fields=['entrada', 'actualizada_en'])
        return _con_pie(pregunta)
    _guardar_respuesta(ficha, telefono, crudo)
    if ficha.entrada == 'indaga1':
        pregunta = _pregunta_de(_llamar(telefono, _mensajes_primera(ficha)))
        if not pregunta:
            ficha.entrada = 'duda'
            ficha.save(update_fields=['entrada', 'actualizada_en'])
            return _texto_entender(ficha)
        return _con_pie(pregunta)
    return texto_de(telefono, ficha)
