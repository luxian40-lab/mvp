"""Aula web básica: estudiantes ven contenido, profesores lo suben."""

from __future__ import annotations

import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Curso, Modulo, ProgresoEstudiante, Estudiante
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario

from .acceso_modulos import (
    modulo_accesible_aula,
    modulos_visibles_aula,
    tareas_visibles_aula,
)
from .auth import es_profesor_aprende, requiere_estudiante_aprende, requiere_profesor_aprende
from .biblioteca_service import biblioteca_agrupada_por_curso_modulo
from .contenido_modulo_service import contexto_render_modulo_estudiante
from .lesson_service import (
    actualizar_modulo_aula,
    archivos_leccion_profesor,
    crear_modulo_aula,
    secciones_modulo_aula as secciones_gestion_aula,
)

from .models import EntregaTarea, TareaCurso
from .perfil_service import actualizar_perfil_aula, resumen_perfil_aula
from .calificacion_aula_service import (
    actualizar_nota_evaluacion,
    borrar_asistencia_sesion,
    calificar_matriz_tareas_curso,
    contexto_modo_calificacion,
    fechas_asistencia_marcadas,
    filas_asistencia_curso,
    filas_calificacion_curso,
    generar_excel_asistencia_curso,
    generar_excel_calificaciones_curso,
    guardar_asistencia_sesion,
    matriz_tareas_calificacion_curso,
    parse_fecha_asistencia,
    registrar_nota_manual_curso,
    slug_archivo_asistencia,
)
from .ranking_service import ranking_curso_profesor, resumen_ranking_aula
from .tarea_service import (
    actualizar_tarea,
    calificar_entrega,
    calificar_entregas_lote,
    crear_tarea,
    eliminar_tarea,
    guardar_entrega,
    guardar_respuesta_post_calificacion,
)
from .tareas_aula_service import tareas_agrupadas_estudiante, tareas_por_curso


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
    if getattr(request, 'aprende_estudiante', None):
        return redirect('/aprende/estudiante/')
    return render(request, 'aprende/inicio.html')


def handoff_desde_studio(request):
    """Recibe token firmado solo de Studio (CuentaAula) y abre sesión en Aprende.

    WhatsApp B2B no usa este puente: entra con código tras *aula*.
    Los crawlers de vista previa reciben HTML con Open Graph y no consumen el token.
    """
    from django.core import signing

    from aprende.og_preview import es_crawler_vista_previa, url_og_image_aprende
    from aprende.session_auth import VIA_STUDIO, iniciar_sesion_estudiante
    from studio.aprende_bridge import consumir_token_handoff

    if es_crawler_vista_previa(request):
        return render(request, 'aprende/link_preview.html', {
            'og_title': 'eki aprende',
            'og_description': 'Tu aula cerca del territorio. Entra desde Studio o con tu código de WhatsApp.',
            'og_image': url_og_image_aprende(request),
            'og_url': request.build_absolute_uri('/aprende/'),
        })

    token = (request.GET.get('t') or '').strip()
    if not token:
        messages.error(request, 'Enlace de acceso inválido o incompleto.')
        return redirect('/aprende/estudiante/login/')
    try:
        eid, next_path, via = consumir_token_handoff(token)
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError, ValueError):
        messages.error(
            request,
            'El enlace de Studio expiró o no es válido. Vuelve a entrar desde Studio. '
            'Si estudias por WhatsApp, escribe *aula* y usa el código.',
        )
        return redirect('/aprende/estudiante/login/')

    est = Estudiante.objects.filter(pk=eid, activo=True).first()
    if not est:
        messages.error(request, 'No encontramos tu cuenta de estudiante.')
        return redirect('/aprende/estudiante/login/')

    iniciar_sesion_estudiante(request, est.pk, via=via or VIA_STUDIO)
    return redirect(next_path)


def estudiante_login(request):
    """
    Acceso aula B2B:
    - Código OTP tras *aula* (WhatsApp) → crear clave si falta / entrar.
    - Documento + contraseña (si ya creó clave).
    - Olvidé clave → *aula* de nuevo (recuperar).
    Cuenta correo: Studio → handoff.
    """
    from aprende.acceso_whatsapp import (
        client_ip_from_request,
        next_aprende_seguro,
        verificar_codigo_web,
    )
    from aprende.credencial_service import (
        autenticar_documento_clave,
        marcar_pending_clave,
        tiene_clave,
    )

    if getattr(request, 'aprende_estudiante', None):
        return redirect(next_aprende_seguro(request.GET.get('next')))

    modo = (request.POST.get('modo') or request.GET.get('modo') or '').strip().lower()
    if modo == 'correo' or request.GET.get('from') == 'correo':
        from urllib.parse import quote

        from core.host_isolation import absolute_path

        next_url = next_aprende_seguro(request.GET.get('next'))
        studio_next = quote(f'/studio/ir-a-aprende/?next={next_url}')
        return redirect(absolute_path('studio', f'/studio/cuenta/login/?next={studio_next}', request))

    error = None
    next_url = next_aprende_seguro(request.POST.get('next') or request.GET.get('next'))
    tab = (request.POST.get('tab') or request.GET.get('tab') or 'codigo').strip().lower()
    if tab not in ('codigo', 'clave', 'olvide'):
        tab = 'codigo'
    recuperar = tab == 'olvide' or request.GET.get('recuperar') == '1'

    if request.method == 'POST':
        from aprende.session_auth import VIA_WHATSAPP, iniciar_sesion_estudiante

        accion = (request.POST.get('accion') or 'codigo').strip().lower()
        if accion == 'clave':
            tab = 'clave'
            est, msg = autenticar_documento_clave(
                request.POST.get('documento') or '',
                request.POST.get('password') or '',
            )
            if est:
                iniciar_sesion_estudiante(request, est.pk, via=VIA_WHATSAPP)
                return redirect(next_url)
            error = msg
        else:
            tab = 'codigo' if not recuperar else 'olvide'
            ip = client_ip_from_request(request)
            eid, msg = verificar_codigo_web(request.POST.get('codigo') or '', ip=ip)
            if eid:
                est = Estudiante.objects.filter(pk=eid, activo=True).first()
                if est:
                    if recuperar or not tiene_clave(est):
                        marcar_pending_clave(
                            request,
                            est.pk,
                            recuperar=bool(recuperar),
                        )
                        from urllib.parse import urlencode
                        q = urlencode({'next': next_url})
                        return redirect(f'/aprende/estudiante/clave/?{q}')
                    iniciar_sesion_estudiante(request, est.pk, via=VIA_WHATSAPP)
                    return redirect(next_url)
                error = 'No encontramos tu cuenta de estudiante.'
            else:
                error = msg

    from core.host_isolation import absolute_path

    return render(request, 'aprende/estudiante_login.html', {
        'error': error,
        'next': next_url,
        'tab': tab,
        'studio_correo_url': absolute_path(
            'studio',
            '/studio/cuenta/login/?next=/studio/ir-a-aprende/',
            request,
        ),
    })


def estudiante_crear_clave(request):
    """Tras OTP de *aula*: crear o restablecer contraseña del aula."""
    from aprende.acceso_whatsapp import next_aprende_seguro
    from aprende.credencial_service import (
        consumir_pending_clave,
        limpiar_pending_clave,
        guardar_clave,
        quiere_recuperar,
        tiene_clave,
    )
    from aprende.session_auth import VIA_WHATSAPP, iniciar_sesion_estudiante

    next_url = next_aprende_seguro(request.POST.get('next') or request.GET.get('next'))
    eid = consumir_pending_clave(request)
    if not eid:
        return redirect('/aprende/estudiante/login/?tab=olvide')

    est = Estudiante.objects.filter(pk=eid, activo=True).first()
    if not est:
        limpiar_pending_clave(request)
        return redirect('/aprende/estudiante/login/')

    error = None
    # es_reset se calcula al render; variable previa no usada
    if request.method == 'POST':
        from aprende.credencial_service import marcar_pending_clave

        marcar_pending_clave(request, eid, recuperar=quiere_recuperar(request) or tiene_clave(est))

        p1 = request.POST.get('password') or ''
        p2 = request.POST.get('password2') or ''
        if p1 != p2:
            error = 'Las contraseñas no coinciden.'
        else:
            ok, msg = guardar_clave(est, p1)
            if not ok:
                error = msg
            else:
                limpiar_pending_clave(request)
                iniciar_sesion_estudiante(request, est.pk, via=VIA_WHATSAPP)
                return redirect(next_url)

    return render(request, 'aprende/estudiante_crear_clave.html', {
        'error': error,
        'next': next_url,
        'estudiante_nombre': (est.nombre or '').split()[0] or 'Hola',
        'es_reset': quiere_recuperar(request),
    })


def estudiante_logout(request):
    from aprende.session_auth import cerrar_sesion_estudiante

    cerrar_sesion_estudiante(request)
    return redirect('/aprende/')


@requiere_estudiante_aprende
def estudiante_cursos(request):
    est = request.aprende_estudiante
    progresos = list(
        ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
        .select_related('curso', 'modulo_actual')
        .order_by('curso__nombre')
    )
    # “Continuar”: prioriza curso en progreso con módulo actual (puente con WhatsApp).
    continuar = None
    for p in progresos:
        if not p.completado and p.modulo_actual_id:
            continuar = p
            break
    if continuar is None:
        for p in progresos:
            if not p.completado:
                continuar = p
                break
    return render(request, 'aprende/estudiante_cursos.html', {
        'estudiante': est,
        'progresos': progresos,
        'continuar': continuar,
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
def estudiante_curso_ranking(request, curso_id: int):
    est = request.aprende_estudiante
    progreso = get_object_or_404(
        ProgresoEstudiante.objects.select_related('curso'),
        estudiante=est,
        curso_id=curso_id,
        curso__activo=True,
    )
    ranking = resumen_ranking_aula(est, progreso.curso)
    return render(request, 'aprende/estudiante_curso_ranking.html', {
        'estudiante': est,
        'progreso': progreso,
        'ranking': ranking,
        'curso_tab': 'ranking',
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
        accion = (request.POST.get('accion') or '').strip()
        if accion == 'respuesta' and entrega and entrega.calificada:
            error = guardar_respuesta_post_calificacion(request, entrega)
            if error:
                messages.error(request, error)
            else:
                messages.success(request, 'Comentario enviado al profesor.')
            return redirect('aprende_estudiante_tarea', tarea_id=tarea.pk)

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
    from aprende.quiz_aula_service import calificar_desde_post

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

    quiz_detalle = None
    quiz_intento = None
    if request.method == 'POST' and (request.POST.get('accion') or '') == 'quiz_modulo':
        resultado = calificar_desde_post(est, modulo, request.POST)
        if isinstance(resultado, str):
            messages.error(request, resultado)
        else:
            quiz_intento = resultado.intento
            quiz_detalle = resultado.detalle
            if resultado.intento.aprobado:
                messages.success(
                    request,
                    f'Práctica aprobada: {resultado.intento.correctas}/{resultado.intento.total}. '
                    'Para avanzar el curso en campo, escribe *listo* en WhatsApp.',
                )
            else:
                messages.warning(
                    request,
                    f'Resultado: {resultado.intento.correctas}/{resultado.intento.total}. '
                    'Puedes reintentar. El avance del programa sigue con *listo* en WhatsApp.',
                )

    ctx = contexto_render_modulo_estudiante(
        modulo,
        estudiante=est,
        quiz_intento=quiz_intento,
        quiz_detalle=quiz_detalle,
    )
    return render(request, 'aprende/estudiante_modulo.html', ctx)


@requiere_profesor_aprende
def profesor_modulo_vista_estudiante(request, modulo_id: int):
    """Vista previa de la lección tal como la ve el estudiante (sin restricción drip)."""
    from django.urls import reverse

    org = _org_profesor(request)
    modulo = get_object_or_404(
        Modulo.objects.select_related('curso'),
        pk=modulo_id,
        curso__cliente=org,
    )
    ctx = contexto_render_modulo_estudiante(modulo)
    ctx.update({
        'vista_previa_profesor': True,
        'volver_profesor_url': reverse('aprende_profesor_modulo_editar', args=[modulo.pk]),
    })
    return render(request, 'aprende/estudiante_modulo.html', ctx)


@requiere_profesor_aprende
def profesor_curso_vista_estudiante(request, curso_id: int):
    """Vista previa del curso: listado de módulos sin restricción drip."""
    from django.urls import reverse

    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    progreso = type('ProgresoPreview', (), {
        'curso': curso,
        'completado': False,
        'modulo_actual_id': modulos[0].pk if modulos else None,
    })()
    return render(request, 'aprende/estudiante_curso.html', {
        'estudiante': None,
        'progreso': progreso,
        'modulos': modulos,
        'curso_tab': 'modulos',
        'vista_previa_profesor': True,
        'volver_profesor_url': reverse('aprende_profesor_curso', args=[curso.pk]),
    })


@requiere_profesor_aprende
def profesor_tarea_vista_estudiante(request, tarea_id: int):
    """Vista previa de la tarea tal como la ve el estudiante (sin enviar)."""
    from django.urls import reverse

    org = _org_profesor(request)
    tarea = get_object_or_404(
        TareaCurso.objects.select_related('curso', 'modulo'),
        pk=tarea_id,
        curso__cliente=org,
    )
    return render(request, 'aprende/estudiante_tarea.html', {
        'estudiante': None,
        'tarea': tarea,
        'entrega': None,
        'vista_previa_profesor': True,
        'volver_profesor_url': reverse('aprende_profesor_tarea_editar', args=[tarea.pk]),
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
    progreso_rank = (
        ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
        .select_related('curso')
        .order_by('curso__orden', 'curso__nombre')
        .first()
    )
    if progreso_rank:
        ranking = resumen_ranking_aula(est, progreso_rank.curso)

    return render(request, 'aprende/estudiante_perfil.html', {
        'estudiante': est,
        'genero_choices': Estudiante.GENERO_CHOICES,
        'ranking': ranking,
        **resumen,
    })


def profesor_login(request):
    if es_profesor_aprende(request):
        pu = request.portal_usuario
        if pu.debe_cambiar_credenciales:
            return redirect('/portal/primer-acceso/')
        return redirect('/aprende/profesor/')

    error = None
    if request.method == 'POST':
        from portal.portal_auth import (
            iniciar_sesion_portal,
            portal_usuario_de_user,
            puede_acceder_aula_docente,
        )

        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)
        pu = portal_usuario_de_user(user) if user else None
        if not user or not pu:
            error = 'Credenciales incorrectas o usuario sin organización en el portal.'
        elif not user.is_active:
            error = 'Esta cuenta está desactivada. Contacta a tu administrador eki.'
        elif not puede_acceder_aula_docente(pu):
            error = (
                f'Tu usuario tiene rol «{pu.get_rol_display()}». '
                'Solo Administrador o Profesor pueden entrar al aula docente.'
            )
        elif user.is_superuser:
            error = (
                'Esta cuenta es superadmin de eki. '
                'Entrá en admin.eki.technology — no uses esa contraseña en Aprende.'
            )
        else:
            from aprende.session_auth import limpiar_estudiante_al_entrar_docente

            limpiar_estudiante_al_entrar_docente(request)
            iniciar_sesion_portal(request, pu)
            request.session.cycle_key()
            if pu.debe_cambiar_credenciales:
                return redirect('/portal/primer-acceso/')
            return redirect('/aprende/profesor/')

    return render(request, 'aprende/profesor_login.html', {'error': error})


def profesor_logout(request):
    request.session.pop(PORTAL_SESSION_KEY, None)
    return redirect('/aprende/profesor/login/')


@requiere_profesor_aprende
def profesor_cursos(request):
    org = _org_profesor(request)
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    admin_base = getattr(settings, 'ADMIN_PUBLIC_URL', 'https://admin.eki.technology').rstrip('/')
    return render(request, 'aprende/profesor_cursos.html', {
        'organizacion': org,
        'cursos': cursos,
        'admin_curso_add_url': f'{admin_base}/admin/core/curso/add/',
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
        'profesor_tab': 'contenido',
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
                'secciones': [],
                'bloques_rapidos': request.POST.get('bloques_rapidos', 'Introducción\nDesarrollo\nCierre'),
            })
        messages.success(request, f'Lección «{modulo.titulo}» creada.')
        return redirect(f'/aprende/profesor/modulo/{modulo.pk}/')

    return render(request, 'aprende/profesor_modulo_form.html', {
        'curso': curso,
        'modulo': None,
        'secciones': [],
        'bloques_rapidos': 'Introducción\nDesarrollo\nCierre',
    })


@requiere_profesor_aprende
def profesor_modulo_editar(request, modulo_id: int):
    org = _org_profesor(request)
    modulo = get_object_or_404(Modulo.objects.select_related('curso'), pk=modulo_id, curso__cliente=org)
    secciones = list(secciones_gestion_aula(modulo))

    if request.method == 'POST':
        error = actualizar_modulo_aula(request, modulo)
        archivos = archivos_leccion_profesor(modulo)
        if error:
            messages.error(request, error)
            return render(request, 'aprende/profesor_modulo_form.html', {
                'curso': modulo.curso,
                'modulo': modulo,
                'archivos': archivos,
                'secciones': secciones,
                'bloques_rapidos': request.POST.get('bloques_rapidos', ''),
            })
        messages.success(request, 'Lección actualizada.')
        return redirect(f'/aprende/profesor/modulo/{modulo.pk}/')

    return render(request, 'aprende/profesor_modulo_form.html', {
        'curso': modulo.curso,
        'modulo': modulo,
        'archivos': archivos_leccion_profesor(modulo),
        'secciones': secciones,
        'bloques_rapidos': '',
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
        accion = request.POST.get('accion', 'individual')
        if accion == 'lote':
            guardadas, error = calificar_entregas_lote(request, entregas)
            if error:
                messages.error(request, error)
            else:
                messages.success(
                    request,
                    f'Se guardaron {guardadas} calificación{"es" if guardadas != 1 else ""}.',
                )
        else:
            entrega_id = request.POST.get('entrega_id')
            entrega = entregas.filter(pk=entrega_id).first()
            if not entrega:
                messages.error(request, 'Entrega no encontrada.')
            else:
                error = calificar_entrega(request, entrega)
                if error:
                    messages.error(request, error)
                else:
                    messages.success(
                        request,
                        f'Calificación guardada para {entrega.estudiante.nombre}.',
                    )
        return redirect('aprende_profesor_tarea_entregas', tarea_id=tarea.pk)

    pendientes = sum(1 for e in entregas if not e.calificada)
    calificadas = entregas.count() - pendientes
    return render(request, 'aprende/profesor_tarea_entregas.html', {
        'tarea': tarea,
        'entregas': entregas,
        'pendientes': pendientes,
        'calificadas': calificadas,
    })


@requiere_profesor_aprende
def profesor_tarea_editar(request, tarea_id: int):
    org = _org_profesor(request)
    tarea = get_object_or_404(
        TareaCurso.objects.select_related('curso'),
        pk=tarea_id,
        curso__cliente=org,
    )
    curso = tarea.curso
    modulos = Modulo.objects.filter(curso=curso).order_by('numero')

    if request.method == 'POST':
        error = actualizar_tarea(request, tarea)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, f'Tarea «{tarea.titulo}» actualizada.')
            return redirect('aprende_profesor_tarea_editar', tarea_id=tarea.pk)

    return render(request, 'aprende/profesor_tarea_form.html', {
        'curso': curso,
        'modulos': modulos,
        'tarea': tarea,
    })


@requiere_profesor_aprende
def profesor_tarea_eliminar(request, tarea_id: int):
    if request.method != 'POST':
        return redirect('aprende_profesor_cursos')
    org = _org_profesor(request)
    tarea = get_object_or_404(
        TareaCurso.objects.select_related('curso'),
        pk=tarea_id,
        curso__cliente=org,
    )
    curso_id = tarea.curso_id
    _, msg = eliminar_tarea(tarea)
    messages.success(request, msg)
    return redirect('aprende_profesor_curso', curso_id=curso_id)


@requiere_profesor_aprende
def profesor_curso_asistencia(request, curso_id: int):
    from django.utils import timezone

    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    fecha = parse_fecha_asistencia(request.GET.get('fecha') or request.POST.get('fecha'))
    if not fecha:
        fecha = timezone.localdate()

    if request.method == 'POST':
        accion = (request.POST.get('accion') or 'guardar').strip()
        if accion == 'borrar':
            n = borrar_asistencia_sesion(curso, fecha)
            messages.success(
                request,
                f'Asistencia del {fecha.isoformat()} borrada ({n} registro(s)).',
            )
            return redirect(f'/aprende/profesor/curso/{curso.pk}/asistencia/?fecha={fecha.isoformat()}')

        presente_ids = {int(x) for x in request.POST.getlist('presente') if str(x).isdigit()}
        total_inscritos = len(filas_asistencia_curso(curso, fecha))
        n = guardar_asistencia_sesion(request, curso, fecha, presente_ids)
        messages.success(request, f'Asistencia guardada: {n} presente(s) de {total_inscritos} inscrito(s).')
        return redirect(f'/aprende/profesor/curso/{curso.pk}/asistencia/?fecha={fecha.isoformat()}')

    filas = filas_asistencia_curso(curso, fecha)
    hay_registro = any(f['registrado'] for f in filas)
    dias_marcados = fechas_asistencia_marcadas(curso)
    return render(request, 'aprende/profesor_curso_asistencia.html', {
        'curso': curso,
        'fecha': fecha,
        'filas': filas,
        'hay_registro': hay_registro,
        'dias_marcados': dias_marcados,
        'profesor_tab': 'asistencia',
        **contexto_modo_calificacion(org, curso),
    })


@requiere_profesor_aprende
def profesor_curso_asistencia_excel(request, curso_id: int):
    """Descarga Excel con la asistencia de los días marcados (o de una fecha si se indica)."""
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    fecha = parse_fecha_asistencia(request.GET.get('fecha'))
    fechas = fechas_asistencia_marcadas(curso, fecha=fecha)
    if not fechas:
        messages.warning(
            request,
            'No hay asistencia marcada para descargar.'
            + (f' (fecha {fecha.isoformat()})' if fecha else ''),
        )
        dest = f'/aprende/profesor/curso/{curso.pk}/asistencia/'
        if fecha:
            dest += f'?fecha={fecha.isoformat()}'
        return redirect(dest)

    try:
        contenido = generar_excel_asistencia_curso(curso, fechas=fechas)
    except ValueError as exc:
        messages.warning(request, str(exc))
        return redirect('aprende_profesor_asistencia', curso_id=curso.pk)

    slug = slug_archivo_asistencia(curso.nombre)
    if len(fechas) == 1:
        nombre = f'asistencia_{slug}_{fechas[0].isoformat()}.xlsx'
    else:
        nombre = f'asistencia_{slug}_{fechas[0].isoformat()}_a_{fechas[-1].isoformat()}.xlsx'

    response = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@requiere_profesor_aprende
def profesor_curso_calificaciones(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        try:
            if accion == 'matriz_lote':
                guardadas, error = calificar_matriz_tareas_curso(request, curso)
                if error:
                    messages.error(request, error)
                else:
                    messages.success(
                        request,
                        f'Se guardaron {guardadas} calificación{"es" if guardadas != 1 else ""} de tareas.',
                    )
            elif accion == 'editar_eval':
                ev = actualizar_nota_evaluacion(
                    int(request.POST.get('eval_id', 0)),
                    curso,
                    request.POST.get('nota', ''),
                )
                messages.success(request, f'Nota actualizada ({ev.get_tipo_display()}).')
            elif accion == 'nota_manual':
                res = registrar_nota_manual_curso(
                    curso,
                    int(request.POST.get('estudiante_id', 0)),
                    request.POST.get('nota', ''),
                    detalle=request.POST.get('detalle', ''),
                    peso_raw=request.POST.get('peso', ''),
                )
                prom = res['promedio']
                prom_txt = f'{prom:.1f}' if prom is not None else '—'
                messages.success(request, f'Nota registrada para {res["estudiante"].nombre}. Promedio: {prom_txt}/5.')
            else:
                messages.error(request, 'Acción no reconocida.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('aprende_profesor_calificaciones', curso_id=curso.pk)

    filas = filas_calificacion_curso(curso)
    tareas_matriz, filas_matriz = matriz_tareas_calificacion_curso(curso)
    return render(request, 'aprende/profesor_curso_calificaciones.html', {
        'curso': curso,
        'filas': filas,
        'tareas_matriz': tareas_matriz,
        'filas_matriz': filas_matriz,
        'profesor_tab': 'calificaciones',
        **contexto_modo_calificacion(org, curso),
    })


@requiere_profesor_aprende
def profesor_curso_calificaciones_excel(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    try:
        contenido = generar_excel_calificaciones_curso(curso)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('aprende_profesor_calificaciones', curso_id=curso.pk)
    nombre = f'calificaciones_{slug_archivo_asistencia(curso.nombre)}.xlsx'
    response = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@requiere_profesor_aprende
def profesor_curso_ranking(request, curso_id: int):
    org = _org_profesor(request)
    curso = get_object_or_404(Curso, pk=curso_id, cliente=org, activo=True)
    ranking = ranking_curso_profesor(org, curso)
    return render(request, 'aprende/profesor_curso_ranking.html', {
        'curso': curso,
        'ranking': ranking,
        'profesor_tab': 'ranking',
        **contexto_modo_calificacion(org, curso),
    })


def manifest_webmanifest(request):
    """PWA manifest (instalar en celular). Sin offline de cursos."""
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.http import JsonResponse

    icons = [
        {
            'src': staticfiles_storage.url('favicons/aprende-192.png'),
            'sizes': '192x192',
            'type': 'image/png',
            'purpose': 'any',
        },
        {
            'src': staticfiles_storage.url('favicons/aprende.png'),
            'sizes': '512x512',
            'type': 'image/png',
            'purpose': 'any',
        },
        {
            'src': staticfiles_storage.url('favicons/aprende.svg'),
            'sizes': 'any',
            'type': 'image/svg+xml',
            'purpose': 'any',
        },
    ]
    data = {
        'name': 'eki aprende',
        'short_name': 'aprende',
        'description': 'Tu aula cerca del territorio',
        'start_url': '/aprende/',
        'scope': '/aprende/',
        'display': 'standalone',
        'background_color': '#7A4E8E',
        'theme_color': '#7A4E8E',
        'lang': 'es-CO',
        'icons': icons,
    }
    resp = JsonResponse(data)
    resp['Content-Type'] = 'application/manifest+json'
    return resp


def service_worker(request):
    """SW mínimo en /aprende/sw.js para poder instalar (sin caché de lecciones)."""
    body = (
        "/* eki aprende PWA mínima: install only */\n"
        "self.addEventListener('install', function (e) { self.skipWaiting(); });\n"
        "self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });\n"
    )
    resp = HttpResponse(body, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/aprende/'
    resp['Cache-Control'] = 'no-cache'
    return resp

