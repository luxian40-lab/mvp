"""Atajo del día: guardar el carrusel de cursos. No envía a Meta."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from core.cursos_generales import CATALOGO
from core.models_campana_meta import PlantillaMeta, guardar_borrador_carrusel


@staff_member_required
def campana_meta_dia_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre') or ''
        claves = request.POST.getlist('cursos')
        try:
            plantilla = guardar_borrador_carrusel(nombre, claves)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(
                request,
                f'Borrador «{plantilla.nombre_interno}» guardado. '
                'En la ficha use «Enviar plantilla a Meta para aprobación».',
            )
            return redirect('admin:core_plantillameta_change', plantilla.pk)
    borradores = (
        PlantillaMeta.objects.filter(tipo='CARRUSEL')
        .order_by('-fecha_creacion')[:8]
    )
    return render(request, 'admin/campana_meta_dia.html', {
        'titulo': 'Campaña Meta del día',
        'cursos': CATALOGO,
        'borradores': borradores,
    })
