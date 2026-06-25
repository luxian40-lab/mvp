"""Panel admin: Aula web eki (estudiantes, profesores — distinto del portal clientes)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import render

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_extras import ArchivoModulo
from portal.models import PortalUsuario


def _cursos_aula_qs(cliente=None):
    qs = (
        Curso.objects.filter(activo=True, visible_en_aula=True)
        .annotate(total_modulos=Count('modulos'))
        .select_related('cliente')
        .order_by('orden', 'nombre')
    )
    if cliente:
        qs = qs.filter(Q(cliente=cliente) | Q(cliente__isnull=True))
    return qs


@staff_member_required
def aula_web_admin_view(request):
    cliente_id = request.GET.get('cliente')
    cliente = None
    if cliente_id:
        cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()

    est_qs = Estudiante.objects.filter(activo=True)
    prof_qs = PortalUsuario.objects.filter(rol__in=('profesor', 'admin')).select_related(
        'user', 'organizacion'
    )
    curso_qs = Curso.objects.filter(activo=True)
    progreso_qs = ProgresoEstudiante.objects.filter(curso__activo=True)

    if cliente:
        est_qs = est_qs.filter(cliente=cliente)
        prof_qs = prof_qs.filter(organizacion=cliente)
        curso_qs = curso_qs.filter(Q(cliente=cliente) | Q(cliente__isnull=True))
        progreso_qs = progreso_qs.filter(estudiante__cliente=cliente)

    cursos_aula = list(_cursos_aula_qs(cliente)[:12])
    modulos_recientes_qs = (
        Modulo.objects.filter(curso__activo=True, curso__visible_en_aula=True)
        .select_related('curso', 'curso__cliente')
        .order_by('-id')
    )
    if cliente:
        modulos_recientes_qs = modulos_recientes_qs.filter(
            Q(curso__cliente=cliente) | Q(curso__cliente__isnull=True)
        )
    modulos_recientes = modulos_recientes_qs[:8]

    archivos_aula = ArchivoModulo.objects.filter(
        activo=True,
        modulo__curso__activo=True,
        modulo__curso__visible_en_aula=True,
    ).count()

    return render(request, 'admin/aula_web.html', {
        'titulo': 'Aula web eki',
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
        'cliente': cliente,
        'profesores': prof_qs[:20],
        'cursos_aula': cursos_aula,
        'modulos_recientes': modulos_recientes,
        'stats': {
            'estudiantes': est_qs.count(),
            'profesores': prof_qs.filter(rol='profesor').count(),
            'admins_aula': prof_qs.filter(rol='admin').count(),
            'cursos_aula': _cursos_aula_qs(cliente).count(),
            'cursos_total': curso_qs.count(),
            'progresos': progreso_qs.count(),
            'archivos': archivos_aula,
        },
    })
