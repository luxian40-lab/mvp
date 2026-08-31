# -*- coding: utf-8 -*-
"""Admin views — Module Builder WA (sin envío Twilio)."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.module_builder import (
    actualizar_micro,
    agregar_micro,
    agregar_seccion,
    arbol_modulo,
    desactivar_micro,
    diagnostico_estructura,
    module_builder_habilitado_para_curso,
    mover_micro,
    reordenar_micros_en_seccion,
    reordenar_secciones,
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
                    if uploaded and resultado.get('async_encode'):
                        aplicar_resultado_upload_async(
                            resultado,
                            paso.pk,
                            carpeta=resultado.get('carpeta') or 'modulos/pasos',
                            prefix=resultado.get('prefix') or f'modulo_{modulo.id}',
                        )
                        messages.info(request, mensaje_upload_media(resultado))
                    else:
                        messages.success(request, 'Microcontenido añadido.')
            elif action == 'save_modulo':
                paso_ids: set[int] = set()
                for key in request.POST:
                    if not key.startswith('paso_'):
                        continue
                    parts = key.split('_', 2)
                    if len(parts) >= 2 and parts[1].isdigit():
                        paso_ids.add(int(parts[1]))
                guardados = 0
                for pid in sorted(paso_ids):
                    paso = PasoModulo.objects.filter(pk=pid, modulo=modulo).first()
                    if not paso:
                        continue
                    titulo = request.POST.get(f'paso_{pid}_titulo')
                    contenido = request.POST.get(f'paso_{pid}_contenido')
                    activo_raw = request.POST.get(f'paso_{pid}_activo')
                    activo = activo_raw in ('1', 'on', 'true', 'True')
                    media_url_clear = request.POST.get(f'paso_{pid}_clear_media') == '1'
                    update_fields = {}
                    if titulo is not None:
                        update_fields['titulo'] = titulo
                    if contenido is not None:
                        update_fields['contenido'] = contenido
                    update_fields['activo'] = activo
                    actualizar_micro(paso, **update_fields)
                    if media_url_clear and (paso.media_url or '').strip():
                        paso.media_url = ''
                        paso.media_wa_apto = None
                        paso.save(update_fields=['media_url', 'media_wa_apto'])
                        from core.media_encode_async import limpiar_estado_encode_paso

                        limpiar_estado_encode_paso(paso.pk)
                    guardados += 1
                if guardados:
                    messages.success(request, f'Módulo guardado ({guardados} micro(s) actualizados).')
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
                        messages.info(request, mensaje_upload_media(resultado))
                    else:
                        messages.success(request, 'Archivo subido y guardado.')
            elif action == 'update_micro':
                paso_id = int(request.POST.get('paso_id') or 0)
                paso = get_object_or_404(PasoModulo, pk=paso_id, modulo=modulo)
                titulo = request.POST.get('titulo')
                contenido = request.POST.get('contenido')
                # Checkbox: ausente = desactivar (el form de edición siempre lo contempla).
                activo = (request.POST.get('activo') or '') in ('1', 'on', 'true', 'True')
                actualizar_micro(
                    paso,
                    titulo=titulo if titulo is not None else None,
                    contenido=contenido if contenido is not None else None,
                    activo=activo,
                )
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
            elif action == 'reorder_micros':
                sec_id = int(request.POST.get('seccion_id') or 0)
                seccion = get_object_or_404(SeccionModulo, pk=sec_id, modulo=modulo)
                raw = (request.POST.get('orden') or '').strip()
                paso_ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
                reordenar_micros_en_seccion(modulo, seccion, paso_ids)
                messages.success(request, 'Orden de micros actualizado.')
            elif action == 'reorder_secciones':
                raw = (request.POST.get('orden') or '').strip()
                seccion_ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
                reordenar_secciones(modulo, seccion_ids)
                messages.success(request, 'Orden de secciones actualizado.')
            else:
                messages.error(request, 'Acción no reconocida.')
        except ValidationError as exc:
            messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            logger.exception('module_builder POST')
            messages.error(request, f'Error: {exc}')
        return _redirect_builder(request, modulo.id)

    arbol, huerfanos = arbol_modulo(modulo, incluir_inactivos=True)
    diag = diagnostico_estructura(modulo)
    from core.modulo_publicacion import listar_problemas_media_modulo

    media_problemas = listar_problemas_media_modulo(modulo)
    publicar_url = reverse('admin:core_modulo_publicar', args=[modulo.pk])
    legacy_url = reverse('admin:core_modulo_change', args=[modulo.pk]) + '?legacy=1'
    n_borradores = sum(
        1
        for b in arbol
        for m in b.get('micros') or []
        if not getattr(m, 'activo', True)
    )
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
        'modulo_publicado_wa': bool(modulo.publicado_wa),
        'builder_on': True,
        'builder_qs': '?builder=1' if (
            request.GET.get('builder') == '1' or request.POST.get('builder') == '1'
        ) else '',
        'change_url': f'/admin/core/modulo/{modulo.id}/change/',
    }
    return render(request, 'admin/module_builder.html', ctx)
