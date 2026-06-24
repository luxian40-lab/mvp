"""Aula web básica: estudiantes ven contenido, profesores lo suben."""

from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth import authenticate
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Curso, Modulo, ProgresoEstudiante
from core.models_extras import ArchivoModulo
from core.utils_telefono import normalizar_telefono, variantes_telefono
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario

from .auth import es_profesor_aprende, requiere_estudiante_aprende, requiere_profesor_aprende
from .middleware import APRENDE_EST_SESSION_KEY


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


@requiere_estudiante_aprende
def estudiante_curso(request, curso_id: int):
    est = request.aprende_estudiante
    progreso = get_object_or_404(
        ProgresoEstudiante.objects.select_related('curso'),
        estudiante=est,
        curso_id=curso_id,
        curso__activo=True,
    )
    modulos = Modulo.objects.filter(curso=progreso.curso).order_by('numero')
    return render(request, 'aprende/estudiante_curso.html', {
        'estudiante': est,
        'progreso': progreso,
        'modulos': modulos,
    })


@requiere_estudiante_aprende
def estudiante_modulo(request, modulo_id: int):
    est = request.aprende_estudiante
    modulo = get_object_or_404(
        Modulo.objects.select_related('curso'),
        pk=modulo_id,
        curso__activo=True,
    )
    if not ProgresoEstudiante.objects.filter(estudiante=est, curso=modulo.curso).exists():
        return redirect('/aprende/estudiante/')

    archivos = (
        ArchivoModulo.objects.filter(modulo=modulo, activo=True)
        .order_by('orden', 'titulo')
    )
    video_url = modulo.get_video_url_publica() if modulo.video_url or modulo.video_archivo else modulo.video_url

    return render(request, 'aprende/estudiante_modulo.html', {
        'estudiante': est,
        'modulo': modulo,
        'archivos': archivos,
        'video_url': video_url,
        'youtube_id': _youtube_embed_id(video_url or ''),
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
    return render(request, 'aprende/profesor_curso.html', {
        'curso': curso,
        'modulos': modulos,
    })


@requiere_profesor_aprende
def profesor_modulo_nuevo(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)

    if request.method == 'POST':
        max_num = Modulo.objects.filter(curso=curso).aggregate(m=Max('numero'))['m'] or 0
        modulo = Modulo.objects.create(
            curso=curso,
            numero=int(max_num) + 1,
            titulo=request.POST.get('titulo', 'Nueva lección').strip() or 'Nueva lección',
            descripcion=request.POST.get('descripcion', '').strip(),
            contenido=request.POST.get('contenido', '').strip() or 'Contenido pendiente.',
            video_url=request.POST.get('video_url', '').strip() or None,
            archivo_pdf_url=request.POST.get('archivo_pdf_url', '').strip() or None,
        )
        _guardar_archivo_modulo(request, modulo)
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
        modulo.titulo = request.POST.get('titulo', modulo.titulo).strip()
        modulo.descripcion = request.POST.get('descripcion', '').strip()
        modulo.contenido = request.POST.get('contenido', '').strip()
        modulo.video_url = request.POST.get('video_url', '').strip() or None
        modulo.archivo_pdf_url = request.POST.get('archivo_pdf_url', '').strip() or None
        modulo.save()
        _guardar_archivo_modulo(request, modulo)
        messages.success(request, 'Lección actualizada.')
        return redirect(f'/aprende/profesor/modulo/{modulo.pk}/')

    return render(request, 'aprende/profesor_modulo_form.html', {
        'curso': modulo.curso,
        'modulo': modulo,
        'archivos': archivos,
    })


def _guardar_archivo_modulo(request, modulo: Modulo) -> None:
    archivo = request.FILES.get('archivo_subir')
    if not archivo:
        return
    tipo = request.POST.get('tipo_archivo', 'pdf')
    if tipo not in dict(ArchivoModulo.TIPOS):
        tipo = 'pdf'
    ArchivoModulo.objects.create(
        modulo=modulo,
        tipo=tipo,
        titulo=request.POST.get('titulo_archivo', archivo.name)[:200],
        descripcion=request.POST.get('descripcion_archivo', '')[:500],
        archivo=archivo,
    )
