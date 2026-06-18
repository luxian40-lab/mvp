"""Admin: envío de certificados — elegir estudiantes, otro cliente OK, sin tocar curso digital."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from core.certificado_admin_preview import (
    GUIA_MARCADORES_HTML,
    guardar_plantilla_imagen_curso,
    respuesta_preview_png,
)
from core.certificado_presencial_service import (
    agregar_participante_certificado,
    enviar_certificados_seleccion,
    filas_estudiantes_certificado,
    info_plantilla_curso,
)
from core.models import Cliente, Curso
from core.models_extras import GrupoEstudiantes
from core.models_certificados import PlantillaCertificado

MENSAJE_PREVIO_DEFAULT = (
    'Hola {nombre}, te escribimos desde eki. '
    'En un momento te enviamos tu certificado digital del curso *{curso}*. '
    'Guárdalo y compártelo con orgullo.'
)


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


def _extra_ids_raw(request) -> str:
    return (request.GET.get('extra') or request.POST.get('extra') or '').strip()


def _extra_ids_set(raw: str) -> set[int]:
    return {int(x) for x in raw.split(',') if str(x).strip().isdigit()}


def _redirect(
    cliente_id: int,
    *,
    curso_id=None,
    grupo_id=None,
    q='',
    qg='',
    plantilla_id=None,
    extra='',
):
    url = f'/admin/envio-certificados/?cliente={cliente_id}'
    if curso_id:
        url += f'&curso={curso_id}'
    if grupo_id:
        url += f'&grupo={grupo_id}'
    if q:
        url += f'&q={q}'
    if qg:
        url += f'&qg={qg}'
    if plantilla_id:
        url += f'&plantilla_id={plantilla_id}'
    if extra:
        url += f'&extra={extra}'
    return redirect(url)


def _append_extra_id(extra_raw: str, estudiante_id: int) -> str:
    ids = _extra_ids_set(extra_raw)
    ids.add(estudiante_id)
    return ','.join(str(i) for i in sorted(ids))


def _ids_grupo(cliente: Cliente, grupo_id: int | None) -> set[int]:
    if not grupo_id:
        return set()
    try:
        grupo = GrupoEstudiantes.objects.get(pk=grupo_id, cliente=cliente, activo=True)
    except GrupoEstudiantes.DoesNotExist:
        return set()
    return set(grupo.estudiantes.filter(activo=True).values_list('pk', flat=True))


def _filtrar_filas_locales(filas: list[dict], busqueda: str) -> list[dict]:
    q = (busqueda or '').strip().lower()
    if not q:
        return filas
    out = []
    for fila in filas:
        est = fila['estudiante']
        blob = f'{est.nombre} {est.cedula} {est.telefono}'.lower()
        if q in blob:
            out.append(fila)
    return out


def _plantilla_desde_post(request) -> PlantillaCertificado | None:
    pid = _int_param(request, 'plantilla_id')
    if not pid:
        return None
    return PlantillaCertificado.objects.filter(pk=pid, activa=True).first()


@staff_member_required
def envio_certificados_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)
    curso_id = _int_param(request, 'curso')
    grupo_id = _int_param(request, 'grupo')
    plantilla_id = _int_param(request, 'plantilla_id')
    busqueda = (request.GET.get('q') or request.POST.get('q') or '').strip()
    busqueda_global = (request.GET.get('qg') or request.POST.get('qg') or '').strip()
    extra_raw = _extra_ids_raw(request)

    if not cliente:
        return render(request, 'admin/envio_certificados.html', {
            'titulo': 'Envío certificados',
            'clientes': clientes,
            'cliente': None,
            'mensaje_previo_default': MENSAJE_PREVIO_DEFAULT,
        })

    cursos = Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
    grupos = GrupoEstudiantes.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    curso = None
    filas = []
    plantilla_info = None
    ids_en_grupo = _ids_grupo(cliente, grupo_id)

    if curso_id:
        try:
            curso = Curso.objects.get(pk=curso_id, cliente=cliente, activo=True)
            filas = filas_estudiantes_certificado(
                cliente,
                curso,
                grupo_id=grupo_id,
                busqueda_global=busqueda_global,
                extra_estudiante_ids=_extra_ids_set(extra_raw),
            )
            if busqueda and not busqueda_global:
                filas = _filtrar_filas_locales(filas, busqueda)
            plantilla_info = info_plantilla_curso(cliente, curso, plantilla_id)
        except Curso.DoesNotExist:
            messages.error(request, 'Curso no válido.')

    if request.method == 'POST' and curso:
        action = request.POST.get('action')

        if action == 'preview':
            return respuesta_preview_png(request, cliente, curso)

        if action == 'subir_plantilla':
            archivo = request.FILES.get('archivo_plantilla_imagen')
            if not archivo:
                messages.error(request, 'Seleccione un archivo de imagen.')
            else:
                try:
                    pl = guardar_plantilla_imagen_curso(
                        cliente, curso, archivo, plantilla_id=plantilla_id,
                    )
                    messages.success(request, f'Plantilla «{pl.nombre}» guardada en S3.')
                except Exception as exc:
                    messages.error(request, f'No se pudo subir: {exc}')
            return _redirect(
                cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
            )

        if action == 'agregar_participante':
            est, estado = agregar_participante_certificado(
                cliente,
                nombre=request.POST.get('part_nombre', ''),
                cedula=request.POST.get('part_cedula', ''),
                telefono=request.POST.get('part_telefono', ''),
            )
            if estado == 'datos_incompletos':
                messages.error(request, 'Complete nombre, cédula y teléfono.')
            elif est is None:
                messages.error(request, 'No se pudo agregar el participante.')
            elif estado == 'encontrado':
                extra_raw = _append_extra_id(extra_raw, est.id)
                org = est.cliente.nombre if est.cliente else 'sin org'
                messages.success(
                    request,
                    f'«{est.nombre}» ya estaba en el sistema ({org}). '
                    'Aparece en la lista — puede enviarle el certificado sin afectar su curso digital.',
                )
            else:
                extra_raw = _append_extra_id(extra_raw, est.id)
                messages.success(request, f'Participante «{est.nombre}» creado y agregado a la lista.')
            return _redirect(
                cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
            )

        seleccionados = {
            int(pk) for pk in request.POST.getlist('estudiantes')
            if str(pk).isdigit()
        }
        if not seleccionados:
            messages.error(request, 'Marque al menos un estudiante.')
            return _redirect(
                cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
            )

        if action == 'enviar':
            try:
                calificacion = float(request.POST.get('calificacion') or '100')
            except ValueError:
                calificacion = 100.0
            calificacion = max(0, min(100, calificacion))

            mensaje_previo = request.POST.get('mensaje_previo', '')
            if request.POST.get('usar_mensaje_previo') != 'on':
                mensaje_previo = ''

            resumen = enviar_certificados_seleccion(
                seleccionados,
                curso,
                mensaje_previo=mensaje_previo,
                emitir_certificado=request.POST.get('emitir_certificado') == 'on',
                enviar_whatsapp_certificado=request.POST.get('enviar_certificado_wa') == 'on',
                calificacion=calificacion,
                regenerar_si_existe=request.POST.get('regenerar') == 'on',
                plantilla=_plantilla_desde_post(request),
                permitir_otro_cliente=True,
            )
            messages.success(
                request,
                f'Enviado a {len(seleccionados)} seleccionado(s): '
                f'{resumen["mensajes_previos"]} mensaje(s) previo, '
                f'{resumen["creados"]} cert. nuevos, '
                f'{resumen["existentes"]} ya existían, '
                f'{resumen["certificados_enviados"]} diploma(s) por WhatsApp, '
                f'{resumen["errores"]} error(es).',
            )
            return _redirect(
                cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
            )

    return render(request, 'admin/envio_certificados.html', {
        'titulo': 'Envío certificados',
        'clientes': clientes,
        'cliente': cliente,
        'cursos': cursos,
        'grupos': grupos,
        'curso': curso,
        'filas': filas,
        'filtro_curso': curso_id,
        'filtro_grupo': grupo_id,
        'filtro_plantilla': plantilla_id,
        'plantilla_info': plantilla_info,
        'ids_en_grupo': ids_en_grupo,
        'busqueda': busqueda,
        'busqueda_global': busqueda_global,
        'extra_raw': extra_raw,
        'mensaje_previo_default': MENSAJE_PREVIO_DEFAULT,
        'guia_marcadores_html': GUIA_MARCADORES_HTML,
    })
