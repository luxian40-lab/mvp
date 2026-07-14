"""Catálogo eki Studio: solo cursos con PublicacionStudio (marketplace de creadores)."""

from __future__ import annotations

from django.db.models import Count, Q

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def cursos_catalogo_studio(estudiante: Estudiante | None = None):
    """
    Catálogo marketplace: requiere PublicacionStudio + curso activo + publicado.
    No lista programas B2B solo por visible_en_studio (desacoplado de cursos live).
    """
    qs = (
        Curso.objects.filter(
            activo=True,
            visible_en_studio=True,
            publicacion_studio__isnull=False,
        )
        .filter(
            Q(publicacion_studio__creador__isnull=True)
            | Q(publicacion_studio__creador__activo=True)
        )
        .annotate(total_lecciones=Count('modulos'))
        .select_related('cliente', 'publicacion_studio', 'publicacion_studio__creador')
    )
    # Solo cursos generales (creador / eki). No mezclar catálogo org B2B.
    qs = qs.filter(cliente__isnull=True)
    return qs.order_by('-publicacion_studio__destacado', 'orden', 'nombre')


def ids_cursos_inscritos(estudiante: Estudiante) -> set[int]:
    return set(
        ProgresoEstudiante.objects.filter(estudiante=estudiante)
        .values_list('curso_id', flat=True)
    )


def curso_disponible_en_studio(estudiante: Estudiante | None, curso_id: int) -> Curso | None:
    return cursos_catalogo_studio(estudiante).filter(pk=curso_id).first()


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
