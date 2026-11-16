"""Vista admin del constructor. CursoAdmin solo registra la URL."""
from __future__ import annotations

import json

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse


def constructor_curso_view(model_admin, request, curso_id):
    """Superficie bloque 5. Flag off → aviso y vuelta al curso."""
    from core.cursos.autoria.servicio import versiones_activas
    from core.cursos.constructor.servicio import (
        adjuntar_media_mensaje,
        constructor_activo,
        crear_bloque,
        crear_mensaje_evaluacion,
        crear_mensaje_texto,
        crear_modulo,
        estructura_desde_snap,
        mover_bloque,
        mover_mensaje,
        mover_modulo,
        preview_ensamblado,
        publicar_desde_constructor,
    )
    from core.models import Curso, Modulo, PasoModulo, ProgresoEstudiante, SeccionModulo

    curso = Curso.objects.filter(pk=curso_id).first()
    if not curso:
        messages.error(request, 'Curso no encontrado.')
        return redirect('admin:core_curso_changelist')
    if not model_admin.has_change_permission(request, curso):
        messages.error(request, 'Sin permiso para cambiar este curso.')
        return redirect('admin:core_curso_changelist')
    if not request.user.has_perm('core.change_modulo'):
        messages.error(request, 'Sin permiso para editar módulos.')
        return redirect('admin:core_curso_change', curso_id)
    if not constructor_activo():
        messages.warning(
            request,
            'EKI_CONSTRUCTOR_CURSOS está apagado. No se abre el constructor.',
        )
        return redirect('admin:core_curso_change', curso_id)

    error = ''
    mensaje = ''
    if request.method == 'POST':
        accion = (request.POST.get('accion') or '').strip()
        direction = (request.POST.get('direction') or '').strip()
        try:
            if accion == 'crear_modulo':
                crear_modulo(
                    curso,
                    titulo=request.POST.get('titulo') or '',
                    descripcion=request.POST.get('descripcion') or '',
                )
                mensaje = 'Módulo creado (borrador; no publicado).'
            elif accion == 'crear_bloque':
                mod = Modulo.objects.filter(
                    pk=request.POST.get('modulo_id'), curso=curso,
                ).first()
                if not mod:
                    raise ValueError('módulo no encontrado en este curso')
                crear_bloque(mod, titulo=request.POST.get('titulo') or '')
                mensaje = 'Bloque añadido.'
            elif accion == 'crear_mensaje':
                bloque = SeccionModulo.objects.filter(
                    pk=request.POST.get('bloque_id'),
                    modulo__curso=curso,
                ).select_related('modulo').first()
                if not bloque:
                    raise ValueError('bloque no encontrado en este curso')
                crear_mensaje_texto(
                    bloque,
                    contenido=request.POST.get('contenido') or '',
                    titulo=request.POST.get('titulo') or '',
                    activo=request.POST.get('activo') == '1',
                )
                mensaje = 'Mensaje de texto añadido (no publica).'
            elif accion == 'mover_modulo':
                mod = Modulo.objects.filter(
                    pk=request.POST.get('modulo_id'), curso=curso,
                ).first()
                if not mod:
                    raise ValueError('módulo no encontrado en este curso')
                if mover_modulo(mod, direction):
                    mensaje = 'Orden de módulo actualizado.'
                else:
                    error = 'No se pudo mover el módulo.'
            elif accion == 'mover_bloque':
                bloque = SeccionModulo.objects.filter(
                    pk=request.POST.get('bloque_id'),
                    modulo__curso=curso,
                ).first()
                if not bloque:
                    raise ValueError('bloque no encontrado en este curso')
                if mover_bloque(bloque, direction):
                    mensaje = 'Orden de bloque actualizado.'
                else:
                    error = 'No se pudo mover el bloque.'
            elif accion == 'mover_mensaje':
                paso = PasoModulo.objects.filter(
                    pk=request.POST.get('mensaje_id'),
                    modulo__curso=curso,
                ).first()
                if not paso:
                    raise ValueError('mensaje no encontrado en este curso')
                if mover_mensaje(paso, direction):
                    mensaje = 'Orden de mensaje actualizado.'
                else:
                    error = 'No se pudo mover el mensaje.'
            elif accion == 'adjuntar_media':
                paso = PasoModulo.objects.filter(
                    pk=request.POST.get('mensaje_id'),
                    modulo__curso=curso,
                ).first()
                if not paso:
                    raise ValueError('mensaje no encontrado en este curso')
                adjuntar_media_mensaje(
                    paso, media_url=request.POST.get('media_url') or '',
                )
                mensaje = 'Media adjuntada (URL). Compresión Meta sigue en el pipeline.'
            elif accion == 'crear_evaluacion':
                bloque = SeccionModulo.objects.filter(
                    pk=request.POST.get('bloque_id'),
                    modulo__curso=curso,
                ).first()
                if not bloque:
                    raise ValueError('bloque no encontrado en este curso')
                crear_mensaje_evaluacion(
                    bloque,
                    pregunta=request.POST.get('pregunta') or '',
                    opcion_a=request.POST.get('opcion_a') or '',
                    opcion_b=request.POST.get('opcion_b') or '',
                    opcion_c=request.POST.get('opcion_c') or '',
                    opcion_d=request.POST.get('opcion_d') or '',
                    correcta=request.POST.get('correcta') or '',
                    activo=request.POST.get('activo') == '1',
                )
                mensaje = 'Evaluación A–D añadida (no publica).'
            elif accion == 'publicar_version':
                if not versiones_activas():
                    error = 'EKI_CURSO_VERSIONES está apagado. No se publicó ninguna versión.'
                elif request.POST.get('post') != 'yes':
                    curso = Curso.objects.select_related('version_publicada').get(pk=curso.pk)
                    n_activos = ProgresoEstudiante.objects.filter(
                        curso=curso, completado=False,
                    ).count()
                    return render(
                        request,
                        'admin/core/curso/constructor_publicar_confirm.html',
                        {
                            **model_admin.admin_site.each_context(request),
                            'title': 'Publicar versión',
                            'curso': curso,
                            'version_actual': curso.version_publicada,
                            'n_activos': n_activos,
                            'nota': (request.POST.get('nota') or '')[:200],
                            'volver_url': reverse('admin:core_curso_constructor', args=[curso.pk]),
                            'opts': model_admin.model._meta,
                            'has_view_permission': True,
                        },
                    )
                else:
                    version = publicar_desde_constructor(
                        curso, nota=request.POST.get('nota') or '',
                    )
                    if version is None:
                        error = 'No se pudo publicar (flag apagado o curso inválido).'
                    else:
                        mensaje = (
                            f'Versión v{version.numero} publicada. '
                            'La cohorte viva no se movió.'
                        )
                        curso.refresh_from_db()
            else:
                error = 'Acción no reconocida.'
        except ValueError as exc:
            error = str(exc)

    snap = preview_ensamblado(curso)
    return render(
        request,
        'admin/core/curso/constructor.html',
        {
            **model_admin.admin_site.each_context(request),
            'title': f'Constructor — {curso.nombre}',
            'curso': curso,
            'arbol': estructura_desde_snap(snap),
            'preview_json': json.dumps(snap, ensure_ascii=False, indent=2),
            'version_publicada': getattr(curso, 'version_publicada', None),
            'puede_publicar': versiones_activas(),
            'mensaje': mensaje,
            'error': error,
            'volver_url': reverse('admin:core_curso_change', args=[curso.pk]),
            'opts': model_admin.model._meta,
            'has_view_permission': True,
        },
    )
