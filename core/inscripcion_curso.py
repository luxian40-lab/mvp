"""Inscripción de estudiante a curso con defaults seguros para Aprende."""

from __future__ import annotations

import re
import unicodedata

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def _norm_nombre_curso(s: str) -> str:
    """Compara nombres ignorando guiones tipográficos, NBSP y espacios raros."""
    t = (s or '').replace('\u00a0', ' ').strip()
    for ch in ('\u2014', '\u2013', '\u2212', '\u2012', '—', '–'):
        t = t.replace(ch, '-')
    t = unicodedata.normalize('NFKC', t)
    t = re.sub(r'\s+', ' ', t)
    return t.casefold()


def resolver_curso_por_nombre(
    nombre: str,
    *,
    cliente_nombre: str | None = None,
) -> Curso | None:
    """
    Busca curso por nombre exacto (case-insensitive) o normalizado
    (guión Excel vs em dash / mojibake en DB). Opcionalmente acota por cliente.
    """
    raw = (nombre or '').strip()
    if not raw:
        return None
    qs = Curso.objects.filter(activo=True).select_related('cliente')
    if cliente_nombre:
        qs = qs.filter(cliente__nombre__iexact=cliente_nombre.strip())

    hit = qs.filter(nombre__iexact=raw).first()
    if hit:
        return hit

    target = _norm_nombre_curso(raw)
    for c in qs.iterator():
        if _norm_nombre_curso(c.nombre) == target:
            return c
        # Mojibake típico UTF-8 em-dash leído como Latin-1: â€"
        if 'clases' in target and 'aprende' in target:
            cn = (c.nombre or '').casefold()
            if 'clases' in cn and 'aprende' in cn:
                return c

    # Clases Aprende / Capital humano 10x: un curso modo clases por cliente.
    if (
        ('clases' in target and 'aprende' in target)
        or 'capital humano' in target
        or ('10x' in target and 'cenipalma' in target)
    ):
        hit = qs.filter(modo_aula=Curso.MODO_AULA_CLASES).order_by('id').last()
        if hit:
            return hit
        if not cliente_nombre:
            return (
                Curso.objects.filter(
                    activo=True,
                    modo_aula=Curso.MODO_AULA_CLASES,
                    cliente__nombre__iexact='Cenipalma',
                )
                .order_by('id')
                .last()
            )
    return None


def primer_modulo_curso(curso: Curso) -> Modulo | None:
    return (
        Modulo.objects.filter(curso=curso)
        .order_by('numero', 'id')
        .first()
    )


def defaults_progreso_nuevo(curso: Curso) -> dict:
    """Defaults al crear ProgresoEstudiante (sin campo inventado `progreso`)."""
    defaults = {'completado': False}
    m1 = primer_modulo_curso(curso)
    if m1 is not None:
        defaults['modulo_actual'] = m1
    return defaults


def inscribir_estudiante_en_curso(
    estudiante: Estudiante,
    curso: Curso,
    *,
    asegurar_modulo_actual: bool = True,
) -> tuple[ProgresoEstudiante, bool]:
    """
    get_or_create de progreso. Si se crea, asigna modulo_actual = 1er módulo.
    Si ya existía y asegurar_modulo_actual y no tiene módulo, lo completa.
    """
    progreso, creado = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        defaults=defaults_progreso_nuevo(curso),
    )
    if (
        asegurar_modulo_actual
        and not creado
        and progreso.modulo_actual_id is None
        and not progreso.completado
    ):
        m1 = primer_modulo_curso(curso)
        if m1 is not None:
            progreso.modulo_actual = m1
            progreso.save(update_fields=['modulo_actual'])
    return progreso, creado
