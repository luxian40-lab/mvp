"""Qué módulos y tareas ve el estudiante en /aprende/ (misma lógica drip que WhatsApp)."""

from __future__ import annotations

from core.drip_schedule import (
    drip_bloquea_siguiente_modulo,
    max_modulo_alcanzado,
    modulo_disponible_por_calendario,
)
from core.models import Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante

from .models import TareaCurso


def _oculto_por_drip_entre_modulos(progreso: ProgresoEstudiante | None, modulo: Modulo) -> bool:
    """True si el módulo anterior ya está completo pero el drip aún no libera el siguiente."""
    if progreso is None:
        return False
    prev = (
        Modulo.objects.filter(curso=modulo.curso_id, numero__lt=modulo.numero)
        .order_by('-numero')
        .first()
    )
    if not prev:
        return False
    if not ModuloCompletado.objects.filter(progreso=progreso, modulo=prev).exists():
        return False
    return drip_bloquea_siguiente_modulo(progreso, prev)


def modulos_visibles_aula(
    estudiante: Estudiante,
    curso: Curso,
    progreso: ProgresoEstudiante | None = None,
) -> list[Modulo]:
    """
    Módulos visibles en el aula web:
    - Lista blanca / calendario (admin drip) vía modulo_disponible_por_calendario.
    - Sin lista blanca: solo hasta el avance alcanzado (como el flujo lineal por WA).
    """
    if progreso is None:
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=estudiante, curso=curso,
        ).first()

    cliente = getattr(estudiante, 'cliente', None)
    lista_explicita = bool(
        cliente and getattr(cliente, 'drip_modulos_solo_estudiantes_listados', False)
    )
    tope_avance = max_modulo_alcanzado(progreso) if progreso else 0
    # Curso C / 10x: todas las clases visibles (Biblioteca = hub; sin *listo*).
    liberar_todas = bool(getattr(curso, 'es_modo_clases', lambda: False)())

    visibles: list[Modulo] = []
    for modulo in Modulo.objects.filter(curso=curso).order_by('numero'):
        if not modulo_disponible_por_calendario(estudiante, modulo):
            continue
        if not liberar_todas:
            if not lista_explicita and modulo.numero > tope_avance:
                continue
            if _oculto_por_drip_entre_modulos(progreso, modulo):
                continue
        visibles.append(modulo)
    return visibles


def modulo_accesible_aula(
    estudiante: Estudiante,
    modulo: Modulo,
    progreso: ProgresoEstudiante | None = None,
) -> bool:
    if progreso is None:
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=estudiante, curso=modulo.curso,
        ).first()
    ids = {m.pk for m in modulos_visibles_aula(estudiante, modulo.curso, progreso)}
    return modulo.pk in ids


def tareas_visibles_aula(
    estudiante: Estudiante,
    curso: Curso,
    progreso: ProgresoEstudiante | None = None,
) -> list[TareaCurso]:
    """Tareas del curso cuyo módulo vinculado (si hay) está liberado para el estudiante."""
    mod_ids = {m.pk for m in modulos_visibles_aula(estudiante, curso, progreso)}
    tareas = TareaCurso.objects.filter(curso=curso, activa=True).select_related('modulo')
    out: list[TareaCurso] = []
    for t in tareas:
        if t.modulo_id and t.modulo_id not in mod_ids:
            continue
        out.append(t)
    return out
