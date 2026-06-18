"""Admin: enviar mensajes push a estudiantes elegidos (sin tocar avance)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import redirect, render

from core.mensajes_push import enviar_push_a_estudiantes
from core.models import Cliente, Curso, Estudiante
from core.models_extras import GrupoEstudiantes, MensajePush


def _cliente_desde_request(request) -> Cliente | None:
    raw = request.GET.get('cliente') or request.POST.get('cliente')
    if not raw:
        return None
    try:
        return Cliente.objects.get(pk=int(raw), activo=True)
    except (ValueError, Cliente.DoesNotExist):
        return None


def _int_param(request, name: str) -> int | None:
    raw = request.GET.get(name) or request.POST.get(name) or ''
    return int(raw) if str(raw).isdigit() else None


def _redirect(cliente_id: int, *, curso_id=None, grupo_id=None, q=''):
    url = f'?cliente={cliente_id}'
    if curso_id:
        url += f'&curso={curso_id}'
    if grupo_id:
        url += f'&grupo={grupo_id}'
    if q:
        url += f'&q={q}'
    return redirect(f'/admin/push-estudiantes/{url}')


def _estudiantes_push(
    cliente: Cliente,
    curso_id: int | None,
    grupo_id: int | None,
    busqueda: str = '',
):
    """Lista para marcar uno por uno; curso/grupo solo acotan la lista."""
    qs = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    if curso_id:
        qs = qs.filter(progresos__curso_id=curso_id).distinct()
    if grupo_id:
        qs = qs.filter(grupos__id=grupo_id, grupos__activo=True).distinct()
    busqueda = (busqueda or '').strip()
    if busqueda:
        qs = qs.filter(
            Q(nombre__icontains=busqueda)
            | Q(cedula__icontains=busqueda)
            | Q(telefono__icontains=busqueda)
        )
    return qs


def _ids_grupo(cliente: Cliente, grupo_id: int | None) -> set[int]:
    if not grupo_id:
        return set()
    return set(
        GrupoEstudiantes.objects.filter(
            pk=grupo_id, cliente=cliente, activo=True,
        ).values_list('estudiantes__id', flat=True)
    )


@staff_member_required
def push_estudiantes_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)
    curso_id = _int_param(request, 'curso')
    grupo_id = _int_param(request, 'grupo')
    busqueda = (request.GET.get('q') or request.POST.get('q') or '').strip()

    if not cliente:
        return render(request, 'admin/push_estudiantes.html', {
            'titulo': 'Push recordatorios',
            'clientes': clientes,
            'cliente': None,
        })

    cursos = Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
    grupos = GrupoEstudiantes.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    mensajes = MensajePush.objects.filter(activo=True, cliente=cliente).order_by('-fecha_creacion')
    estudiantes = _estudiantes_push(cliente, curso_id, grupo_id, busqueda)
    ids_en_grupo = _ids_grupo(cliente, grupo_id)

    if request.method == 'POST' and request.POST.get('action') == 'enviar':
        mensaje_id = _int_param(request, 'mensaje_push')
        post_grupo_id = _int_param(request, 'grupo') or grupo_id
        post_busqueda = (request.POST.get('q') or busqueda).strip()

        if not mensaje_id:
            messages.error(request, 'Elija un mensaje push.')
            return _redirect(cliente.id, curso_id=curso_id, grupo_id=post_grupo_id, q=post_busqueda)

        try:
            mensaje = MensajePush.objects.get(pk=mensaje_id, cliente=cliente, activo=True)
        except MensajePush.DoesNotExist:
            messages.error(request, 'Mensaje push no válido.')
            return _redirect(cliente.id, curso_id=curso_id, grupo_id=post_grupo_id, q=post_busqueda)

        if request.POST.get('enviar_todo_grupo') == '1' and post_grupo_id:
            try:
                grupo = GrupoEstudiantes.objects.get(pk=post_grupo_id, cliente=cliente, activo=True)
            except GrupoEstudiantes.DoesNotExist:
                messages.error(request, 'Grupo no válido.')
                return _redirect(cliente.id, curso_id=curso_id, grupo_id=post_grupo_id, q=post_busqueda)
            seleccionados = set(
                grupo.estudiantes.filter(cliente=cliente, activo=True).values_list('pk', flat=True)
            )
        else:
            seleccionados = {
                int(pk) for pk in request.POST.getlist('estudiantes')
                if str(pk).isdigit()
            }

        if not seleccionados:
            messages.error(
                request,
                'Marque al menos un estudiante en la lista (selección individual).',
            )
            return _redirect(cliente.id, curso_id=curso_id, grupo_id=post_grupo_id, q=post_busqueda)

        r = enviar_push_a_estudiantes(mensaje, seleccionados)
        messages.success(
            request,
            f'Push «{mensaje.nombre}»: {r["enviados"]} enviado(s), {r["errores"]} error(es). '
            f'Enviado a {len(seleccionados)} persona(s) marcada(s). Responden *listo* para continuar.',
        )
        return _redirect(cliente.id, curso_id=curso_id, grupo_id=post_grupo_id, q=post_busqueda)

    return render(request, 'admin/push_estudiantes.html', {
        'titulo': 'Push recordatorios',
        'clientes': clientes,
        'cliente': cliente,
        'cursos': cursos,
        'grupos': grupos,
        'mensajes': mensajes,
        'estudiantes': estudiantes,
        'filtro_curso': curso_id,
        'filtro_grupo': grupo_id,
        'busqueda': busqueda,
        'ids_en_grupo': ids_en_grupo,
        'total_estudiantes_cliente': Estudiante.objects.filter(cliente=cliente, activo=True).count(),
    })
