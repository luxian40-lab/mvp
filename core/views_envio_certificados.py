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
    enviar_plantilla_inicial_certificado,
    enviar_whatsapp_certificados_existentes,
    filas_estudiantes_certificado,
    info_plantilla_curso,
    numeros_cierre_curso,
    plantillas_twilio_whatsapp,
    resolver_twilio_content_sid,
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


def _twilio_params_desde_post(request) -> dict:
    """Lee plantillas Twilio (admin o HX manual) del formulario."""
    inicial_id = _int_param(request, 'twilio_plantilla_inicial_id')
    media_id = _int_param(request, 'twilio_plantilla_media_id')
    previo_id = _int_param(request, 'twilio_plantilla_previo_id')
    diploma_id = _int_param(request, 'twilio_plantilla_diploma_id')
    media_var = (request.POST.get('media_var_index') or '1').strip() or '1'
    return {
        'twilio_content_sid_inicial': resolver_twilio_content_sid(
            plantilla_id=inicial_id,
            sid_manual=request.POST.get('twilio_sid_inicial_manual', ''),
        ),
        'twilio_content_sid_media': resolver_twilio_content_sid(
            plantilla_id=media_id,
            sid_manual=request.POST.get('twilio_sid_media_manual', ''),
        ),
        'media_var_index': media_var,
        'twilio_content_sid_previo': resolver_twilio_content_sid(
            plantilla_id=previo_id,
            sid_manual=request.POST.get('twilio_sid_previo_manual', ''),
        ),
        'twilio_content_sid_diploma': resolver_twilio_content_sid(
            plantilla_id=diploma_id,
            sid_manual=request.POST.get('twilio_sid_diploma_manual', ''),
        ),
    }


def _cerrar_avance_desde_post(request) -> bool:
    """Checkbox: cerrar curso si está en penúltimo o último módulo. Default ON."""
    if request.method != 'POST':
        return True
    return request.POST.get('cerrar_avance') == 'on'


def _mensaje_previo_desde_post(request) -> str:
    if request.POST.get('usar_mensaje_previo') != 'on':
        return ''
    if request.POST.get('modo_previo') == 'twilio':
        return ''
    return request.POST.get('mensaje_previo', '')


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

    penultimo_numero = ultimo_numero = None
    filas_en_cierre = 0
    if curso:
        penultimo_numero, ultimo_numero = numeros_cierre_curso(curso)
        filas_en_cierre = sum(1 for f in filas if f.get('en_tramo_cierre'))

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

        if action == 'enviar_plantilla_inicial':
            try:
                calificacion = float(request.POST.get('calificacion') or '100')
            except ValueError:
                calificacion = 100.0
            calificacion = max(0, min(100, calificacion))

            twilio = _twilio_params_desde_post(request)
            if not twilio['twilio_content_sid_inicial']:
                messages.error(
                    request,
                    'Elija la plantilla inicial (la que pide responder OK) o pegue su HX.',
                )
                return _redirect(
                    cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                    q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
                )

            resumen = enviar_plantilla_inicial_certificado(
                seleccionados,
                curso,
                twilio_content_sid_inicial=twilio['twilio_content_sid_inicial'],
                emitir_certificado=request.POST.get('emitir_certificado') == 'on',
                calificacion=calificacion,
                regenerar_si_existe=request.POST.get('regenerar') == 'on',
                plantilla=_plantilla_desde_post(request),
                permitir_otro_cliente=True,
                cerrar_avance=_cerrar_avance_desde_post(request),
            )
            messages.success(
                request,
                f'Plantilla inicial enviada a {len(seleccionados)} seleccionado(s): '
                f'{resumen.get("plantillas_enviadas", 0)} plantilla(s), '
                f'{resumen.get("creados", 0)} cert. nuevos, '
                f'{resumen.get("existentes", 0)} ya existían, '
                f'{resumen.get("pendientes", 0)} en espera de OK, '
                f'{resumen.get("errores", 0)} error(es). '
                'Cuando respondan *OK* o un número, reciben el certificado automáticamente.',
            )
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

            twilio = _twilio_params_desde_post(request)
            mensaje_previo = _mensaje_previo_desde_post(request)
            enviar_wa = request.POST.get('enviar_certificado_wa') == 'on'

            if (
                enviar_wa
                and not twilio['twilio_content_sid_media']
                and not twilio['twilio_content_sid_previo']
                and not mensaje_previo
            ):
                messages.warning(
                    request,
                    'Sin plantilla de aviso ni plantilla con imagen: el diploma solo llega si el estudiante '
                    'escribió en las últimas 24 h. Elija plantilla aviso o plantilla con imagen.',
                )

            resumen = enviar_certificados_seleccion(
                seleccionados,
                curso,
                mensaje_previo=mensaje_previo,
                twilio_content_sid_media=twilio['twilio_content_sid_media'] or None,
                media_var_index=twilio['media_var_index'],
                twilio_content_sid_previo=twilio['twilio_content_sid_previo'] or None,
                twilio_content_sid_diploma=twilio['twilio_content_sid_diploma'] or None,
                emitir_certificado=request.POST.get('emitir_certificado') == 'on',
                enviar_whatsapp_certificado=enviar_wa,
                calificacion=calificacion,
                regenerar_si_existe=request.POST.get('regenerar') == 'on',
                plantilla=_plantilla_desde_post(request),
                permitir_otro_cliente=True,
                cerrar_avance=_cerrar_avance_desde_post(request),
            )
            messages.success(
                request,
                f'Enviado a {len(seleccionados)} seleccionado(s): '
                f'{resumen["mensajes_previos"]} plantilla(s) aviso, '
                f'{resumen.get("pendientes_respuesta", 0)} en espera de respuesta del estudiante, '
                f'{resumen["creados"]} cert. nuevos, '
                f'{resumen["existentes"]} ya existían, '
                f'{resumen["certificados_enviados"]} diploma(s) directos por WhatsApp, '
                f'{resumen.get("cursos_cerrados", 0)} curso(s) cerrado(s) al entregar, '
                f'{resumen["errores"]} error(es). '
                'Tras la plantilla, el diploma llega cuando el estudiante responde. '
                'Si está en el penúltimo o último módulo, el avance se cierra al llegar el diploma.',
            )
            return _redirect(
                cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
            )

        if action == 'reenviar_wa':
            twilio = _twilio_params_desde_post(request)
            mensaje_previo = _mensaje_previo_desde_post(request)
            if (
                not twilio['twilio_content_sid_media']
                and not twilio['twilio_content_sid_previo']
                and not mensaje_previo
            ):
                messages.error(
                    request,
                    'Para reenviar fuera de ventana 24 h elija la plantilla con imagen (ideal) '
                    'o una plantilla de aviso previo.',
                )
                return _redirect(
                    cliente.id, curso_id=curso.id, grupo_id=grupo_id,
                    q=busqueda, qg=busqueda_global, plantilla_id=plantilla_id, extra=extra_raw,
                )

            resumen = enviar_whatsapp_certificados_existentes(
                seleccionados,
                curso,
                mensaje_previo=mensaje_previo,
                twilio_content_sid_media=twilio['twilio_content_sid_media'] or None,
                media_var_index=twilio['media_var_index'],
                twilio_content_sid_previo=twilio['twilio_content_sid_previo'] or None,
                twilio_content_sid_diploma=twilio['twilio_content_sid_diploma'] or None,
                permitir_otro_cliente=True,
                cerrar_avance=_cerrar_avance_desde_post(request),
            )
            messages.success(
                request,
                f'Reenvío WhatsApp: {resumen["mensajes_previos"]} aviso(s) previo, '
                f'{resumen["enviados"]} diploma(s), {resumen["errores"]} error(es), '
                f'{resumen["omitidos"]} sin certificado emitido.',
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
        'plantillas_twilio': plantillas_twilio_whatsapp(),
        'penultimo_numero': penultimo_numero,
        'ultimo_numero': ultimo_numero,
        'filas_en_cierre': filas_en_cierre,
    })
