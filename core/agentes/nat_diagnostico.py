"""Modo diagnóstico agronómico — anamnesis tipo consulta de campo (estilo médico).

Nati pregunta como agrónoma real: escucha → resume lo que entendió → pide el
dato crítico que falta, personalizado al cultivo/región/síntoma ya conocidos.
"""

from __future__ import annotations

import re
import unicodedata

_PATRON_SINTOMA = re.compile(
    r'\b(mancha|manchas|plaga|plagas|enfermedad|seco|seca|amarill\w*|caíd\w*|caid\w*|'
    r'marchit|roya|gusano|hongos?|problema|daño|dano|síntoma|sintoma|'
    r'no crece|se muere|se están muriendo|muriendo|mueren|'
    r'tengo unas|débil|debil|'
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
# Cómo hacer / desde cero. No es una planta enferma.
_ORIENTACION = re.compile(
    r'\b('
    r'desde\s+cero|'
    r'c[oó]mo\s+(se\s+)?(hago|hacer|cultivo|cultivar|siembro|sembrar|preparo|preparar|'
    r'evito|evitar|empiezo|empezar|inicio|iniciar|aprendo|aprender)|'
    r'quiero\s+(aprender|empezar|iniciar|sembrar|cultivar|arrancar)|'
    r'para\s+empezar|'
    r'qu[eé]\s+hago|'
    r'qu[eé]\s+(puedo|debo)\s+hacer'
    r')\b',
    re.I,
)
# "cómo evitar plagas" es prevención. "ya veo manchas" es daño presente.
_PREVENCION = re.compile(
    r'\b(evitar|evito|prevenir|prevenga|para que no|que no haya|que no salga)\b',
    re.I,
)
_PRESENTE = re.compile(
    r'\b(tengo|veo|vi|hay|salieron|apareci[oó]|aparecieron|est[aá]n|est[aá]|'
    r'le\s+dio|se\s+ven|se\s+est[aá]n)\b',
    re.I,
)
# Otra pregunta, distinta de la planta enferma: no llena el casillero clínico.
_OTRA_COSA = re.compile(
    r'\b(precio|cu[aá]nto\s+vale|cu[aá]nto\s+cuesta|vender|venta|curso|aula|diploma)\b',
    re.I,
)
_SOLO_SALUDO = re.compile(
    r'^(hola|buenas|buenos dias|buen dia|buenas tardes|buenas noches|hey|que tal)\b',
    re.I,
)

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
                'diagnostico_en_pausa',
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


def es_orientacion(mensaje: str) -> bool:
    """Cómo hacer algo, o arrancar desde cero. No describe una planta ya enferma."""
    return bool(_ORIENTACION.search(mensaje or ''))


def es_otra_pregunta(mensaje: str) -> bool:
    """Precio, venta o curso. *continuar curso* sigue siendo palabra del guion."""
    if _norm_msg(mensaje) in _KEYWORDS_CURSOS:
        return False
    return bool(_OTRA_COSA.search(mensaje or ''))


def _sin_tildes(texto: str) -> str:
    t = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in t if not unicodedata.combining(c))


def mensaje_es_solo_saludo(mensaje: str) -> bool:
    """Hola suelto. Si atrás viene la pregunta, no se queda en el saludo."""
    t = _sin_tildes(_norm_msg(mensaje))
    if not t or not _SOLO_SALUDO.match(t):
        return False
    if es_orientacion(mensaje) or dano_presente(mensaje) or es_otra_pregunta(mensaje):
        return False
    return len(t.split()) <= 4


def dano_presente(mensaje: str) -> bool:
    """Daño que está pasando. Prevenir, o la palabra «problema» suelta, no alcanza."""
    if not es_consulta_diagnostico(mensaje):
        return False
    if es_orientacion(mensaje) and not _PRESENTE.search(mensaje or ''):
        sin_generico = re.sub(r'\bproblemas?\b', ' ', mensaje or '', flags=re.I)
        if not _PATRON_SINTOMA.search(sin_generico):
            return False
        if _PREVENCION.search(mensaje or ''):
            return False
    elif es_orientacion(mensaje) and _PREVENCION.search(mensaje or '') and not _PRESENTE.search(mensaje or ''):
        return False
    return True


def _consulta_abierta(meta: dict) -> bool:
    return bool(meta.get('diagnostico_activo')) and not meta.get('diagnostico_omitido')


def _poner_pausa(ctx) -> None:
    meta = _get_meta(ctx)
    if meta.get('diagnostico_en_pausa'):
        return
    meta['diagnostico_en_pausa'] = True
    _set_meta(ctx, meta)


def _quitar_pausa(ctx) -> None:
    meta = _get_meta(ctx)
    if not meta.get('diagnostico_en_pausa'):
        return
    meta.pop('diagnostico_en_pausa', None)
    _set_meta(ctx, meta)


def frase_que_oyo(ctx, mensaje: str) -> str:
    """Una línea de lo oído. No inventa un daño que el mensaje no trae."""
    cultivo = ((getattr(ctx, 'cultivo', None) or '') if ctx else '').strip()
    if es_orientacion(mensaje) and not dano_presente(mensaje):
        if cultivo and _PREVENCION.search(mensaje or ''):
            return f'Entendí que quiere saber cómo cuidar {cultivo} y prevenir problemas.'
        if cultivo:
            return f'Entendí que quiere saber cómo arrancar {cultivo}.'
        return 'Entendí que quiere saber cómo hacerlo desde el inicio.'
    if dano_presente(mensaje) and cultivo:
        corto = _sintoma_corto(ctx) if (getattr(ctx, 'problema', None) or '').strip() else 'un daño'
        return f'Entendí que en {cultivo} ve {corto}.'
    if cultivo:
        return f'Entendí que habla de {cultivo}.'
    return 'Entendí lo que me cuenta.'


def anteponer_entendio(ctx, mensaje: str, texto: str) -> str:
    """La frase va arriba del mismo mensaje. No es otro envío ni otro cupo."""
    cuerpo = (texto or '').strip()
    if not cuerpo or cuerpo.startswith('Entendí'):
        return cuerpo
    return f'{frase_que_oyo(ctx, mensaje)}\n\n{cuerpo}'


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
    """Etiqueta corta de síntoma; evita ecoear frases largas o pedidos de ayuda."""
    p = (ctx.problema or '').strip()
    if not p:
        return 'lo que describe'
    low = p.lower()
    # Pedidos tipo "qué podemos hacer" no son el síntoma
    if any(
        x in low
        for x in (
            'podemos', 'qué hacer', 'que hacer', 'que hago', 'ayuda',
            'cómo', 'como ', 'recomien', 'qué me', 'que me',
        )
    ):
        m = _PATRON_SINTOMA.search(p)
        if m:
            start = max(0, m.start() - 2)
            end = min(len(p), m.end() + 12)
            chunk = re.sub(r'\s+', ' ', p[start:end]).strip(' ,.;:')
            if chunk:
                return chunk[:40]
        return 'lo que describe'
    if len(p) <= 40:
        return p
    return p[:37] + '…'


def _ack(ctx, frase: str) -> str:
    """La pregunta, dicha. Sin rótulo «En café (Este):»."""
    frase = (frase or '').strip()
    if not frase:
        return ''
    i = 0
    while i < len(frase) and frase[i] in '¿¡':
        i += 1
    if i < len(frase) and frase[i].islower():
        frase = frase[:i] + frase[i].upper() + frase[i + 1:]
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
            # En pausa el clima lo responde el criterio. No cerrar la consulta.
            if meta_prev.get('diagnostico_en_pausa'):
                return None
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

    # Cómo / desde cero, sin daño presente: no es consulta clínica.
    # Pausa el guion. No lo borra: un daño después lo reabre.
    if (
        (es_orientacion(mensaje) or es_otra_pregunta(mensaje))
        and not dano_presente(mensaje)
        and not tiene_imagen
    ):
        _poner_pausa(ctx)
        return None

    if meta.get('diagnostico_en_pausa') and not dano_presente(mensaje) and not tiene_imagen:
        return None

    if dano_presente(mensaje) or tiene_imagen:
        _quitar_pausa(ctx)

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
            f'En su {_cultivo_txt(ctx)}, ¿en qué parte de la planta empezó '
            '(hojas, tallo, fruto, raíz) y qué tanto del lote está afectado?',
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
