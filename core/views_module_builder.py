# -*- coding: utf-8 -*-
"""Admin views — Module Builder WA (sin envío Twilio)."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.module_builder import (
    actualizar_micro,
    agregar_micro,
    agregar_seccion,
    arbol_modulo,
    desactivar_micro,
    duplicar_micro,
    diagnostico_estructura,
    module_builder_habilitado_para_curso,
    mover_micro,
    reordenar_micros_en_seccion,
    reordenar_secciones,
)
from core.module_builder_config import (
    formato_habilitado_desde_input,
    partes_habilitado_desde_input,
    persistir_builder_desde_post,
)
from core.models import Modulo, PasoModulo, SeccionModulo

logger = logging.getLogger(__name__)


def _require_builder(request, curso=None):
    if not request.user.is_staff:
        raise PermissionDenied
    if not module_builder_habilitado_para_curso(curso, request):
        raise PermissionDenied(
            'Module Builder beta desactivado para este curso. '
            'Active EKI_MODULE_BUILDER_BETA=1, use ?builder=1 como superusuario, '
            'o añada el curso a EKI_MODULE_BUILDER_CURSOS.'
        )


def _redirect_builder(request, modulo_id: int):
    """302 al Builder preservando ?builder=1 (bypass superusuario)."""
    url = reverse('admin_module_builder', kwargs={'modulo_id': modulo_id})
    if request.GET.get('builder') == '1' or request.POST.get('builder') == '1':
        return redirect(f'{url}?builder=1')
    return redirect(url)


_DRAFT_UPLOAD_KW = {
    'include_modulo_titulo': False,
    'include_config_general': False,
}

_DRAFT_REPLACE_MEDIA_KW = {
    'include_modulo_titulo': False,
    'include_secciones': False,
    'include_config_general': False,
}


def _draft_persist_kwargs(request, base: dict) -> dict:
    """Subida con cambios dirty: persiste general; subida limpia: no toca drip/entrega."""
    kw = dict(base)
    if request.POST.get('persist_general') == '1':
        kw['include_config_general'] = True
    return kw


def _persist_builder_from_post(
    request,
    modulo: Modulo,
    *,
    solo_paso_id: int | None = None,
    include_modulo_titulo: bool = True,
    include_secciones: bool = True,
    include_config_general: bool = True,
) -> list[str]:
    return persistir_builder_desde_post(
        modulo,
        request.POST,
        solo_paso_id=solo_paso_id,
        include_modulo_titulo=include_modulo_titulo,
        include_secciones=include_secciones,
        include_config_general=include_config_general,
    )


def _json_reorder_ok(modulo: Modulo, request):
    if request.POST.get('ajax') != '1':
        return None
    orden = {
        str(row['id']): row['orden']
        for row in PasoModulo.objects.filter(modulo=modulo).values('id', 'orden')
    }
    return JsonResponse({'ok': True, 'orden': orden})


@staff_member_required
@require_http_methods(['GET', 'POST'])
def module_builder_view(request, modulo_id: int):
    modulo = get_object_or_404(
        Modulo.objects.select_related('curso', 'curso__cliente'),
        pk=modulo_id,
    )
    _require_builder(request, modulo.curso)

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'replace_media':
                paso_id = int(request.POST.get('paso_id') or 0)
                _persist_builder_from_post(
                    request,
                    modulo,
                    solo_paso_id=paso_id or None,
                    **_draft_persist_kwargs(request, _DRAFT_REPLACE_MEDIA_KW),
                )
            elif action in (
                'add_micro',
                'add_seccion',
                'duplicate_micro',
                'deactivate_micro',
                'reorder_micros',
                'reorder_secciones',
            ):
                _persist_builder_from_post(
                    request,
                    modulo,
                    **_draft_persist_kwargs(request, _DRAFT_UPLOAD_KW),
                )
            if action == 'add_seccion':
                titulo = (request.POST.get('titulo') or '').strip()
                s = agregar_seccion(modulo, titulo=titulo)
                messages.success(request, f'Sección «{s.titulo}» creada.')
            elif action == 'add_micro':
                sec_id = int(request.POST.get('seccion_id') or 0)
                seccion = get_object_or_404(SeccionModulo, pk=sec_id, modulo=modulo)
                titulo = (request.POST.get('titulo') or '').strip()
                contenido = (request.POST.get('contenido') or '').strip()
                media_url = ''
                media_wa_apto = None
                resultado = None
                uploaded = request.FILES.get('media_file')
                if uploaded:
                    from core.admin._common import guardar_upload_admin_media_resultado
                    from core.media_encode_async import (
                        aplicar_resultado_upload_async,
                        mensaje_upload_media,
                    )

                    resultado = guardar_upload_admin_media_resultado(
                        uploaded,
                        carpeta='modulos/pasos',
                        prefix=f'modulo_{modulo.id}',
                    )
                    media_url = resultado['url']
                    media_wa_apto = resultado.get('media_wa_apto')
                if not contenido and not media_url:
                    messages.error(request, 'Escriba texto o suba un archivo.')
                else:
                    paso = agregar_micro(
                        modulo,
                        seccion,
                        titulo=titulo,
                        contenido=contenido,
                        media_url=media_url,
                        media_wa_apto=media_wa_apto,
                    )
                    if uploaded and resultado and resultado.get('async_encode'):
                        aplicar_resultado_upload_async(
                            resultado,
                            paso.pk,
                            carpeta=resultado.get('carpeta') or 'modulos/pasos',
                            prefix=resultado.get('prefix') or f'modulo_{modulo.id}',
                        )
                        messages.info(
                            request,
                            f'Micro #{paso.orden}: {mensaje_upload_media(resultado)}',
                        )
                    elif uploaded:
                        messages.success(request, f'Micro #{paso.orden}: archivo subido.')
                    else:
                        messages.success(request, 'Microcontenido añadido.')
            elif action in ('save_modulo', 'save_modulo_meta', 'rename_seccion'):
                solo_paso = request.POST.get('paso_id')
                solo_paso_id = int(solo_paso) if solo_paso and str(solo_paso).isdigit() else None

                if action == 'rename_seccion':
                    sec_id = int(request.POST.get('seccion_id') or 0)
                    seccion = get_object_or_404(SeccionModulo, pk=sec_id, modulo=modulo)
                    nuevo = (request.POST.get('titulo') or '').strip()
                    if not nuevo:
                        messages.error(request, 'Escriba un nombre para la sección.')
                    else:
                        seccion.titulo = nuevo[:200]
                        seccion.save(update_fields=['titulo'])
                        messages.success(request, f'Sección renombrada: «{seccion.titulo}».')
                    return _redirect_builder(request, modulo.id)

                hab_antes = modulo.habilitado_desde
                partes = persistir_builder_desde_post(
                    modulo,
                    request.POST,
                    solo_paso_id=solo_paso_id,
                    require_titulo_modulo=True,
                )
                modulo.refresh_from_db()
                hab_txt = formato_habilitado_desde_input(modulo.habilitado_desde)
                if 'calendario' in (partes or []):
                    logger.info(
                        'module_builder save_modulo calendario modulo_id=%s habilitado_desde=%s',
                        modulo.id,
                        hab_txt or '(vacío)',
                    )
                if request.POST.get('ajax') == '1':
                    return JsonResponse({
                        'ok': True,
                        'partes': partes,
                        'habilitado_desde': formato_habilitado_desde_input(modulo.habilitado_desde),
                        'habilitado_desde_fecha': partes_habilitado_desde_input(modulo.habilitado_desde)[0],
                        'habilitado_desde_hora': partes_habilitado_desde_input(modulo.habilitado_desde)[1],
                    })
                if partes:
                    msg = f'Módulo guardado ({", ".join(partes)}).'
                    if modulo.habilitado_desde:
                        msg += f' Drip guardado: {hab_txt}.'
                    elif hab_antes and not modulo.habilitado_desde:
                        msg += ' Calendario drip eliminado.'
                    messages.success(request, msg)
                elif action == 'save_modulo_meta':
                    messages.success(request, f'Nombre del módulo actualizado: «{modulo.titulo}».')
                else:
                    messages.info(request, 'Nada que guardar.')
            elif action == 'replace_media':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                uploaded = request.FILES.get('media_file')
                if not uploaded:
                    messages.error(request, 'Elegí un archivo para subir.')
                else:
                    from core.admin._common import guardar_upload_admin_media_resultado
                    from core.media_encode_async import (
                        aplicar_resultado_upload_async,
                        limpiar_estado_encode_paso,
                        mensaje_upload_media,
                    )

                    limpiar_estado_encode_paso(paso.pk)
                    resultado = guardar_upload_admin_media_resultado(
                        uploaded,
                        carpeta='modulos/pasos',
                        prefix=f'modulo_{modulo.id}',
                    )
                    paso.media_url = resultado['url']
                    paso.media_wa_apto = resultado.get('media_wa_apto')
                    paso.save(update_fields=['media_url', 'media_wa_apto'])
                    if resultado.get('async_encode'):
                        aplicar_resultado_upload_async(
                            resultado,
                            paso.pk,
                            carpeta=resultado.get('carpeta') or 'modulos/pasos',
                            prefix=resultado.get('prefix') or f'modulo_{modulo.id}',
                        )
                        messages.info(
                            request,
                            f'Micro #{paso.orden} «{(paso.titulo or "").strip() or paso.pk}»: '
                            f'{mensaje_upload_media(resultado)}',
                        )
                    else:
                        messages.success(
                            request,
                            f'Micro #{paso.orden}: archivo subido y listo para WhatsApp.',
                        )
            elif action == 'delete_media':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                from core.media_encode_async import limpiar_estado_encode_paso

                paso.media_url = ''
                paso.media_wa_apto = None
                paso.save(update_fields=['media_url', 'media_wa_apto'])
                limpiar_estado_encode_paso(paso.pk)
                if request.POST.get('ajax') == '1':
                    return JsonResponse({
                        'ok': True,
                        'paso_id': paso.pk,
                        'media_url': '',
                    })
                messages.success(
                    request,
                    f'Micro #{paso.orden}: archivo quitado. El texto del paso se conserva.',
                )
            elif action == 'update_micro':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                titulo = request.POST.get('titulo')
                contenido = request.POST.get('contenido')
                update_kwargs = {}
                if titulo is not None:
                    update_kwargs['titulo'] = titulo
                if contenido is not None:
                    update_kwargs['contenido'] = contenido
                if 'activo' in request.POST:
                    update_kwargs['activo'] = (request.POST.get('activo') or '') in (
                        '1',
                        'on',
                        'true',
                        'True',
                    )
                actualizar_micro(paso, **update_kwargs)
                messages.success(request, 'Micro guardado.')
            elif action == 'move_micro':
                paso_id = int(request.POST.get('paso_id') or 0)
                direction = (request.POST.get('direction') or '').strip()
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                if mover_micro(paso, direction):
                    messages.success(request, 'Orden actualizado.')
                else:
                    messages.info(request, 'Sin cambio (ya está al extremo).')
            elif action == 'deactivate_micro':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                desactivar_micro(paso)
                messages.success(request, 'Micro desactivado (ya no se envía).')
            elif action == 'duplicate_micro':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                copia = duplicar_micro(paso)
                messages.success(
                    request,
                    f'Micro duplicado como borrador (#{copia.orden} «{(copia.titulo or "").strip()}»).',
                )
            elif action == 'reorder_micros':
                sec_id = int(request.POST.get('seccion_id') or 0)
                seccion = get_object_or_404(SeccionModulo, pk=sec_id, modulo=modulo)
                raw = (request.POST.get('orden') or '').strip()
                paso_ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
                reordenar_micros_en_seccion(modulo, seccion, paso_ids)
                resp = _json_reorder_ok(modulo, request)
                if resp:
                    return resp
                messages.success(request, 'Orden de micros actualizado.')
            elif action == 'reorder_secciones':
                raw = (request.POST.get('orden') or '').strip()
                seccion_ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
                reordenar_secciones(modulo, seccion_ids)
                resp = _json_reorder_ok(modulo, request)
                if resp:
                    return resp
                messages.success(request, 'Orden de secciones actualizado.')
            else:
                messages.error(request, 'Acción no reconocida.')
        except Http404:
            raise
        except ValidationError as exc:
            messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
        except ValueError as exc:
            if request.POST.get('ajax') == '1':
                return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
        except Exception as exc:
            logger.exception('module_builder POST action=%s', action)
            err_msg = 'No se pudo completar la acción. Revise los datos e intente de nuevo.'
            if request.POST.get('ajax') == '1':
                return JsonResponse({'ok': False, 'error': err_msg}, status=500)
            messages.error(request, err_msg)
        return _redirect_builder(request, modulo.id)

    arbol, huerfanos = arbol_modulo(modulo, incluir_inactivos=True)
    diag = diagnostico_estructura(modulo)
    from core.modulo_publicacion import listar_problemas_media_modulo

    media_problemas = listar_problemas_media_modulo(modulo)
    publicar_url = reverse('admin:core_modulo_publicar', args=[modulo.pk])
    avanzado_url = reverse('admin:core_modulo_change', args=[modulo.pk]) + '?avanzado=1'
    legacy_url = avanzado_url
    archivos_url = f'/admin/core/archivomodulo/?modulo__id__exact={modulo.pk}'
    n_borradores = sum(
        1
        for b in arbol
        for m in b.get('micros') or []
        if not getattr(m, 'activo', True)
    )
    curso = modulo.curso
    cliente = getattr(curso, 'cliente', None) if curso else None
    habilitacion_cliente = None
    if cliente and curso:
        from core.models import HabilitacionModuloDripCliente

        habilitacion_cliente = (
            HabilitacionModuloDripCliente.objects.filter(
                cliente=cliente,
                curso=curso,
                modulo=modulo,
                activo=True,
            )
            .first()
        )
    drip_estudiantes_url = reverse('admin_drip_estudiantes')
    if cliente:
        drip_estudiantes_url += f'?cliente={cliente.pk}'
    ce_studio_url = reverse('admin_course_engine_studio', args=[curso.pk]) if curso else ''
    ctx = {
        'title': f'Builder · Módulo {modulo.numero}',
        'modulo': modulo,
        'curso': modulo.curso,
        'arbol': arbol,
        'huerfanos': huerfanos,
        'diag': diag,
        'n_borradores': n_borradores,
        'media_problemas': media_problemas,
        'n_media_problemas': len(media_problemas),
        'publicar_url': publicar_url,
        'legacy_url': legacy_url,
        'avanzado_url': avanzado_url,
        'archivos_url': archivos_url,
        'modo_entrega_choices': Modulo.MODOS_ENTREGA,
        'facilitador_checkpoint_choices': Modulo._meta.get_field(
            'facilitador_checkpoint'
        ).choices,
        'habilitado_desde_value': formato_habilitado_desde_input(modulo.habilitado_desde),
        'habilitado_desde_fecha': partes_habilitado_desde_input(modulo.habilitado_desde)[0],
        'habilitado_desde_hora': partes_habilitado_desde_input(modulo.habilitado_desde)[1],
        'curso_dias_espera': getattr(curso, 'dias_espera_entre_modulos', 0) if curso else 0,
        'cliente': cliente,
        'cliente_admin_url': reverse('admin:core_cliente_change', args=[cliente.pk]) if cliente else '',
        'curso_admin_url': reverse('admin:core_curso_change', args=[curso.pk]) if curso else '',
        'drip_estudiantes_url': drip_estudiantes_url,
        'habilitacion_cliente': habilitacion_cliente,
        'general_abierto': True,
        'modulo_publicado_wa': bool(modulo.publicado_wa),
        'builder_on': True,
        'builder_qs': '?builder=1' if (
            request.GET.get('builder') == '1' or request.POST.get('builder') == '1'
        ) else '',
        'change_url': f'/admin/core/modulo/{modulo.id}/change/',
        'ce_studio_url': ce_studio_url,
    }
    return render(request, 'admin/module_builder.html', ctx)
