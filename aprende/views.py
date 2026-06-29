"""Aula web básica: estudiantes ven contenido, profesores lo suben."""

from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Curso, Modulo, ProgresoEstudiante, Estudiante
from core.models_extras import ArchivoModulo
from core.utils_telefono import normalizar_telefono, variantes_telefono
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario

from .acceso_modulos import (
    modulo_accesible_aula,
    modulos_visibles_aula,
    tareas_visibles_aula,
)
from .auth import es_profesor_aprende, requiere_estudiante_aprende, requiere_profesor_aprende
from .biblioteca_service import biblioteca_agrupada_por_curso_modulo
from .contenido_modulo_service import (
    archivos_multimedia_modulo,
    modulo_tiene_microcontenidos,
    secciones_modulo_aula,
)
from .lesson_service import actualizar_modulo_aula, crear_modulo_aula
from .media_aula import media_desde_url
from .middleware import APRENDE_EST_SESSION_KEY
from .models import EntregaTarea, TareaCurso
from .perfil_service import actualizar_perfil_aula, resumen_perfil_aula
from .ranking_service import resumen_ranking_aula
from .tarea_service import calificar_entrega, crear_tarea, guardar_entrega
from .tareas_aula_service import tareas_agrupadas_estudiante, tareas_por_curso


def _telefonos_coinciden(a: str, b: str) -> bool:
    va = set(variantes_telefono(a))
    vb = set(variantes_telefono(b))
    return bool(va & vb)


def _org_profesor(request):
    pu = getattr(request, 'portal_usuario', None)
    return pu.organizacion if pu else None


def _youtube_embed_id(url: str) -> str | None:
    if not url:
        return None
    m = re.search(
        r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})',
        url,
    )
    return m.group(1) if m else None


def inicio(request):
    return render(request, 'aprende/inicio.html')


def estudiante_login(request):
    if getattr(request, 'aprende_estudiante', None):
        return redirect('/aprende/estudiante/')

    error = None
    if request.method == 'POST':
        from core.models import Estudiante

        cedula = re.sub(r'[\s\.\-]', '', request.POST.get('cedula', '').strip())
        tel = normalizar_telefono(request.POST.get('telefono', ''))

        est = Estudiante.objects.filter(cedula=cedula, activo=True).first()
        if est and _telefonos_coinciden(est.telefono, tel):
            request.session[APRENDE_EST_SESSION_KEY] = est.pk
            return redirect('/aprende/estudiante/')
        error = (
            'Cédula o teléfono no coinciden. Use el mismo número de WhatsApp registrado '
            '(puede escribirlo con o sin 57).'
        )

    return render(request, 'aprende/estudiante_login.html', {'error': error})


def estudiante_logout(request):
    request.session.pop(APRENDE_EST_SESSION_KEY, None)
    return redirect('/aprende/')


@requiere_estudiante_aprende
def estudiante_cursos(request):
    est = request.aprende_estudiante
    progresos = (
        ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
        .select_related('curso', 'modulo_actual')
        .order_by('curso__nombre')
    )
    return render(request, 'aprende/estudiante_cursos.html', {
        'estudiante': est,
        'progresos': progresos,
    })
def estudiante_curso(request, curso_id: int):
    est = request.aprende_estudiante
    progreso = get_object_or_404(
        ProgresoEstudiante.objects.select_related('curso'),
        estudiante=est,
        curso_id=curso_id,
        curso__activo=True,
    )
    modulos = modulos_visibles_aula(est, progreso.curso, progreso)
    return render(request, 'aprende/estudiante_curso.html', {
        'estudiante': est,
        'progreso': progreso,
        'modulos': modulos,
        'curso_tab': 'modulos',
    })


@requiere_estudiante_aprende
def estudiante_curso_tareas(request, curso_id: int):
    est = request.aprende_estudiante
    progreso = get_object_or_404(
        ProgresoEstudiante.objects.select_related('curso'),
        estudiante=est,
        curso_id=curso_id,
        curso__activo=True,
    )
    tareas_list = tareas_por_curso(est, progreso.curso)
    return render(request, 'aprende/estudiante_curso_tareas.html', {
        'estudiante': est,
        'progreso': progreso,
        'tareas_list': tareas_list,
        'curso_tab': 'tareas',
    })


@requiere_estudiante_aprende
def estudiante_tarea(request, tarea_id: int):
    est = request.aprende_estudiante
    tarea = get_object_or_404(
        TareaCurso.objects.select_related('curso', 'modulo'),
        pk=tarea_id,
        activa=True,
        curso__activo=True,
    )
    if not ProgresoEstudiante.objects.filter(estudiante=est, curso=tarea.curso).exists():
        return redirect('/aprende/estudiante/')
    progreso = ProgresoEstudiante.objects.filter(estudiante=est, curso=tarea.curso).first()
    if tarea.modulo_id and not modulo_accesible_aula(est, tarea.modulo, progreso):
        messages.error(request, 'Esta tarea aún no está disponible para ti.')
        return redirect('aprende_estudiante_curso', curso_id=tarea.curso_id)

    entrega = EntregaTarea.objects.filter(tarea=tarea, estudiante=est).first()
    if request.method == 'POST':
        entrega, error = guardar_entrega(request, tarea, est)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, 'Tarea entregada correctamente.')
            return redirect('aprende_estudiante_tareas')

    return render(request, 'aprende/estudiante_tarea.html', {
        'estudiante': est,
        'tarea': tarea,
        'entrega': entrega,
    })


@requiere_estudiante_aprende
def estudiante_tareas(request):
    est = request.aprende_estudiante
    secciones = tareas_agrupadas_estudiante(est)
    return render(request, 'aprende/estudiante_tareas.html', {
        'estudiante': est,
        'secciones': secciones,
    })


@requiere_estudiante_aprende
def estudiante_modulo(request, modulo_id: int):
    est = request.aprende_estudiante
    modulo = get_object_or_404(
        Modulo.objects.select_related('curso'),
        pk=modulo_id,
        curso__activo=True,
    )
    progreso = ProgresoEstudiante.objects.filter(
        estudiante=est, curso=modulo.curso,
    ).first()
    if not progreso:
        return redirect('/aprende/estudiante/')
    if not modulo_accesible_aula(est, modulo, progreso):
        messages.error(request, 'Este módulo aún no está disponible para ti.')
        return redirect('aprende_estudiante_curso', curso_id=modulo.curso_id)

    archivos_media = archivos_multimedia_modulo(modulo)
    secciones = secciones_modulo_aula(modulo)
    tiene_micro = modulo_tiene_microcontenidos(modulo)
    video_url = modulo.get_video_url_publica() if modulo.video_url or modulo.video_archivo else modulo.video_url
    video_media = media_desde_url(f'Video — {modulo.titulo}', video_url or '', 'video') if video_url else None
    pdf_media = (
        media_desde_url('Documento del módulo', modulo.archivo_pdf_url, 'pdf')
        if modulo.archivo_pdf_url else None
    )

    return render(request, 'aprende/estudiante_modulo.html', {
        'estudiante': est,
        'modulo': modulo,
        'secciones': secciones,
        'tiene_micro': tiene_micro,
        'archivos_media': archivos_media,
        'video_media': video_media,
        'pdf_media': pdf_media,
    })


@requiere_estudiante_aprende
def estudiante_biblioteca(request):
    est = request.aprende_estudiante
    secciones = biblioteca_agrupada_por_curso_modulo(est)
    total = sum(len(m['items']) for s in secciones for m in s['modulos'])
    return render(request, 'aprende/estudiante_biblioteca.html', {
        'estudiante': est,
        'secciones': secciones,
        'total': total,
    })


@requiere_estudiante_aprende
def estudiante_perfil(request):
    est = request.aprende_estudiante
    resumen = resumen_perfil_aula(est)

    if request.method == 'POST':
        error = actualizar_perfil_aula(request, est)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, 'Perfil actualizado.')
            return redirect('aprende_estudiante_perfil')

    ranking = resumen_ranking_aula(est)

    return render(request, 'aprende/estudiante_perfil.html', {
        'estudiante': est,
        'genero_choices': Estudiante.GENERO_CHOICES,
        'ranking': ranking,
        **resumen,
    })


def profesor_login(request):
    if es_profesor_aprende(request):
        return redirect('/aprende/profesor/')

    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username', ''),
            password=request.POST.get('password', ''),
        )
        if user and user.is_staff:
            error = (
                'Esta es la cuenta de administrador Django (/admin/). '
                'Use un usuario del portal B2B con rol Administrador o Profesor.'
            )
        elif user:
            try:
                pu = user.portal_usuario
                if pu.rol not in ('admin', 'profesor'):
                    error = (
                        f'Tu usuario tiene rol «{pu.get_rol_display()}». '
                        'Solo Administrador o Profesor pueden subir contenido en el aula web.'
                    )
                else:
                    request.session[PORTAL_SESSION_KEY] = pu.pk
                    return redirect('/aprende/profesor/')
            except PortalUsuario.DoesNotExist:
                error = 'Usuario sin organización en el portal. Pida acceso al coordinador.'
        else:
            error = 'Credenciales incorrectas.'

    return render(request, 'aprende/profesor_login.html', {'error': error})


def profesor_logout(request):
    request.session.pop(PORTAL_SESSION_KEY, None)
    return redirect('/aprende/profesor/login/')


@requiere_profesor_aprende
def profesor_cursos(request):
    org = _org_profesor(request)
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    return render(request, 'aprende/profesor_cursos.html', {
        'organizacion': org,
        'cursos': cursos,
    })


@requiere_profesor_aprende
def profesor_curso(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    modulos = Modulo.objects.filter(curso=curso).order_by('numero')
    tareas = (
        TareaCurso.objects.filter(curso=curso)
        .annotate(total_entregas=Count('entregas'), pendientes=Count('entregas', filter=Q(entregas__nota__isnull=True)))
        .order_by('orden', '-fecha_creacion')
    )
    return render(request, 'aprende/profesor_curso.html', {
        'curso': curso,
        'modulos': modulos,
        'tareas': tareas,
    })


@requiere_profesor_aprende
def profesor_modulo_nuevo(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)

    if request.method == 'POST':
        modulo, error = crear_modulo_aula(request, curso)
        if error:
            messages.error(request, error)
            return render(request, 'aprende/profesor_modulo_form.html', {
                'curso': curso,
                'modulo': None,
            })
        messages.success(request, f'Lección «{modulo.titulo}» creada.')
        return redirect(f'/aprende/profesor/modulo/{modulo.pk}/')

    return render(request, 'aprende/profesor_modulo_form.html', {
        'curso': curso,
        'modulo': None,
    })


@requiere_profesor_aprende
def profesor_modulo_editar(request, modulo_id: int):
    org = _org_profesor(request)
    modulo = get_object_or_404(Modulo.objects.select_related('curso'), pk=modulo_id, curso__cliente=org)
    archivos = ArchivoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden')

    if request.method == 'POST':
        error = actualizar_modulo_aula(request, modulo)
        if error:
            messages.error(request, error)
            return render(request, 'aprende/profesor_modulo_form.html', {
                'curso': modulo.curso,
                'modulo': modulo,
                'archivos': archivos,
            })
        messages.success(request, 'Lección actualizada.')
        return redirect(f'/aprende/profesor/modulo/{modulo.pk}/')

    return render(request, 'aprende/profesor_modulo_form.html', {
        'curso': modulo.curso,
        'modulo': modulo,
        'archivos': archivos,
    })


@requiere_profesor_aprende
def profesor_tarea_nueva(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    modulos = Modulo.objects.filter(curso=curso).order_by('numero')

    if request.method == 'POST':
        tarea, error = crear_tarea(request, curso)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, f'Tarea «{tarea.titulo}» publicada.')
            return redirect('aprende_profesor_curso', curso_id=curso.pk)

    return render(request, 'aprende/profesor_tarea_form.html', {
        'curso': curso,
        'modulos': modulos,
        'tarea': None,
    })


@requiere_profesor_aprende
def profesor_tarea_entregas(request, tarea_id: int):
    org = _org_profesor(request)
    tarea = get_object_or_404(
        TareaCurso.objects.select_related('curso'),
        pk=tarea_id,
        curso__cliente=org,
    )
    entregas = (
        EntregaTarea.objects.filter(tarea=tarea)
        .select_related('estudiante')
        .order_by('-fecha_entrega')
    )

    if request.method == 'POST':
        entrega_id = request.POST.get('entrega_id')
        entrega = entregas.filter(pk=entrega_id).first()
        if not entrega:
            messages.error(request, 'Entrega no encontrada.')
        else:
            error = calificar_entrega(request, entrega)
            if error:
                messages.error(request, error)
            else:
                messages.success(request, f'Calificación guardada para {entrega.estudiante.nombre}.')
        return redirect('aprende_profesor_tarea_entregas', tarea_id=tarea.pk)

    return render(request, 'aprende/profesor_tarea_entregas.html', {
        'tarea': tarea,
        'entregas': entregas,
    })

