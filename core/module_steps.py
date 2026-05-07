"""Pasos internos por módulo (entrega progresiva por WhatsApp)."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Estudiante, Modulo, PasoModulo, ProgresoEstudiante

logger = logging.getLogger(__name__)

# Mensaje al estudiante si modo "pasos" quedó mal configurado (sin filas PasoModulo activas).
FALLBACK_MODULO_PASOS_SIN_PASOS = (
    '📚 Estamos organizando el contenido de esta unidad. '
    'Intentá de nuevo en unos minutos o escribí *menú* para ver opciones.'
)


def modulo_usa_pasos(modulo: Optional[Modulo]) -> bool:
    """
    True si el flujo WhatsApp debe usar pasos internos (PasoModulo).
    - modo 'pasos'  → True aunque no haya pasos (el operador debe corregir; ver fallback).
    - modo 'legacy' → False aunque existan pasos en BD
    - modo 'auto'   → True solo si hay al menos un PasoModulo activo
    """
    if not modulo:
        return False
    from .models import Modulo

    modo = getattr(modulo, 'modo_entrega', None) or Modulo.MODO_ENTREGA_AUTO
    if modo == Modulo.MODO_ENTREGA_PASOS:
        return True
    if modo == Modulo.MODO_ENTREGA_LEGACY:
        return False
    return pasos_activos_qs(modulo).exists()


def log_y_mensaje_modo_pasos_sin_pasos(modulo: Modulo, contexto: str) -> str:
    """Log operativo 🔧; devuelve texto seguro para el estudiante."""
    logger.warning(
        '🔧 [pasos] modo_entrega=pasos sin pasos activos | modulo_id=%s ctx=%s',
        modulo.id,
        contexto,
    )
    return FALLBACK_MODULO_PASOS_SIN_PASOS


def pasos_activos_qs(modulo: Modulo):
    from .models import PasoModulo

    return (
        PasoModulo.objects.filter(modulo=modulo, activo=True, seccion__activa=True)
        .select_related('seccion')
        .order_by('orden', 'id')
    )


def modulo_tiene_pasos_activos(modulo: Optional[Modulo]) -> bool:
    """True si hay al menos un PasoModulo activo en BD (no usa modo_entrega)."""
    if not modulo:
        return False
    return pasos_activos_qs(modulo).exists()


def reset_progreso_pasos_modulo(progreso: ProgresoEstudiante, save: bool = True) -> None:
    progreso.paso_actual_modulo = 1
    progreso.esperando_respuesta_evaluacion_paso = False
    progreso.paso_evaluacion_paso = None
    if save:
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )


def _letra_correcta_eval_opciones(paso: PasoModulo) -> str:
    from .models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_EVAL_OPC:
        return ''
    if paso.respuesta_correcta:
        return str(paso.respuesta_correcta).strip().upper()[:1]
    data = paso.opciones_json or {}
    c = data.get('correcta') if isinstance(data, dict) else None
    if c is None and isinstance(data, dict):
        c = data.get('respuesta_correcta')
    if c is None:
        return ''
    return str(c).strip().upper()[:1]


def formatear_texto_paso(paso: PasoModulo, curso) -> str:
    from .models import PasoModulo

    header = f"📌 *{paso.titulo}*\n\n"
    body = (paso.contenido or '').strip()
    msg = header + body if body else header.rstrip()
    if paso.tipo == PasoModulo.TIPO_EVAL_OPC:
        data = paso.opciones_json or {}
        opts = []
        if isinstance(data, dict):
            for key in ('A', 'B', 'C', 'D'):
                val = data.get(key)
                if val:
                    opts.append(f"*{key}*) {val}")
        if opts:
            msg = msg + "\n\n" + "\n".join(opts)
        msg += "\n\nResponde con la letra (ej: *A*)."
    elif paso.tipo == PasoModulo.TIPO_EVAL_ABIERTA:
        msg += "\n\n✍️ Envía tu respuesta en un mensaje."
    elif paso.tipo in (PasoModulo.TIPO_RETO, PasoModulo.TIPO_ENTREGA):
        msg += "\n\n📎 Envía tu respuesta o escribe *listo* cuando termines."
    return msg.strip()


def partes_mensaje_paso(paso: PasoModulo, curso) -> list[str]:
    """
    Bloques para MULTI_MSG. Si hay media_url, va en el mismo bloque que el texto
    para que Twilio envíe cuerpo + adjunto juntos (evita mensajes “vacíos” solo con media).
    """
    base = formatear_texto_paso(paso, curso)
    url = (paso.media_url or '').strip()
    if url:
        return [f'{base}\n\n[MEDIA:{url}]', '[DELAY:5]']
    return [base]


def unir_multimsg(partes: list[str]) -> str:
    return "[MULTI_MSG]" + "[SEP]".join(p for p in partes if p)


def _ids_secciones_activas_ordenadas(modulo: Modulo) -> list[int]:
    from .models import SeccionModulo

    return list(
        SeccionModulo.objects.filter(modulo=modulo, activa=True)
        .order_by('orden', 'id')
        .values_list('id', flat=True)
    )


def _batch_pasos_desde_indice(modulo: Modulo, qs: list, idx: int) -> list:
    """
    idx en 1..len(qs). Hasta secciones_por_listo secciones consecutivas (por orden de sección),
    en orden de paso. Corta después del primer paso de evaluación incluido en el recorrido.
    """
    if idx < 1 or idx > len(qs):
        return []
    k_raw = getattr(modulo, 'secciones_por_listo', None)
    try:
        k = int(k_raw)
    except (TypeError, ValueError):
        k = 1
    k = max(1, min(k, 5))
    sec_order = _ids_secciones_activas_ordenadas(modulo)
    start = qs[idx - 1]
    try:
        i0 = sec_order.index(start.seccion_id)
    except ValueError:
        return [start]
    allowed_sec = set(sec_order[i0 : i0 + k])
    batch = []
    for p in qs[idx - 1 :]:
        if p.seccion_id not in allowed_sec:
            break
        batch.append(p)
        if p.es_evaluacion:
            break
    return batch


def entregar_bloque_secciones_desde_paso(
    progreso: ProgresoEstudiante, modulo: Modulo, idx: int
) -> str:
    """Entrega hasta N secciones (secciones_por_listo) desde el paso idx, con títulos de sección."""
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    batch = _batch_pasos_desde_indice(modulo, qs, idx)
    if not batch:
        raise ValueError('índice de paso fuera de rango o batch vacío')
    curso = progreso.curso
    partes: list[str] = []
    last_sec_id = None
    for paso in batch:
        if paso.seccion_id != last_sec_id:
            last_sec_id = paso.seccion_id
            tit = ((paso.seccion.titulo or '') if paso.seccion_id else '').strip()
            if tit:
                partes.append(f'📑 *{tit}*\n')
        partes.extend(partes_mensaje_paso(paso, curso))
    last_paso = batch[-1]
    last_idx = qs.index(last_paso) + 1

    if last_paso.es_evaluacion:
        progreso.esperando_respuesta_evaluacion_paso = True
        progreso.paso_evaluacion_paso = last_paso
        progreso.paso_actual_modulo = last_idx
        progreso.save(
            update_fields=[
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
                'paso_actual_modulo',
            ]
        )
        logger.info(
            "📚 [pasos] evaluación paso (bloque) | estudiante_id=%s progreso_id=%s paso_id=%s idx=%s",
            progreso.estudiante_id,
            progreso.id,
            last_paso.id,
            last_idx,
        )
    else:
        progreso.paso_actual_modulo = last_idx + 1
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        if progreso.paso_actual_modulo <= n:
            partes.append(
                'Cuando termines de revisar, escribe *listo* para continuar 👇'
            )
        logger.info(
            "📚 [pasos] bloque entregado | estudiante_id=%s progreso_id=%s último_paso_id=%s nuevo_idx=%s n_pasos=%s",
            progreso.estudiante_id,
            progreso.id,
            last_paso.id,
            progreso.paso_actual_modulo,
            n,
        )
    return unir_multimsg(partes)


def entregar_paso_indice(progreso: ProgresoEstudiante, modulo: Modulo, idx: int) -> str:
    """Entrega el paso en posición idx (1-based) y actualiza progreso."""
    from .models import PasoModulo

    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    if idx < 1 or idx > n:
        raise ValueError('índice de paso fuera de rango')
    paso = qs[idx - 1]
    curso = progreso.curso
    partes = partes_mensaje_paso(paso, curso)
    if paso.es_evaluacion:
        progreso.paso_actual_modulo = idx
        progreso.esperando_respuesta_evaluacion_paso = True
        progreso.paso_evaluacion_paso = paso
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        logger.info(
            "📚 [pasos] evaluación paso | estudiante_id=%s progreso_id=%s paso_id=%s idx=%s",
            progreso.estudiante_id,
            progreso.id,
            paso.id,
            idx,
        )
    else:
        progreso.paso_actual_modulo = idx + 1
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        if progreso.paso_actual_modulo <= n:
            partes.append("Cuando termines de revisar, escribe *listo* para continuar 👇")
        logger.info(
            "📚 [pasos] contenido entregado | estudiante_id=%s progreso_id=%s paso_id=%s nuevo_idx=%s",
            progreso.estudiante_id,
            progreso.id,
            paso.id,
            progreso.paso_actual_modulo,
        )
    return unir_multimsg(partes)


def mensaje_recordatorio_paso_actual(progreso: ProgresoEstudiante, modulo: Modulo) -> Optional[str]:
    """Para *continuar*: reenvía el paso en curso sin avanzar índices."""
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    if n == 0:
        return None
    if progreso.esperando_respuesta_evaluacion_paso and progreso.paso_evaluacion_paso_id:
        paso = progreso.paso_evaluacion_paso
        idx = progreso.paso_actual_modulo
    else:
        idx = progreso.paso_actual_modulo
        if idx > n:
            return None
        if idx < 1:
            idx = 1
        paso = qs[idx - 1]
    partes = partes_mensaje_paso(paso, progreso.curso)
    partes.append(
        "Cuando estés listo, escribe *listo* para el siguiente material o responde la actividad 👇"
    )
    return unir_multimsg(partes)


def procesar_respuesta_evaluacion_paso(
    estudiante: Estudiante,
    progreso: ProgresoEstudiante,
    texto_crudo: str,
) -> Optional[str]:
    """
    Si está esperando evaluación de paso, evalúa y devuelve MULTI_MSG o str.
    Si no aplica, devuelve None.
    """
    if not progreso.esperando_respuesta_evaluacion_paso or not progreso.paso_evaluacion_paso_id:
        return None
    paso = progreso.paso_evaluacion_paso
    modulo = progreso.modulo_actual
    if not modulo or paso.modulo_id != modulo.id:
        logger.warning(
            "⚠️ [pasos] paso eval fuera de módulo actual | est=%s progreso=%s",
            estudiante.id,
            progreso.id,
        )
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        return None

    from .models import PasoModulo

    texto = (texto_crudo or '').strip()
    idx = progreso.paso_actual_modulo
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)

    ok = False
    if paso.tipo == PasoModulo.TIPO_EVAL_OPC:
        letra_in = re.sub(r'[^a-dA-D]', '', texto)
        letra_in = (letra_in[:1] or '').upper()
        ok = bool(letra_in) and letra_in == _letra_correcta_eval_opciones(paso)
    elif paso.tipo == PasoModulo.TIPO_EVAL_ABIERTA:
        ok = bool(texto)
    elif paso.tipo in (PasoModulo.TIPO_RETO, PasoModulo.TIPO_ENTREGA):
        raw = (texto_crudo or '').strip().lower()
        ok = bool(texto) or raw in ('listo', 'lista', 'ok', 'sí', 'si')
    else:
        ok = bool(texto)

    if not ok:
        fb = (paso.feedback_incorrecto or '').strip() or (
            "❌ No es correcto. Revisa el material y vuelve a intentar."
        )
        logger.info(
            "📚 [pasos] eval incorrecta | est=%s paso_id=%s",
            estudiante.id,
            paso.id,
        )
        return fb

    fb_ok = (paso.feedback_correcto or '').strip() or "✅ ¡Muy bien! Seguimos."
    progreso.esperando_respuesta_evaluacion_paso = False
    progreso.paso_evaluacion_paso = None
    progreso.paso_actual_modulo = idx + 1
    progreso.save(
        update_fields=[
            'esperando_respuesta_evaluacion_paso',
            'paso_evaluacion_paso',
            'paso_actual_modulo',
        ]
    )
    logger.info(
        "📚 [pasos] eval correcta | est=%s paso_id=%s nuevo_idx=%s n_pasos=%s",
        estudiante.id,
        paso.id,
        progreso.paso_actual_modulo,
        n,
    )

    if progreso.paso_actual_modulo > n:
        from .response_templates import get_response_for_intent

        tail = get_response_for_intent(
            'continuar_leccion',
            estudiante.nombre or 'Estudiante',
            estudiante_id=estudiante.id,
            mensaje_original='listo',
            _saltar_bloque_pasos_internos=True,
        )
        if tail and tail.startswith('[MULTI_MSG]'):
            resto = tail[len('[MULTI_MSG]') :].split('[SEP]')
            return unir_multimsg([fb_ok] + [p for p in resto if p])
        partes = [fb_ok]
        if tail:
            partes.append(tail)
        return unir_multimsg(partes)

    partes = [fb_ok, "Escribe *listo* para recibir el siguiente material 👇"]
    return unir_multimsg(partes)
