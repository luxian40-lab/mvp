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
    estilo: str = '',
) -> str:
    from django.conf import settings

    from core.course_engine.visual_style import PERFIL_DOCUMENTAL, sufijo_imagen_documental

    estilo = estilo or getattr(settings, 'COURSE_ENGINE_VISUAL_STYLE', '') or ''
    ctx = contexto_leccion(titulo_leccion=titulo_leccion, objetivo=objetivo, brief=brief)
    visual = (escena.notas_visuales or escena.titulo or 'Ilustración educativa rural').strip()
    tema = (escena.titulo or '').strip()
    doc_suffix = sufijo_imagen_documental() if estilo == PERFIL_DOCUMENTAL else ''

    if escena.tipo in {SceneType.TEXTO, SceneType.RESUMEN}:
        base = (
            f'Fotografía realista de fondo para microlearning agrícola latinoamericano. '
            if estilo == PERFIL_DOCUMENTAL
            else f'Fotografía realista de fondo para microlearning agrícola latinoamericano. '
        )
        return (
            f'{base}'
            f'{ctx}. Tema de escena: {tema}. '
            f'Escena visual (sin palabras, sin letras, sin subtítulos en la imagen): {visual}. '
            f'El texto en pantalla se añade después — imagen solo fondo limpio.{doc_suffix}'
        )

    if escena.tipo == SceneType.DIAGRAMA:
        return (
            f'Diagrama educativo simple, infografía clara, fondo blanco, sin texto ilegible. '
            f'{ctx}. Tema: {tema}. {visual}'
        )

    guion = _clip(escena.guion, 120)
    extra = f' Relacionado con: {guion}.' if guion else ''
    if estilo == PERFIL_DOCUMENTAL:
        return (
            f'Fotografía documental profesional, campo rural latinoamericano, luz natural. '
            f'{ctx}. Escena: {tema}. {visual}.{extra}{doc_suffix}'
        )
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
    estilo: str = '',
) -> str:
    from django.conf import settings

    from core.course_engine.visual_style import PERFIL_DOCUMENTAL, prompt_runway_documental

    estilo = estilo or getattr(settings, 'COURSE_ENGINE_VISUAL_STYLE', '') or ''
    if estilo == PERFIL_DOCUMENTAL:
        tema = (escena.titulo or brief or titulo_leccion or '').strip()
        return prompt_runway_documental(tema=tema)

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
