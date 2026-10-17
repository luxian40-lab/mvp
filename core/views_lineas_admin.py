"""Pantalla de líneas WhatsApp en el admin. Solo lectura."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.lineas.campana import fichas_admin


@staff_member_required
def lineas_admin_view(request):
    return render(request, 'admin/lineas_meta.html', {
        'fichas': fichas_admin(),
    })
