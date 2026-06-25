"""Catálogo e inscripción de cursos en el aula web (estilo Platzi)."""

from __future__ import annotations

from django.db.models import Count, Q

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def cursos_catalogo_aula(estudiante: Estudiante):
    """
    Cursos que el estudiante puede elegir en /aprende/:
    - De su organización (cliente)
    - Generales eki (sin cliente específico)
  """
    qs = Curso.objects.filter(activo=True, visible_en_aula=True).annotate(
        total_lecciones=Count('modulos'),
    )
    org_id = getattr(estudiante, 'cliente_id', None)
    if org_id:
        qs = qs.filter(Q(cliente_id=org_id) | Q(cliente__isnull=True))
    else:
        qs = qs.filter(cliente__isnull=True)
    return qs.order_by('orden', 'nombre')


def ids_cursos_inscritos(estudiante: Estudiante) -> set[int]:
    return set(
        ProgresoEstudiante.objects.filter(estudiante=estudiante)
        .values_list('curso_id', flat=True)
    )


def curso_disponible_para_estudiante(estudiante: Estudiante, curso_id: int) -> Curso | None:
    return cursos_catalogo_aula(estudiante).filter(pk=curso_id).first()


def inscribir_estudiante_en_curso(estudiante: Estudiante, curso: Curso) -> ProgresoEstudiante:
    """Crea o retoma progreso en un curso del catálogo aula."""
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
