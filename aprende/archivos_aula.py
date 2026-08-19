"""Validación de archivos subidos en el aula web."""

from __future__ import annotations

import os

from django.core.exceptions import ValidationError

MAX_ARCHIVO_MB = 25
MAX_VIDEO_CLASE_MB = 100  # subida directa a S3; preferir URL YouTube/Vimeo si es más pesado
EXTENSIONES_PERMITIDAS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.zip', '.txt', '.mp4',
})
EXTENSIONES_VIDEO = frozenset({'.mp4', '.webm', '.mov', '.m4v'})
EXTENSIONES_AVATAR = frozenset({'.jpg', '.jpeg', '.png', '.gif', '.webp'})
MAX_AVATAR_MB = 5


def validar_archivo_entrega(archivo) -> None:
    if not archivo:
        raise ValidationError('Debes adjuntar un archivo.')
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            f'Formato no permitido ({ext or "sin extensión"}). '
            f'Usa PDF, Word, Excel, imagen o ZIP.'
        )
    if archivo.size > MAX_ARCHIVO_MB * 1024 * 1024:
        raise ValidationError(f'El archivo no puede superar {MAX_ARCHIVO_MB} MB.')


def validar_archivo_clase_profesor(archivo, *, tipo_hint: str = '') -> None:
    """
    Archivo de lección (PDF/imagen/audio/video) subido por el profesor.
    Videos: máx. 100 MB; recomendado ≤ 50 MB o URL externa.
    """
    if not archivo:
        return
    ext = os.path.splitext(archivo.name)[1].lower()
    es_video = (tipo_hint or '').lower() == 'video' or ext in EXTENSIONES_VIDEO
    if es_video:
        if ext and ext not in EXTENSIONES_VIDEO:
            raise ValidationError('Video: usa MP4, WebM o MOV.')
        if archivo.size > MAX_VIDEO_CLASE_MB * 1024 * 1024:
            raise ValidationError(
                f'El video no puede superar {MAX_VIDEO_CLASE_MB} MB. '
                f'Para clases más largas usa URL de YouTube/Vimeo o un MP4 ≤ {MAX_VIDEO_CLASE_MB} MB.'
            )
        return
    if ext and ext not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            f'Formato no permitido ({ext or "sin extensión"}).'
        )
    if archivo.size > MAX_ARCHIVO_MB * 1024 * 1024:
        raise ValidationError(f'El archivo no puede superar {MAX_ARCHIVO_MB} MB.')


def validar_foto_perfil(archivo) -> None:
    if not archivo:
        return
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXTENSIONES_AVATAR:
        raise ValidationError('La foto debe ser JPG, PNG, GIF o WebP.')
    if archivo.size > MAX_AVATAR_MB * 1024 * 1024:
        raise ValidationError(f'La foto no puede superar {MAX_AVATAR_MB} MB.')
