"""Admin: Centro de Éxito (retención) en Dashboard Eki + consultor."""

from __future__ import annotations

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from core.models import Cliente, Curso, GrupoEstudiantes
from portal.agente_retencion import responder_agente_retencion
from portal.retencion_service import analitica_retencion_portal


@staff_member_required
def retencion_admin_view(request):
    """Compat: /admin/retencion/ → Dashboard Eki pestaña Centro de Éxito."""
    params = request.GET.copy()
    params['tab'] = 'retencion'
    qs = params.urlencode()
    return redirect(f'/admin/dashboard/?{qs}' if qs else '/admin/dashboard/?tab=retencion')


@staff_member_required
@require_POST
def retencion_admin_agente(request):
    """Consultor de retención para staff (misma lógica que portal)."""
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        body = {}

    pregunta = (body.get('pregunta') or request.POST.get('pregunta') or '').strip()
    cliente_raw = body.get('cliente') or request.GET.get('cliente')
    cliente_id = int(cliente_raw) if cliente_raw and str(cliente_raw).isdigit() else None
    if not cliente_id:
        return JsonResponse({'error': 'Seleccione una organización.'}, status=400)

    org = Cliente.objects.filter(pk=cliente_id, activo=True).first()
    if not org:
        return JsonResponse({'error': 'Organización no encontrada.'}, status=404)

    curso_raw = body.get('curso') or request.GET.get('curso')
    curso_id = int(curso_raw) if curso_raw and str(curso_raw).isdigit() else None
    if curso_id and not Curso.objects.filter(pk=curso_id, activo=True).exists():
        curso_id = None

    grupo_raw = body.get('grupo') or request.GET.get('grupo')
    grupo_id = int(grupo_raw) if grupo_raw and str(grupo_raw).isdigit() else None
    if grupo_id and not GrupoEstudiantes.objects.filter(pk=grupo_id).exists():
        grupo_id = None

    data = analitica_retencion_portal(
        org,
        curso_id=curso_id,
        grupo_id=grupo_id,
        desde=(body.get('desde') or None) or None,
        hasta=(body.get('hasta') or None) or None,
    )
    out = responder_agente_retencion(pregunta, data)
    return JsonResponse(out)
