"""Modo diagnóstico agronómico — Nat hace preguntas antes de recomendar (estilo AgroChat)."""

from __future__ import annotations

import re

_PATRON_SINTOMA = re.compile(
    r'\b(mancha|manchas|plaga|plagas|enfermedad|seco|seca|amarill|caíd|caid|'
    r'marchit|roya|gusano|hongos?|problema|daño|dano|síntoma|sintoma|'
    r'no crece|se muere|se están muriendo|tengo unas)\b',
    re.I,
)


def _get_meta(ctx) -> dict:
    if not ctx:
        return {}
    meta = getattr(ctx, 'metadata', None) or {}
    return dict(meta) if isinstance(meta, dict) else {}


def _set_meta(ctx, meta: dict) -> None:
    if ctx:
        ctx.metadata = meta
        ctx.save(update_fields=['metadata', 'updated_at'])


def es_consulta_diagnostico(mensaje: str) -> bool:
    return bool(_PATRON_SINTOMA.search(mensaje or ''))


def datos_suficientes(ctx) -> bool:
    if not ctx:
        return False
    cultivo = (ctx.cultivo or '').strip()
    problema = (ctx.problema or '').strip()
    ubicacion = (ctx.municipio or '').strip() or (ctx.region or '').strip()
    return bool(cultivo and problema and ubicacion)


def siguiente_pregunta_diagnostico(ctx, mensaje: str, *, tiene_imagen: bool = False) -> str | None:
    """
    Devuelve la siguiente pregunta de diagnóstico o None si puede responder con LLM.
    """
    if not ctx:
        return None

    msg = (mensaje or '').strip().lower()
    if msg in ('continuar', 'siguiente', 'no tengo foto', 'sin foto'):
        meta = _get_meta(ctx)
        meta['foto_omitida'] = True
        _set_meta(ctx, meta)

    if datos_suficientes(ctx):
        meta = _get_meta(ctx)
        if meta.get('pidio_foto') or meta.get('foto_omitida') or tiene_imagen:
            return None
        if not tiene_imagen:
            meta['pidio_foto'] = True
            _set_meta(ctx, meta)
            return (
                'Gracias por la información. ¿Puede enviarme una fotografía de la zona afectada? '
                'Si no tiene, escriba *continuar*.'
            )
        return None

    if not es_consulta_diagnostico(mensaje) and not _get_meta(ctx).get('diagnostico_activo'):
        return None

    meta = _get_meta(ctx)
    meta['diagnostico_activo'] = True
    _set_meta(ctx, meta)

    if not (ctx.cultivo or '').strip():
        return 'Para orientarle mejor: ¿qué cultivo tiene plantado?'
    if not ((ctx.municipio or '').strip() or (ctx.region or '').strip()):
        return '¿En qué municipio o vereda está ubicado el lote?'
    if not (ctx.problema or '').strip():
        return '¿Puede describir con más detalle el problema que observa en las plantas?'
    if not meta.get('tiempo_problema'):
        if len(msg) > 8 and not es_consulta_diagnostico(mensaje):
            meta['tiempo_problema'] = mensaje[:200]
            _set_meta(ctx, meta)
        else:
            return '¿Hace cuánto tiempo apareció este problema?'
    if not meta.get('fertilizacion_reciente'):
        if len(msg) > 5 and meta.get('tiempo_problema') and msg not in ('continuar',):
            meta['fertilizacion_reciente'] = mensaje[:200]
            _set_meta(ctx, meta)
        else:
            return '¿Qué fertilización o manejo nutricional realizó en las últimas semanas?'

    return None
