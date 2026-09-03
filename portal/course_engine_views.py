"""Course Engine en portal — mismo motor y mismo contrato ajax que el Studio admin."""
from __future__ import annotations

import logging
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from core.course_engine.portal_api import contexto_studio, estado_generacion, studio_ajax
from core.models import Curso
from portal.authz import es_eki_ops

logger = logging.getLogger(__name__)


def _requiere_ce_portal(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        pu = getattr(request, 'portal_usuario', None)
        if not pu or pu.rol not in ('admin', 'eki_ops'):
            return redirect('/portal/login/')
        return view_func(request, *args, **kwargs)

    return wrapper


def _puede_course_engine(request, curso: Curso) -> bool:
    pu = getattr(request, 'portal_usuario', None)
    if not pu:
        return False
    if es_eki_ops(pu):
        return True
    if pu.rol == 'admin' and curso.cliente_id == pu.organizacion_id:
        return True
    return False


@_requiere_ce_portal
@require_http_methods(['GET', 'POST'])
def portal_curso_course_engine(request, curso_id: int):
    """Página del Course Engine y su endpoint ajax (mismo contrato que el admin)."""
    curso = get_object_or_404(Curso, pk=curso_id, activo=True)
    if not _puede_course_engine(request, curso):
        if request.method == 'POST':
            return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)
        return redirect('/portal/dashboard/')

    out = studio_ajax(request, curso, usuario=None)
    if out is not None:
        status = out.pop('status', 200)
        return JsonResponse(out, status=status)

    ctx = contexto_studio(curso)
    ctx['studio_url'] = f'/portal/cursos/{curso.pk}/course-engine/'
    return render(request, 'portal/curso_course_engine.html', ctx)


@require_GET
@_requiere_ce_portal
def api_course_engine_status(request, run_id: str):
    out = estado_generacion(run_id)
    if not out.get('ok'):
        return JsonResponse(out, status=404)
    return JsonResponse(out)
