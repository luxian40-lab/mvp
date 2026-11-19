"""URL fija de novedades de producto (/admin/novedades-eki/)."""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.models import BoletinEki


@staff_member_required
def novedades_eki_view(request):
    boletin = BoletinEki.objects.filter(publicado=True).first()
    cuerpo = ''
    if boletin:
        # Permitimos HTML del staff; el admin es de confianza.
        cuerpo = mark_safe(boletin.cuerpo)
    return render(
        request,
        'admin/novedades_eki.html',
        {
            'title': 'Novedades eki',
            'boletin': boletin,
            'cuerpo': cuerpo,
            'titulo_seguro': escape(boletin.titulo) if boletin else '',
        },
    )
