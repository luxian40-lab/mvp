"""Lista de aceptantes de un curso, una página a la vez.

La tabla de métricas no carga nombres. Esta consulta es de un curso y de
una organización, con la persona y el módulo actual ya unidos.
"""
from __future__ import annotations

from django.core.paginator import Paginator

from core.models import Curso, ModuloCompletado, ProgresoEstudiante

POR_PAGINA = 50


def curso_de_la_org(org, curso_id):
    """Curso propio, o curso general con al menos un aceptante de la organización."""
    curso = Curso.objects.filter(pk=curso_id).first()
    if curso is None:
        return None
    if curso.cliente_id == org.id:
        return curso
    if curso.cliente_id is not None:
        return None
    tiene_gente = ProgresoEstudiante.objects.filter(
        curso=curso,
        estudiante__cliente=org,
        estudiante__activo=True,
    ).exists()
    return curso if tiene_gente else None


def _estado(progreso, cerro_modulo: bool) -> str:
    if progreso.completado:
        return 'Terminó'
    empezo = (progreso.paso_actual_modulo or 1) > 1 or cerro_modulo or bool(progreso.modulo_actual_id)
    return 'Empezó' if empezo else 'Sin empezar'


def inscritos_curso(org, curso, *, q='', page=1) -> dict:
    """Una página de aceptantes activos. El estado usa la misma idea de inicio del curso."""
    texto = (q or '').strip()
    qs = (
        ProgresoEstudiante.objects.filter(
            curso=curso,
            estudiante__cliente=org,
            estudiante__activo=True,
        )
        .select_related('estudiante', 'modulo_actual')
        .order_by('estudiante__nombre', 'id')
    )
    if texto:
        qs = qs.filter(estudiante__nombre__icontains=texto)
    paginator = Paginator(qs, POR_PAGINA)
    pagina = paginator.get_page(page)
    ids = [progreso.id for progreso in pagina.object_list]
    cerrados = set()
    if ids:
        cerrados = set(
            ModuloCompletado.objects.filter(progreso_id__in=ids).values_list('progreso_id', flat=True)
        )
    filas = []
    for progreso in pagina.object_list:
        modulo = progreso.modulo_actual
        filas.append({
            'estudiante_id': progreso.estudiante_id,
            'nombre': progreso.estudiante.nombre,
            'estado': _estado(progreso, progreso.id in cerrados),
            'modulo': f'M{modulo.numero} — {modulo.titulo}' if modulo else None,
            'paso': progreso.paso_actual_modulo,
            'ultimo': progreso.fecha_ultimo_avance,
        })
    return {
        'filas': filas,
        'pagina': pagina,
        'q': texto,
        'total': paginator.count,
    }
