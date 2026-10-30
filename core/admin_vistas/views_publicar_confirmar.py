# -*- coding: utf-8 -*-
"""Confirmación de publicar. La ruta antigua core_modulo_publicar no se toca.

Esta pantalla se retira cuando la interfaz de hoy también apunte aquí.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.models import Modulo


@staff_member_required
@require_http_methods(['GET', 'POST'])
def publicar_confirmar_view(request, modulo_id: int, contexto_admin=None):
    from core.modulo_publicacion import (
        evaluar_checklist_publicacion_detalle,
        publicar_modulo_wa,
    )

    modulo = Modulo.objects.select_related('curso').filter(pk=modulo_id).first()
    if not modulo:
        messages.error(request, 'Módulo no encontrado.')
        return redirect('admin:core_modulo_changelist')
    if not request.user.has_perm('core.change_modulo'):
        messages.error(request, 'Sin permiso para publicar módulos.')
        return redirect('admin:core_modulo_change', modulo_id)
    if request.method == 'POST':
        ok, errores = publicar_modulo_wa(modulo, usuario=request.user)
        if ok:
            messages.success(
                request,
                f'Módulo {modulo.numero} («{modulo.titulo}») publicado para WhatsApp.',
            )
        else:
            messages.error(
                request,
                'No se pudo publicar: ' + '; '.join(errores[:3]),
            )
        return redirect('admin_module_builder', modulo_id=modulo.pk)
    checklist = evaluar_checklist_publicacion_detalle(modulo)
    ctx = dict(contexto_admin or {})
    ctx.update({
        'title': 'Confirmar publicación',
        'modulo': modulo,
        'checklist': checklist,
        'builder_url': reverse('admin_module_builder', kwargs={'modulo_id': modulo.pk}),
        'ruta_antigua': reverse('admin:core_modulo_publicar', args=[modulo.pk]),
    })
    return render(request, 'admin/core/modulo/publicar_confirmar_v2.html', ctx)
