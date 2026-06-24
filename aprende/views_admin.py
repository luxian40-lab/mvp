"""Panel admin: Aula web eki (estudiantes, profesores — distinto del portal clientes)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from portal.models import PortalUsuario


@staff_member_required
def aula_web_admin_view(request):
    cliente_id = request.GET.get('cliente')
    cliente = None
    if cliente_id:
        cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()

    est_qs = Estudiante.objects.filter(activo=True)
    prof_qs = PortalUsuario.objects.filter(rol='profesor')
    curso_qs = Curso.objects.filter(activo=True)
    progreso_qs = ProgresoEstudiante.objects.filter(curso__activo=True)

    if cliente:
        est_qs = est_qs.filter(cliente=cliente)
        prof_qs = prof_qs.filter(organizacion=cliente)
        curso_qs = curso_qs.filter(cliente=cliente)
        progreso_qs = progreso_qs.filter(estudiante__cliente=cliente)

    return render(request, 'admin/aula_web.html', {
        'titulo': 'Aula web eki',
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
        'cliente': cliente,
        'stats': {
            'estudiantes': est_qs.count(),
            'profesores': prof_qs.count(),
            'cursos': curso_qs.count(),
            'progresos': progreso_qs.count(),
        },
    })
