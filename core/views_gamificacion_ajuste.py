"""Admin: sumar/restar puntos y registrar notas manuales de gamificación."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from core.gamificacion_ajuste_service import (
    _modo_label,
    ajustar_puntos_estudiantes,
    filas_estudiantes_gamificacion,
    registrar_nota_manual_estudiante,
)
from core.gamificacion_modo import gamificacion_activa, modo_usa_calificacion, modo_usa_puntos
from core.models import Cliente, Curso


def _cliente_desde_request(request) -> Cliente | None:
    raw = request.GET.get('cliente') or request.POST.get('cliente')
    if not raw:
        return None
    try:
        return Cliente.objects.get(pk=int(raw), activo=True)
    except (ValueError, Cliente.DoesNotExist):
        return None


def _redirect_gamif(cliente_id: int):
    return redirect(f'/admin/gamificacion-ajuste/?cliente={cliente_id}')


@staff_member_required
def gamificacion_ajuste_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)
    filas = []
    modo = None
    modo_label = ''
    cursos = []
    gamif_activa = False
    usa_puntos = False
    usa_notas = False

    if cliente:
        gamif_activa = gamificacion_activa(cliente)
        usa_puntos = modo_usa_puntos(cliente)
        usa_notas = modo_usa_calificacion(cliente)
        filas, modo = filas_estudiantes_gamificacion(cliente)
        modo_label = _modo_label(modo)
        cursos = list(Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre'))

    if request.method == 'POST' and cliente:
        action = request.POST.get('action', '')

        if action == 'ajustar_puntos':
            if not usa_puntos:
                messages.error(request, 'Este cliente usa modo calificación, no puntos.')
                return _redirect_gamif(cliente.id)
            try:
                delta = int(request.POST.get('delta', '0'))
            except ValueError:
                messages.error(request, 'Puntos inválidos. Use un número entero (+15 o −5).')
                return _redirect_gamif(cliente.id)

            seleccionados = {
                int(pk) for pk in request.POST.getlist('estudiantes')
                if str(pk).isdigit()
            }
            motivo = request.POST.get('motivo', '').strip()

            try:
                resultados = ajustar_puntos_estudiantes(seleccionados, delta, motivo, cliente)
            except ValueError as exc:
                messages.error(request, str(exc))
                return _redirect_gamif(cliente.id)

            signo = '+' if delta > 0 else '−'
            messages.success(
                request,
                f'Puntos ajustados para {len(resultados)} estudiante(s) ({signo}{abs(delta)} pts). '
                'El ranking del portal se actualiza al refrescar.',
            )
            return _redirect_gamif(cliente.id)

        if action == 'registrar_nota':
            if not usa_notas:
                messages.error(request, 'Este cliente usa modo puntos, no calificación 1–5.')
                return _redirect_gamif(cliente.id)

            est_id = request.POST.get('estudiante_nota', '')
            if not str(est_id).isdigit():
                messages.error(request, 'Elija un estudiante para la nota.')
                return _redirect_gamif(cliente.id)

            curso_id = request.POST.get('curso_nota') or ''
            curso_pk = int(curso_id) if str(curso_id).isdigit() else None

            try:
                resultado = registrar_nota_manual_estudiante(
                    int(est_id),
                    request.POST.get('nota', ''),
                    cliente,
                    curso_id=curso_pk,
                    detalle=request.POST.get('detalle_nota', ''),
                    peso_raw=request.POST.get('peso_nota', ''),
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return _redirect_gamif(cliente.id)

            prom_txt = f'{resultado["promedio"]:.1f}' if resultado['promedio'] is not None else '—'
            messages.success(
                request,
                f'Nota {resultado["nota"]} registrada para {resultado["estudiante"].nombre}. '
                f'Promedio actual: {prom_txt} ({resultado["cantidad"]} evaluación/es).',
            )
            return _redirect_gamif(cliente.id)

    return render(request, 'admin/gamificacion_ajuste.html', {
        'titulo': 'Ajustar gamificación',
        'clientes': clientes,
        'cliente': cliente,
        'filas': filas,
        'modo': modo,
        'modo_label': modo_label,
        'gamif_activa': gamif_activa,
        'usa_puntos': usa_puntos,
        'usa_notas': usa_notas,
        'cursos': cursos,
    })
