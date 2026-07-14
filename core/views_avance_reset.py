"""Admin: ajustar avance de estudiantes por curso (sin borrar personas)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from core.avance_reset_service import (
    ajustar_avance_estudiantes,
    filas_avance_curso,
    modulos_curso_ordenados,
    opciones_pasos_por_modulo,
)
from core.models import Cliente, Curso, Modulo, PasoModulo


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


def _redirect_avance(cliente_id: int, *, curso_id=None):
    q = f'?cliente={cliente_id}'
    if curso_id:
        q += f'&curso={curso_id}'
    return redirect(f'/admin/ajustar-avance/{q}')


@staff_member_required
def ajustar_avance_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)
    curso_id = _int_param(request, 'curso')

    if not cliente:
        return render(request, 'admin/avance_reset.html', {
            'titulo': 'Ajustar avance',
            'clientes': clientes,
            'cliente': None,
        })

    cursos = Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
    curso = None
    modulos = []
    filas = []
    pasos_por_modulo = {}

    if curso_id:
        try:
            curso = Curso.objects.get(pk=curso_id, cliente=cliente, activo=True)
            modulos = modulos_curso_ordenados(curso)
            filas = filas_avance_curso(cliente, curso)
            pasos_por_modulo = opciones_pasos_por_modulo(curso)
        except Curso.DoesNotExist:
            messages.error(request, 'Curso no válido para este cliente.')

    if request.method == 'POST' and request.POST.get('action') == 'ajustar' and curso:
        seleccionados = {
            int(pk) for pk in request.POST.getlist('estudiantes')
            if str(pk).isdigit()
        }
        if not seleccionados:
            messages.error(request, 'Marque al menos un estudiante.')
            return _redirect_avance(cliente.id, curso_id=curso.id)

        reiniciar = request.POST.get('modo') == 'reiniciar'
        modulo_id = _int_param(request, 'modulo_destino')
        paso_id = _int_param(request, 'paso_destino')
        modulo_destino = None
        paso_destino = None
        if not reiniciar:
            if not modulo_id:
                messages.error(request, 'Elija el módulo donde dejar al estudiante.')
                return _redirect_avance(cliente.id, curso_id=curso.id)
            try:
                modulo_destino = Modulo.objects.get(pk=modulo_id, curso=curso)
            except Modulo.DoesNotExist:
                messages.error(request, 'Módulo no válido.')
                return _redirect_avance(cliente.id, curso_id=curso.id)
            if paso_id:
                try:
                    paso_destino = PasoModulo.objects.select_related('seccion').get(
                        pk=paso_id, modulo=modulo_destino,
                    )
                except PasoModulo.DoesNotExist:
                    messages.error(request, 'Microcontenido no válido para ese módulo.')
                    return _redirect_avance(cliente.id, curso_id=curso.id)

        quitar_cert = request.POST.get('quitar_certificado') == 'on'
        quitar_examen = request.POST.get('quitar_examen') == 'on'

        try:
            resultados = ajustar_avance_estudiantes(
                seleccionados,
                curso,
                modulo_destino,
                paso_destino=paso_destino,
                reiniciar=reiniciar,
                quitar_certificado=quitar_cert,
                quitar_resultado_examen=quitar_examen,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return _redirect_avance(cliente.id, curso_id=curso.id)

        if reiniciar:
            destino_txt = 'desde el inicio'
        elif paso_destino:
            destino_txt = (
                f'en M{modulo_destino.numero}, micro #{paso_destino.orden}'
            )
        else:
            destino_txt = f'en M{modulo_destino.numero} (primer micro)'
        messages.success(
            request,
            f'Avance ajustado para {len(resultados)} estudiante(s) {destino_txt}. '
            'Al escribir *listo* en WhatsApp retoman desde ahí.',
        )
        return _redirect_avance(cliente.id, curso_id=curso.id)

    return render(request, 'admin/avance_reset.html', {
        'titulo': 'Ajustar avance',
        'clientes': clientes,
        'cliente': cliente,
        'cursos': cursos,
        'curso': curso,
        'modulos': modulos,
        'filas': filas,
        'filtro_curso': curso_id,
        'pasos_por_modulo': pasos_por_modulo,
    })
