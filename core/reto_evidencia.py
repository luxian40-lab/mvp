"""
Evidencia fotográfica de un reto de campo (WhatsApp).

Guarda la foto en el storage del proyecto y la evalúa con el mismo facilitador
del curso (Claudia o tecnicoagro) usando visión.
"""
from __future__ import annotations

import logging
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

MAX_BYTES_EVIDENCIA = 8 * 1024 * 1024

_EXT_POR_MIME = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
}


def es_imagen_soportada(media_type: str | None) -> bool:
    base = (media_type or '').split(';')[0].strip().lower()
    return base in _EXT_POR_MIME


def descargar_media_twilio(media_url: str) -> tuple[bytes | None, str]:
    """Descarga el media con credenciales Twilio. Devuelve (bytes, content_type)."""
    if not media_url:
        return None, ''
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    try:
        resp = requests.get(media_url, auth=(sid, token), timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning('[reto-evidencia] descarga falló: %s', exc)
        return None, ''
    contenido = resp.content or b''
    if len(contenido) > MAX_BYTES_EVIDENCIA:
        logger.warning('[reto-evidencia] imagen muy grande (%s bytes)', len(contenido))
        return None, resp.headers.get('Content-Type', '')
    return contenido, resp.headers.get('Content-Type', '')


def guardar_evidencia(contenido: bytes, media_type: str, *, estudiante_id, curso_id) -> str:
    """Guarda la foto y devuelve la URL (o '' si falla)."""
    if not contenido:
        return ''
    base = (media_type or '').split(';')[0].strip().lower()
    ext = _EXT_POR_MIME.get(base, '.jpg')
    nombre = f'retos_evidencia/{curso_id or 0}/{estudiante_id or 0}/{uuid.uuid4().hex}{ext}'
    try:
        ruta = default_storage.save(nombre, ContentFile(contenido))
        return default_storage.url(ruta)
    except Exception as exc:
        logger.warning('[reto-evidencia] guardar falló: %s', exc)
        return ''


def evaluar_evidencia_foto(
    contenido: bytes,
    media_type: str,
    *,
    reto_original: str,
    modulos_cubiertos,
    curso=None,
    estudiante_nombre: str = 'Estudiante',
    texto_acompanante: str = '',
    modo_gamificacion=None,
) -> tuple[float | int, str] | None:
    """
    Califica la foto con el facilitador del curso. None si no hay cliente/visión.
    Devuelve (puntaje|nota, feedback) con el mismo contrato que evaluar_reto_facilitador.
    """
    import base64

    from core.facilitador_perfil import system_prompt_evaluacion_para_curso
    from core.gamificacion_modo import MODO_CALIFICACION, MODO_PUNTOS
    from core.tutor_ia_modulo import _extraer_nota_1_5, _get_client

    if not contenido:
        return None
    client = _get_client()
    if not client:
        return None

    modo = modo_gamificacion or MODO_PUNTOS
    usar_notas = modo == MODO_CALIFICACION

    modulos_info = ''
    for m in modulos_cubiertos or []:
        corto = (getattr(m, 'contenido', '') or getattr(m, 'descripcion', '') or '')[:600]
        modulos_info += f'- Módulo {getattr(m, "numero", "?")}: {getattr(m, "titulo", "")}\n  {corto}\n'

    base = (media_type or '').split(';')[0].strip().lower() or 'image/jpeg'
    data_url = f'data:{base};base64,{base64.b64encode(contenido).decode("ascii")}'

    instruccion = (
        'El participante envió una FOTO como evidencia del reto de campo.\n'
        'Describa brevemente qué se observa y evalúe si la evidencia cumple lo pedido.\n'
        'Si la foto no permite verificar el reto (borrosa, no corresponde, no muestra lo pedido), '
        'dígalo con claridad y pida la toma faltante.\n'
        'No invente diagnósticos que la imagen no sustente.'
    )
    texto_usuario = (
        f'CURSO: {getattr(curso, "nombre", "") or "Curso actual"}\n\n'
        f'Módulos cubiertos:\n{modulos_info}\n'
        f'RETO PLANTEADO: {reto_original}\n\n'
        f'MENSAJE DEL PARTICIPANTE ({estudiante_nombre}): {texto_acompanante or "(solo envió la foto)"}\n\n'
        f'{instruccion}'
    )

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt_evaluacion_para_curso(curso, usar_notas=usar_notas),
                },
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': texto_usuario},
                        {'type': 'image_url', 'image_url': {'url': data_url}},
                    ],
                },
            ],
            temperature=0.4,
            max_tokens=320,
            timeout=25,
        )
        feedback = (response.choices[0].message.content or '').strip()
        if not feedback:
            return None
        if usar_notas:
            return _extraer_nota_1_5(feedback), feedback
        import re

        match = re.search(r'(\d+)\s*/\s*10', feedback)
        puntaje = min(10, max(1, int(match.group(1)))) if match else 7
        return puntaje, feedback
    except Exception as exc:
        logger.warning('[reto-evidencia] visión falló: %s', exc)
        return None


def mensaje_evidencia_no_evaluable(nombre_facilitador: str = 'Facilitadora') -> str:
    return (
        '📸 Recibí su foto, pero no pude revisarla en este momento.\n\n'
        'Por favor cuénteme en texto o audio qué observó '
        '(qué revisó, cuántas unidades y qué encontró).\n\n'
        '✍️ _Escriba o envíe un audio con su respuesta._'
    )
