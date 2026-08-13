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
                uploaded = request.FILES.get('media_file')
                if uploaded:
                    from core.admin._common import guardar_upload_admin_media_resultado

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
                    agregar_micro(
                        modulo,
                        seccion,
                        titulo=titulo,
                        contenido=contenido,
                        media_url=media_url,
                        media_wa_apto=media_wa_apto,
                    )
                    messages.success(request, 'Microcontenido añadido.')
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
        'builder_on': True,
        'builder_qs': '?builder=1' if (
            request.GET.get('builder') == '1' or request.POST.get('builder') == '1'
        ) else '',
        'change_url': f'/admin/core/modulo/{modulo.id}/change/',
    }
    return render(request, 'admin/module_builder.html', ctx)
