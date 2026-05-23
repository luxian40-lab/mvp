"""
Integración con el flujo de cursos: inicio del formulario al completar un módulo
configurado (TipoFormulario con el mismo módulo como «disparador»).
"""
from __future__ import annotations

import logging

from django.db.models import Q

from .agent import iniciar_sesion_formulario
from .models import SesionFormulario, TipoFormulario

logger = logging.getLogger(__name__)


def intentar_iniciar_formulario_al_completar_modulo(estudiante, progreso, modulo_completado, modulo_siguiente) -> str | None:
    """
    Si existe un TipoFormulario activo cuyo módulo disparador es `modulo_completado`
    (y el curso coincide), inicia la sesión y devuelve el primer mensaje.

    Prioridad: TipoFormulario con `cliente` específico del estudiante gana sobre
    el TipoFormulario global (`cliente__isnull=True`). Esto permite que un cliente
    (p. ej. Nitrofert) tenga su propio formulario para el mismo curso/módulo, mientras
    que otros clientes (p. ej. TechnoServe) usen el global o ninguno.

    En ese caso el avance a `modulo_siguiente` en `progreso` queda en pausa
    hasta que `manejar_mensaje_formulario` cierre la sesión.

    Returns:
        str para enviar al usuario, o None si no aplica formulario.
    """
    if not progreso or not modulo_completado:
        return None

    # Balance GEI en el último módulo: no hay modulo_siguiente pero sí debe dispararse.

    # Toggle por curso: el operador puede desactivar el formulario GEI desde
    # Admin → Cursos sin tener que editar TipoFormulario.
    curso = getattr(progreso, "curso", None)
    if curso is not None and not getattr(curso, "tiene_formulario_gei", True):
        logger.debug(
            "Curso %s tiene tiene_formulario_gei=False; no se dispara formulario.",
            getattr(curso, "id", "?"),
        )
        return None

    cliente_id = getattr(estudiante, "cliente_id", None)
    qs = TipoFormulario.objects.filter(
        curso_id=progreso.curso_id,
        modulo_id=modulo_completado.id,
        activo=True,
    )
    if cliente_id:
        qs = qs.filter(Q(cliente_id=cliente_id) | Q(cliente__isnull=True))
    else:
        qs = qs.filter(cliente__isnull=True)

    tf = qs.order_by("-cliente_id", "id").first()
    if not tf:
        logger.info(
            "GEI: sin TipoFormulario activo curso=%s modulo=%s cliente=%s",
            progreso.curso_id,
            modulo_completado.id,
            cliente_id,
        )
        return None

    if not tf.flujo_pasos.exists():
        logger.warning("TipoFormulario %s sin FlujoPregunta; no se inicia sesión.", tf.id)
        return None

    if SesionFormulario.objects.filter(estudiante=estudiante, formulario=tf, completado=False).exists():
        return None

    return iniciar_sesion_formulario(
        estudiante,
        tf,
        progreso=progreso,
        modulo_siguiente=modulo_siguiente,
    )
