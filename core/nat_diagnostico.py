"""Modo diagnóstico agronómico — anamnesis tipo consulta de campo (estilo médico).

Nati pregunta como agrónoma real: escucha → resume lo que entendió → pide el
dato crítico que falta, personalizado al cultivo/región/síntoma ya conocidos.
"""

from __future__ import annotations

import re

_PATRON_SINTOMA = re.compile(
    r'\b(mancha|manchas|plaga|plagas|enfermedad|seco|seca|amarill|caíd|caid|'
    r'marchit|roya|gusano|hongos?|problema|daño|dano|síntoma|sintoma|'
    r'no crece|se muere|se están muriendo|tengo unas|débil|debil|'
    r'pudric|necros|deficien|clorosis|quemadur)\b',
    re.I,
)

# Escapes propios de Nati (NUNCA listo/continuar/menu del bot de cursos).
_ESCAPES_FOTO = frozenset({'saltar', 'sin foto', 'no tengo foto', 'omitir foto'})
_ESCAPES_MENU = frozenset({'asesoria', 'asesoría', 'reiniciar'})
_ESCAPES_DIAGNOSTICO = _ESCAPES_FOTO | _ESCAPES_MENU
_KEYWORDS_CURSOS = frozenset({
    'listo', 'continuar', 'menu', 'menú', 'siguiente', 'continuar curso',
    'ok', 'dale', 'sigue',
})
# Solo abortar anamnesis activa si el productor pide clima de forma explícita.
_CLIMA_EXPLICITO = re.compile(
    r'\b('
    r'primero\s+clima|c[oó]mo\s+est[aá]\s+el\s+clima|pron[oó]stico|'
    r'va\s+a\s+llover|puedo\s+fumigar\s+ma[nñ]ana|clima\s+para\s+(fumig|aplic|riego)'
    r')\b',
    re.I,
)


def _norm_msg(mensaje: str) -> str:
    """Normaliza keywords (puntuación / emoji al final)."""
    t = (mensaje or '').strip().lower()
    t = re.sub(r'[✅✔️]+', '', t)
    t = re.sub(r'[\s.!?…,;:]+$', '', t).strip()
    return t


def reiniciar_diagnostico(ctx) -> None:
    """Limpia flags de anamnesis (omit sticky, preguntas pendientes)."""
    if not ctx:
        return
    meta = _get_meta(ctx)
    for k in list(meta.keys()):
        if (
            k.startswith('_pregunto_')
            or k in (
                'diagnostico_activo',
                'diagnostico_omitido',
                'foto_omitida',
                'pidio_foto',
                'anamnesis_completa',
                'extension_afectada',
                'tiempo_problema',
                'manejo_previo',
                'fertilizacion_reciente',
                'etapa_consultada',
            )
        ):
            meta.pop(k, None)
    _set_meta(ctx, meta)


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
    """Mínimo clínico para orientar: cultivo + síntoma + ubicación."""
    if not ctx:
        return False
    cultivo = (ctx.cultivo or '').strip()
    problema = (ctx.problema or '').strip()
    ubicacion = (ctx.municipio or '').strip() or (ctx.region or '').strip()
    return bool(cultivo and problema and ubicacion)


def _cultivo_txt(ctx) -> str:
    return (ctx.cultivo or '').strip() or 'su cultivo'


def _lugar_txt(ctx) -> str:
    mun = (ctx.municipio or '').strip()
    reg = (ctx.region or '').strip()
    if mun and reg:
        return f'{mun} ({reg})'
    return mun or reg or 'su zona'


def _sintoma_corto(ctx) -> str:
    p = (ctx.problema or '').strip()
    if not p:
        return 'lo que describe'
    return p[:80] if len(p) <= 80 else (p[:77] + '…')


def _ack(ctx, frase: str) -> str:
    """Reconoce lo ya sabido (estilo médico) y pide el siguiente dato."""
    cultivo = (ctx.cultivo or '').strip()
    problema = (ctx.problema or '').strip()
    lugar_ok = bool((ctx.municipio or '').strip() or (ctx.region or '').strip())
    if cultivo and problema and lugar_ok:
        return (
            f'Entendido: {_cultivo_txt(ctx)} con {_sintoma_corto(ctx)} '
            f'en {_lugar_txt(ctx)}. {frase}'
        ).strip()
    if cultivo and problema:
        return f'Entendido: {_cultivo_txt(ctx)} con {_sintoma_corto(ctx)}. {frase}'.strip()
    if cultivo:
        return f'Perfecto, cultivo de {_cultivo_txt(ctx)}. {frase}'.strip()
    if problema:
        return f'Anoto lo que observa: {_sintoma_corto(ctx)}. {frase}'.strip()
    return frase


def _guardar_problema_desde_mensaje(ctx, mensaje: str) -> None:
    texto = (mensaje or '').strip()
    if len(texto) < 4:
        return
    low = _norm_msg(texto)
    if low in _ESCAPES_DIAGNOSTICO or low in _KEYWORDS_CURSOS or low in ('hola', 'primero clima'):
        return
    if re.match(r'^(hola|buenas|gracias)\b', low):
        return
    ctx.problema = texto[:200]
    ctx.save(update_fields=['problema', 'updated_at'])


def _respuesta_util(mensaje: str, *, min_len: int = 5) -> bool:
    texto = (mensaje or '').strip()
    if len(texto) < min_len:
        return False
    low = _norm_msg(texto)
    if low in _ESCAPES_DIAGNOSTICO or low in _KEYWORDS_CURSOS:
        return False
    if re.match(r'^(hola|buenas|gracias)\b', low):
        return False
    return True


def _capturar_si_responde(ctx, clave: str, mensaje: str, *, min_len: int = 5) -> bool:
    """Si el productor responde (no es solo un síntoma nuevo suelto), guarda en metadata."""
    meta = _get_meta(ctx)
    if meta.get(clave):
        return True
    if not meta.get(f'_pregunto_{clave}'):
        return False
    if not _respuesta_util(mensaje, min_len=min_len):
        return False
    # Evitar pisar con el mismo mensaje que activó el diagnóstico (síntoma inicial)
    if clave != 'extension_afectada' and es_consulta_diagnostico(mensaje) and len((mensaje or '').split()) < 6:
        return False
    meta[clave] = (mensaje or '').strip()[:200]
    if clave == 'manejo_previo':
        meta['fertilizacion_reciente'] = meta[clave]  # compat
    _set_meta(ctx, meta)
    return True


def _preguntar(ctx, clave: str, texto: str) -> str:
    meta = _get_meta(ctx)
    meta[f'_pregunto_{clave}'] = True
    _set_meta(ctx, meta)
    return texto


def anamnesis_clinica_completa(ctx) -> bool:
    meta = _get_meta(ctx)
    if meta.get('anamnesis_completa'):
        return True
    manejo = meta.get('manejo_previo') or meta.get('fertilizacion_reciente')
    return bool(
        meta.get('extension_afectada')
        and meta.get('tiempo_problema')
        and manejo
    )


def siguiente_pregunta_diagnostico(ctx, mensaje: str, *, tiene_imagen: bool = False) -> str | None:
    """
    Anamnesis clínica: una pregunta a la vez, personalizada con lo ya conocido.
    Devuelve None cuando ya puede pasar al criterio técnico (LLM + catálogo).
    """
    if not ctx:
        return None

    msg = _norm_msg(mensaje)
    meta0 = _get_meta(ctx)

    # Menú / reinicio: salir limpio (no dejar omit sticky).
    if msg in _ESCAPES_MENU:
        reiniciar_diagnostico(ctx)
        return None

    # Foto: solo omitir foto si ya se pidió; si no, "saltar" aborta toda la anamnesis.
    if msg in _ESCAPES_FOTO:
        meta = meta0
        if meta.get('pidio_foto') or meta.get('anamnesis_completa'):
            meta['foto_omitida'] = True
            _set_meta(ctx, meta)
            return None
        meta['foto_omitida'] = True
        meta['diagnostico_omitido'] = True
        _set_meta(ctx, meta)
        return None

    try:
        from core.clima_open_meteo import consulta_necesita_clima

        if consulta_necesita_clima(mensaje):
            meta_prev = _get_meta(ctx)
            # No abortar si estamos esperando respuesta de anamnesis
            # (p. ej. "solo riego, no fumigué" tras preguntar manejo previo).
            esperando = any(
                meta_prev.get(f'_pregunto_{k}') and not meta_prev.get(k)
                for k in ('extension_afectada', 'tiempo_problema', 'manejo_previo')
            ) or (
                meta_prev.get('_pregunto_etapa')
                and not (ctx.etapa or '').strip()
            )
            en_curso = bool(meta_prev.get('diagnostico_activo')) and not meta_prev.get(
                'diagnostico_omitido'
            )
            clima_explicito = bool(_CLIMA_EXPLICITO.search(mensaje or ''))
            ubicacion = (ctx.municipio or '').strip() or (ctx.region or '').strip()
            # Con anamnesis activa, riego/fumigar son respuestas clínicas salvo clima explícito.
            if ubicacion and not esperando and (not en_curso or clima_explicito):
                meta = meta_prev
                meta['diagnostico_omitido'] = True
                _set_meta(ctx, meta)
                return None
    except Exception:
        pass

    meta = _get_meta(ctx)
    if meta.get('diagnostico_omitido'):
        return None

    # Capturar respuestas pendientes antes de decidir la siguiente pregunta
    _capturar_si_responde(ctx, 'extension_afectada', mensaje, min_len=4)
    _capturar_si_responde(ctx, 'tiempo_problema', mensaje, min_len=4)
    _capturar_si_responde(ctx, 'manejo_previo', mensaje, min_len=3)
    if meta.get('_pregunto_etapa') and not (ctx.etapa or '').strip() and _respuesta_util(mensaje, min_len=3):
        if not es_consulta_diagnostico(mensaje) or len((mensaje or '').split()) >= 2:
            ctx.etapa = (mensaje or '').strip()[:80]
            ctx.save(update_fields=['etapa', 'updated_at'])
            meta = _get_meta(ctx)
            meta['etapa_consultada'] = True
            _set_meta(ctx, meta)

    meta = _get_meta(ctx)

    # Mínimo clínico + anamnesis + foto → listo para LLM
    if datos_suficientes(ctx) and anamnesis_clinica_completa(ctx):
        if meta.get('pidio_foto') or meta.get('foto_omitida') or tiene_imagen:
            return None
        meta['pidio_foto'] = True
        meta['anamnesis_completa'] = True
        _set_meta(ctx, meta)
        return _ack(
            ctx,
            'Para afinar el criterio como en una visita de campo: '
            '¿puede enviarme una foto de la zona afectada? '
            'Si no tiene, escriba *sin foto* o *saltar*.',
        )

    if not es_consulta_diagnostico(mensaje) and not meta.get('diagnostico_activo'):
        return None

    meta['diagnostico_activo'] = True
    _set_meta(ctx, meta)

    # 1. Cultivo
    if not (ctx.cultivo or '').strip():
        if (ctx.problema or '').strip():
            return (
                f'Veo que menciona {_sintoma_corto(ctx)}. '
                'Para orientarle bien: ¿en qué cultivo lo está observando?'
            )
        return (
            'Cuénteme como en consulta de campo: ¿qué cultivo tiene en el lote '
            'y qué es lo primero que le preocupa en las plantas?'
        )

    # 2. Ubicación
    if not (ctx.municipio or '').strip() and not (ctx.region or '').strip():
        return _ack(
            ctx,
            '¿En qué municipio y departamento está el lote? '
            'Si puede, agregue la vereda: el clima local cambia el criterio.',
        )

    # 3. Motivo / síntoma
    if not (ctx.problema or '').strip():
        if _respuesta_util(mensaje, min_len=4):
            _guardar_problema_desde_mensaje(ctx, mensaje)
            if (ctx.problema or '').strip():
                return siguiente_pregunta_diagnostico(ctx, mensaje, tiene_imagen=tiene_imagen)
        return _ack(
            ctx,
            f'En su {_cultivo_txt(ctx)} de {_lugar_txt(ctx)}, '
            '¿qué está viendo exactamente? '
            '(manchas, amarillamiento, marchitez, insectos, pudrición…)',
        )

    # 4. Dónde y cuánto (extensión)
    if not _get_meta(ctx).get('extension_afectada'):
        return _preguntar(
            ctx,
            'extension_afectada',
            _ack(
                ctx,
                f'Con {_sintoma_corto(ctx)} en {_cultivo_txt(ctx)}: '
                '¿en qué parte de la planta empezó (hojas, tallo, fruto, raíz) '
                'y aproximadamente qué tanto del lote está afectado?',
            ),
        )

    # 5. Tiempo / evolución
    if not _get_meta(ctx).get('tiempo_problema'):
        return _preguntar(
            ctx,
            'tiempo_problema',
            _ack(
                ctx,
                '¿Hace cuánto apareció y ha empeorado, se mantiene igual o mejoró un poco?',
            ),
        )

    # 6. Etapa fenológica
    if not (ctx.etapa or '').strip():
        return _preguntar(
            ctx,
            'etapa',
            _ack(
                ctx,
                f'¿En qué etapa va el {_cultivo_txt(ctx)}? '
                '(siembra, crecimiento, floración, llenado/fructificación, cosecha)',
            ),
        )

    # 7. Manejo previo (clave clínica — qué ya hizo)
    meta = _get_meta(ctx)
    if not (meta.get('manejo_previo') or meta.get('fertilizacion_reciente')):
        return _preguntar(
            ctx,
            'manejo_previo',
            _ack(
                ctx,
                'Última pregunta antes de orientarle: '
                '¿qué ha aplicado o hecho ya (fertilización, riego, fungicida, insecticida)? '
                'Si no ha aplicado nada, dígamelo igual.',
            ),
        )

    meta['anamnesis_completa'] = True
    _set_meta(ctx, meta)

    if tiene_imagen or meta.get('foto_omitida'):
        return None

    if not meta.get('pidio_foto'):
        meta['pidio_foto'] = True
        _set_meta(ctx, meta)
        return _ack(
            ctx,
            'Con ese cuadro ya puedo orientarle mejor. '
            '¿Puede enviarme una foto de la zona afectada? '
            'Si no tiene, escriba *sin foto* o *saltar*.',
        )

    return None
