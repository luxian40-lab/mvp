"""Prompts con contexto completo de lección — imágenes y Runway."""
from __future__ import annotations

from core.course_engine.types import Scene, SceneType, Storyboard


def _clip(s: str, n: int) -> str:
    t = (s or '').strip()
    return t if len(t) <= n else t[: n - 1] + '…'


def contexto_leccion(
    *,
    titulo_leccion: str = '',
    objetivo: str = '',
    brief: str = '',
) -> str:
    parts = []
    if titulo_leccion:
        parts.append(f'Lección: {titulo_leccion}')
    if objetivo:
        parts.append(f'Objetivo: {_clip(objetivo, 200)}')
    if brief:
        parts.append(f'Brief: {_clip(brief, 300)}')
    return ' | '.join(parts)


def prompt_imagen_escena(
    escena: Scene,
    *,
    titulo_leccion: str = '',
    objetivo: str = '',
    brief: str = '',
) -> str:
    ctx = contexto_leccion(titulo_leccion=titulo_leccion, objetivo=objetivo, brief=brief)
    visual = (escena.notas_visuales or escena.titulo or 'Ilustración educativa rural').strip()
    tema = (escena.titulo or '').strip()

    if escena.tipo in {SceneType.TEXTO, SceneType.RESUMEN}:
        return (
            f'Fotografía realista de fondo para microlearning agrícola latinoamericano. '
            f'{ctx}. Tema de escena: {tema}. '
            f'Escena visual (sin palabras, sin letras, sin subtítulos en la imagen): {visual}. '
            f'El texto en pantalla se añade después — imagen solo fondo limpio.'
        )

    if escena.tipo == SceneType.DIAGRAMA:
        return (
            f'Diagrama educativo simple, infografía clara, fondo blanco, sin texto ilegible. '
            f'{ctx}. Tema: {tema}. {visual}'
        )

    guion = _clip(escena.guion, 120)
    extra = f' Relacionado con: {guion}.' if guion else ''
    return (
        f'Ilustración educativa realista, campo rural latinoamericano, luz natural. '
        f'{ctx}. Escena: {tema}. {visual}.{extra} '
        f'Sin marcas de agua, sin texto en imagen, coherente con la lección.'
    )


def prompt_runway_escena(
    escena: Scene,
    *,
    titulo_leccion: str = '',
    objetivo: str = '',
    brief: str = '',
    storyboard: Storyboard | None = None,
) -> str:
    ctx = contexto_leccion(titulo_leccion=titulo_leccion, objetivo=objetivo, brief=brief)
    visual = (escena.notas_visuales or escena.titulo or '').strip()
    guion = _clip(escena.guion, 200)
    titulo = (escena.titulo or '').strip()

    parts = [
        'Video educativo documental rural, movimiento suave de cámara.',
        ctx,
        f'Escena «{titulo}».' if titulo else '',
        f'Acción visual: {visual}.' if visual else '',
        f'Narración de referencia (mantener coherencia temática): {guion}.' if guion else '',
        'Respetar fielmente el keyframe: misma plantación, cultivo, personas y entorno.',
        'No cambiar a otro cultivo ni a contenido genérico de agricultura.',
    ]

    if storyboard and storyboard.objetivo:
        parts.append(f'Objetivo pedagógico: {_clip(storyboard.objetivo, 150)}.')

    return ' '.join(p for p in parts if p)[:1000]
