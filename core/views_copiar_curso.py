"""Copiar curso(s) a otro cliente desde el admin."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from core.copiar_cursos import copiar_cursos_a_cliente
from core.models import Cliente, Curso


@staff_member_required
def copiar_curso_cliente_view(request):
    curso_ids_raw = request.GET.get('cursos') or request.POST.get('curso_ids') or request.GET.get('curso') or ''
    if request.POST.get('curso_ids'):
        curso_ids_raw = request.POST.get('curso_ids')
    curso_ids = [int(x) for x in str(curso_ids_raw).split(',') if str(x).strip().isdigit()]
    cursos = list(Curso.objects.filter(pk__in=curso_ids).select_related('cliente')) if curso_ids else []

    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    error = None

    if request.method == 'POST' and cursos:
        try:
            destino_id = int(request.POST.get('destino_id') or 0)
        except (TypeError, ValueError):
            destino_id = 0
        prefijo = (request.POST.get('prefijo') or '').strip()
        if not destino_id:
            error = 'Seleccione el cliente destino.'
        elif destino_id == cursos[0].cliente_id:
            error = 'El destino debe ser distinto al cliente del curso.'
        else:
            try:
                result = copiar_cursos_a_cliente(
                    curso_ids=[c.pk for c in cursos],
                    destino_id=destino_id,
                    prefijo=prefijo,
                )
                msg = (
                    f'Copiados {result.total_copiados} curso(s) de «{result.origen.nombre}» '
                    f'a «{result.destino.nombre}».'
                )
                if result.omitidos:
                    msg += f' Omitidos (ya existían): {", ".join(result.omitidos)}.'
                messages.success(request, msg)
                return redirect(f'/admin/core/curso/?cliente__id__exact={destino_id}')
            except (LookupError, ValueError) as exc:
                error = str(exc)

    return render(request, 'admin/copiar_curso_cliente.html', {
        'cursos': cursos,
        'curso_ids': ','.join(str(c.pk) for c in cursos),
        'clientes': clientes,
        'error': error,
        'origen': cursos[0].cliente if cursos else None,
    })
