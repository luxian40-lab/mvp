"""Pasos internos por módulo (entrega progresiva por WhatsApp)."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Estudiante, Modulo, PasoModulo, ProgresoEstudiante

logger = logging.getLogger(__name__)


def pasos_activos_qs(modulo: Modulo):
    from .models import PasoModulo

    return PasoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')


def modulo_tiene_pasos_activos(modulo: Optional[Modulo]) -> bool:
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
    partes = [formatear_texto_paso(paso, curso)]
    url = (paso.media_url or '').strip()
    hay_media = False
    if url:
        partes.append(f"[MEDIA:{url}]")
        hay_media = True
    if hay_media:
        partes.append("[DELAY:5]")
    return partes


def unir_multimsg(partes: list[str]) -> str:
    return "[MULTI_MSG]" + "[SEP]".join(p for p in partes if p)


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
        progreso.esperando_respuesta_evaluacion_paso = True
        progreso.paso_evaluacion_paso = paso
        progreso.save(
            update_fields=[
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
