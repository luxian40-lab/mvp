"""Catálogo e inscripción en eki Studio (marketplace / explorar cursos)."""

from __future__ import annotations

from django.db.models import Count, Q

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def cursos_catalogo_studio(estudiante: Estudiante | None = None):
    """
    Cursos publicados en Studio.
    Con estudiante: de su organización + generales eki.
    Sin sesión: solo generales eki (cliente null).
    """
    qs = Curso.objects.filter(activo=True, visible_en_studio=True).annotate(
        total_lecciones=Count('modulos'),
    )
    if estudiante and estudiante.cliente_id:
        qs = qs.filter(Q(cliente_id=estudiante.cliente_id) | Q(cliente__isnull=True))
    elif estudiante:
        pass
    else:
        qs = qs.filter(cliente__isnull=True)
    return qs.order_by('orden', 'nombre')


def ids_cursos_inscritos(estudiante: Estudiante) -> set[int]:
    return set(
        ProgresoEstudiante.objects.filter(estudiante=estudiante)
        .values_list('curso_id', flat=True)
    )


def curso_disponible_en_studio(estudiante: Estudiante | None, curso_id: int) -> Curso | None:
    if estudiante:
        return cursos_catalogo_studio(estudiante).filter(pk=curso_id).first()
    return cursos_catalogo_studio(None).filter(pk=curso_id).first()


def inscribir_estudiante_en_curso(estudiante: Estudiante, curso: Curso) -> ProgresoEstudiante:
    primer_modulo = Modulo.objects.filter(curso=curso).order_by('numero').first()
    progreso, creado = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        defaults={'completado': False, 'modulo_actual': primer_modulo},
    )
    if not creado and not progreso.modulo_actual and primer_modulo:
        progreso.modulo_actual = primer_modulo
        progreso.save(update_fields=['modulo_actual'])
    return progreso
