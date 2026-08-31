"""Perfiles visuales Course Engine — documental vs ilustración."""
from __future__ import annotations

# Perfil documental: menos “look IA”, más foto/video profesional rural.
PERFIL_DOCUMENTAL = 'documental'

_KEYFRAME_CAFE = (
    'Fotografía documental profesional, cámara DSLR, luz natural de mañana, '
    'caficultor colombiano revisando plantas de café en ladera andina, '
    'texturas reales de hojas y suelo, profundidad de campo suave, '
    'estilo reportaje agrícola National Geographic, NO ilustración, NO CGI, '
    'NO arte digital, NO rostros deformes, sin texto ni marcas de agua en imagen.'
)

_MOTION_DOCUMENTAL = (
    'Movimiento muy sutil de cámara tipo documental: slow dolly lateral suave, '
    'misma escena del keyframe, luz natural consistente, sin morphing fantástico, '
    'sin objetos flotantes, ambiente rural profesional educativo.'
)


def prompt_keyframe_documental(*, tema: str = '') -> str:
    tema = (tema or 'Manejo del cultivo de café').strip()
    return f'{_KEYFRAME_CAFE} Tema educativo: {tema}.'


def prompt_runway_documental(*, tema: str = '') -> str:
    tema = (tema or 'café de especialidad').strip()
    return f'{_MOTION_DOCUMENTAL} Coherente con lección sobre {tema}.'


def sufijo_imagen_documental() -> str:
    return (
        ' Fotografía real documental, NO ilustración digital, NO render 3D, '
        'NO estilo cartoon, granos de película natural, Colombia rural.'
    )
