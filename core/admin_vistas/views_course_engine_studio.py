# -*- coding: utf-8 -*-
"""Course Engine Studio — pantalla dedicada por curso (admin Unfold)."""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.course_engine.portal_api import contexto_studio, studio_ajax
from core.models import Curso

logger = logging.getLogger(__name__)


def _wants_json(request) -> bool:
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
        or bool(request.GET.get('demo_voice'))
        or request.GET.get('docs') == '1'
        or bool(request.GET.get('status'))
        or request.method == 'POST'
    )


def staff_member_required_json(view_func):
    """Como staff_member_required, pero ajax/demo_voice → JSON 401 en vez de HTML login."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_active and request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if _wants_json(request):
            return JsonResponse(
                {'ok': False, 'error': 'Sesión expirada. Vuelve a entrar al admin.'},
                status=401,
            )
        return staff_member_required(view_func)(request, *args, **kwargs)

    return wrapper


@staff_member_required_json
@require_http_methods(['GET', 'POST'])
def course_engine_studio_view(request, curso_id: int):
    curso = get_object_or_404(Curso.objects.select_related('cliente'), pk=curso_id)
    if not request.user.is_staff:
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)
        raise PermissionDenied

    out = studio_ajax(request, curso, usuario=request.user)
    if out is not None:
        status = out.pop('status', 200)
        return JsonResponse(out, status=status)

    rag_list_url = reverse('admin:agents_edu_documentorag_changelist') + f'?curso__id__exact={curso.pk}'
    ctx = contexto_studio(curso, request=request)
    ctx.update(
        {
            'title': f'Course Engine · {curso.nombre}',
            'studio_url': reverse('admin_course_engine_studio', kwargs={'curso_id': curso.pk}),
            'rag_list_url': rag_list_url,
            'curso_change_url': reverse('admin:core_curso_change', args=[curso.pk]),
        }
    )
    return render(request, 'admin/course_engine_studio.html', ctx)
