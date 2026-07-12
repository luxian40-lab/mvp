"""eki Studio: catálogo, cuentas, creadores y pagos."""

from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Estudiante
from core.utils_telefono import normalizar_telefono, variantes_telefono

from aprende.middleware import APRENDE_EST_SESSION_KEY

from .catalogo_service import (
    cursos_catalogo_studio,
    curso_disponible_en_studio,
    ids_cursos_inscritos,
    inscribir_estudiante_en_curso,
)
from .cuenta_service import (
    autenticar_cuenta_aula,
    cerrar_sesion_cuenta,
    cuenta_desde_request,
    iniciar_sesion_cuenta,
    registrar_cuenta_aula,
)
from .models import CreadorStudio, PublicacionStudio
from .creador_service import actualizar_precio_publicacion, publicar_curso_creador
from .pago_service import (
    contexto_widget_wompi,
    crear_intento_pago,
    curso_requiere_pago,
    marcar_pago_aprobado,
    precio_curso_studio,
    procesar_evento_wompi,
    tiene_acceso_curso,
    validar_checksum_webhook,
    wompi_integracion_activa,
    wompi_llave_publica,
    wompi_permite_simulacion,
)


def _telefonos_coinciden(a: str, b: str) -> bool:
    va = set(variantes_telefono(a))
    vb = set(variantes_telefono(b))
    return bool(va & vb)


def _estudiante_sesion(request) -> Estudiante | None:
    return getattr(request, 'aprende_estudiante', None)


def _cuenta_o_redirect(request, next_url='/studio/cursos/'):
    cuenta = cuenta_desde_request(request)
    if cuenta:
        return cuenta
    return redirect(f'/studio/cuenta/login/?next={next_url}')


def inicio(request):
    est = _estudiante_sesion(request)
    catalogo = cursos_catalogo_studio(est)[:6]
    return render(request, 'studio/inicio.html', {
        'estudiante': est,
        'cuenta': cuenta_desde_request(request),
        'destacados': catalogo,
    })


def catalogo(request):
    est = _estudiante_sesion(request)
    cuenta = cuenta_desde_request(request)
    inscritos = ids_cursos_inscritos(est) if est else set()
    todos = cursos_catalogo_studio(est)
    for c in todos:
        c.precio_studio = precio_curso_studio(c)
    return render(request, 'studio/catalogo.html', {
        'estudiante': est,
        'cuenta': cuenta,
        'cursos': todos,
        'inscritos': inscritos,
    })


def cuenta_registro(request):
    if cuenta_desde_request(request):
        return redirect('/studio/cursos/')

    error = None
    if request.method == 'POST':
        cuenta, error = registrar_cuenta_aula(
            email=request.POST.get('email', ''),
            password=request.POST.get('password', ''),
            nombre=request.POST.get('nombre', ''),
        )
        if cuenta:
            iniciar_sesion_cuenta(request, cuenta)
            messages.success(request, 'Cuenta creada. ¡Explora el catálogo!')
            return redirect(request.GET.get('next', '/studio/cursos/'))

    return render(request, 'studio/cuenta_registro.html', {'error': error})


def cuenta_login(request):
    if cuenta_desde_request(request):
        return redirect(request.GET.get('next', '/studio/cursos/'))

    error = None
    if request.method == 'POST':
        cuenta, error = autenticar_cuenta_aula(
            email=request.POST.get('email', ''),
            password=request.POST.get('password', ''),
        )
        if cuenta:
            iniciar_sesion_cuenta(request, cuenta)
            pending = request.session.pop('studio_pending_curso', None)
            if pending:
                return redirect(f'/studio/inscribir/{pending}/')
            return redirect(request.GET.get('next', '/studio/cursos/'))

    return render(request, 'studio/cuenta_login.html', {'error': error})


def cuenta_logout(request):
    cerrar_sesion_cuenta(request)
    logout(request)
    return redirect('/studio/')


def estudiante_login_whatsapp(request):
    """Legacy: cédula + teléfono (programas B2B por WhatsApp)."""
    if _estudiante_sesion(request):
        return redirect('/studio/cursos/')

    error = None
    if request.method == 'POST':
        cedula = re.sub(r'[\s\.\-]', '', request.POST.get('cedula', '').strip())
        tel = normalizar_telefono(request.POST.get('telefono', ''))
        est = Estudiante.objects.filter(cedula=cedula, activo=True).first()
        if est and _telefonos_coinciden(est.telefono, tel):
            request.session[APRENDE_EST_SESSION_KEY] = est.pk
            pending = request.session.pop('studio_pending_curso', None)
            if pending:
                curso = curso_disponible_en_studio(est, int(pending))
                if curso and curso.pk not in ids_cursos_inscritos(est):
                    inscribir_estudiante_en_curso(est, curso)
                    messages.success(request, f'Te inscribiste en «{curso.nombre}».')
                    return redirect(f'/aprende/estudiante/curso/{curso.pk}/')
            return redirect(request.GET.get('next', '/studio/cursos/'))
        error = 'Cédula o teléfono no coinciden con el registro de WhatsApp.'

    return render(request, 'studio/estudiante_login_whatsapp.html', {'error': error})


def estudiante_login(request):
    return redirect('/studio/cuenta/login/' + (
        f'?next={request.GET["next"]}' if request.GET.get('next') else ''
    ))


def inscribir(request, curso_id: int):
    if request.method != 'POST':
        return redirect('/studio/cursos/')

    cuenta = cuenta_desde_request(request)
    est = _estudiante_sesion(request)
    if not cuenta and not est:
        request.session['studio_pending_curso'] = curso_id
        return redirect(f'/studio/cuenta/login/?next=/studio/cursos/')

    if cuenta:
        est = cuenta.estudiante

    curso = curso_disponible_en_studio(est, curso_id)
    if not curso:
        messages.error(request, 'Ese curso no está disponible en Studio.')
        return redirect('/studio/cursos/')

    if curso.pk in ids_cursos_inscritos(est):
        messages.info(request, f'Ya estás inscrito en «{curso.nombre}».')
        return redirect(f'/aprende/estudiante/curso/{curso.pk}/')

    if curso_requiere_pago(curso):
        if not cuenta:
            request.session['studio_pending_curso'] = curso_id
            messages.info(request, 'Para cursos de pago necesitas una cuenta con correo.')
            return redirect(f'/studio/cuenta/login/?next=/studio/cursos/')
        if not tiene_acceso_curso(cuenta, curso):
            acceso = crear_intento_pago(cuenta, curso)
            return redirect(f'/studio/pagar/{acceso.wompi_referencia}/')

    inscribir_estudiante_en_curso(est, curso)
    messages.success(
        request,
        f'Te inscribiste en «{curso.nombre}». Continúa en Aprende.',
    )
    return redirect(f'/aprende/estudiante/curso/{curso.pk}/')


def pagar_curso(request, referencia: str):
    from .models import AccesoCursoPagado

    acceso = get_object_or_404(
        AccesoCursoPagado.objects.select_related('cuenta', 'curso'),
        wompi_referencia=referencia,
    )
    cuenta = cuenta_desde_request(request)
    if not cuenta or cuenta.pk != acceso.cuenta_id:
        return redirect(f'/studio/cuenta/login/?next=/studio/pagar/{referencia}/')

    if acceso.estado == AccesoCursoPagado.ESTADO_APROBADO:
        return redirect(f'/aprende/estudiante/curso/{acceso.curso_id}/')

    redirect_url = request.build_absolute_uri(f'/studio/pagar/{referencia}/resultado/')
    widget = None
    if wompi_integracion_activa():
        widget = contexto_widget_wompi(acceso, redirect_url=redirect_url)

    return render(request, 'studio/pagar_curso.html', {
        'acceso': acceso,
        'curso': acceso.curso,
        'wompi_activo': wompi_integracion_activa(),
        'wompi_public_key': wompi_llave_publica(),
        'wompi_widget': widget,
        'permite_simulacion': wompi_permite_simulacion(),
    })


def pagar_curso_resultado(request, referencia: str):
    """Landing tras redirect de Wompi: muestra estado e inscripción si ya aprobó el webhook."""
    from .models import AccesoCursoPagado

    acceso = get_object_or_404(
        AccesoCursoPagado.objects.select_related('cuenta', 'curso'),
        wompi_referencia=referencia,
    )
    cuenta = cuenta_desde_request(request)
    if not cuenta or cuenta.pk != acceso.cuenta_id:
        return redirect(f'/studio/cuenta/login/?next=/studio/pagar/{referencia}/resultado/')

    if acceso.estado == AccesoCursoPagado.ESTADO_APROBADO:
        messages.success(request, f'Pago aprobado. ¡Bienvenido a «{acceso.curso.nombre}»!')
        return redirect(f'/aprende/estudiante/curso/{acceso.curso_id}/')

    return render(request, 'studio/pagar_resultado.html', {
        'acceso': acceso,
        'curso': acceso.curso,
    })


@require_POST
def pagar_curso_confirmar(request, referencia: str):
    """Simulación solo en entornos sin Wompi real (o DEBUG)."""
    from .models import AccesoCursoPagado

    if not wompi_permite_simulacion():
        return HttpResponseForbidden('Simulación deshabilitada: use Wompi.')

    acceso = get_object_or_404(AccesoCursoPagado, wompi_referencia=referencia)
    cuenta = cuenta_desde_request(request)
    if not cuenta or cuenta.pk != acceso.cuenta_id:
        return HttpResponseForbidden()

    if acceso.estado != AccesoCursoPagado.ESTADO_APROBADO:
        marcar_pago_aprobado(
            acceso,
            wompi_transaccion_id=f'MVP-{referencia[:16]}',
            metadata={'origen': 'confirmar_mvp'},
        )
        messages.success(request, f'Pago confirmado. ¡Bienvenido a «{acceso.curso.nombre}»!')
    return redirect(f'/aprende/estudiante/curso/{acceso.curso_id}/')


@csrf_exempt
@require_POST
def webhook_wompi(request):
    """
    Webhook Wompi: validar checksum y marcar AccesoCursoPagado.
    URL: /studio/webhook/wompi/ — evento transaction.updated APPROVED.
    """
    import json

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    checksum = (
        request.headers.get('X-Event-Checksum')
        or request.META.get('HTTP_X_EVENT_CHECKSUM', '')
    )
    if not validar_checksum_webhook(payload, checksum):
        return HttpResponse(status=401)

    acceso = procesar_evento_wompi(payload)
    if acceso is None and not (
        (payload.get('data') or {}).get('transaction', {}).get('reference')
        or payload.get('data', {}).get('reference')
    ):
        return HttpResponse(status=400)

    return HttpResponse(status=200)


def creador(request):
    creador_perfil = None
    if request.user.is_authenticated:
        creador_perfil = CreadorStudio.objects.filter(user=request.user).first()
    publicaciones = 0
    if creador_perfil:
        publicaciones = PublicacionStudio.objects.filter(creador=creador_perfil).count()
    return render(request, 'studio/creador.html', {
        'creador_perfil': creador_perfil,
        'publicaciones': publicaciones,
        'cuenta': cuenta_desde_request(request),
    })


@login_required(login_url='/studio/creador/registro/')
def creador_panel(request):
    creador_perfil = get_object_or_404(CreadorStudio, user=request.user)
    error = None

    if request.method == 'POST':
        accion = request.POST.get('accion', 'crear')
        if accion == 'crear':
            curso, err = publicar_curso_creador(
                creador_perfil,
                nombre=request.POST.get('nombre', ''),
                descripcion=request.POST.get('descripcion', ''),
                precio_cop=request.POST.get('precio_cop', '0'),
                publicar_en_catalogo=request.POST.get('publicar') == 'on',
            )
            if err:
                error = err
            elif curso:
                if curso.visible_en_studio:
                    messages.success(request, f'Curso «{curso.nombre}» publicado en el catálogo.')
                else:
                    messages.success(
                        request,
                        f'Curso «{curso.nombre}» creado. '
                        f'{"Perfil en revisión: " if not creador_perfil.activo else ""}'
                        f'aparecerá en catálogo cuando esté activo y marcado como publicar.',
                    )
                return redirect('/studio/creador/panel/')
        elif accion == 'precio':
            pub, err = actualizar_precio_publicacion(
                creador_perfil,
                int(request.POST.get('publicacion_id', 0) or 0),
                precio_cop=request.POST.get('precio_cop', '0'),
                publicar_en_catalogo=(
                    True if request.POST.get('publicar') == 'on'
                    else False if request.POST.get('publicar') == 'off'
                    else None
                ),
            )
            if err:
                error = err
            elif pub:
                messages.success(request, f'Precio actualizado: ${pub.precio_cop} COP.')
                return redirect('/studio/creador/panel/')

    pubs = PublicacionStudio.objects.filter(creador=creador_perfil).select_related('curso')
    return render(request, 'studio/creador_panel.html', {
        'creador': creador_perfil,
        'publicaciones': pubs,
        'error': error,
    })


def creador_registro(request):
    if request.user.is_authenticated and CreadorStudio.objects.filter(user=request.user).exists():
        return redirect('/studio/creador/panel/')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        nombre = request.POST.get('nombre_publico', '').strip()
        bio = request.POST.get('bio', '').strip()

        cuenta, err = registrar_cuenta_aula(email=email, password=password, nombre=nombre)
        if cuenta and not err:
            CreadorStudio.objects.create(
                user=cuenta.user,
                nombre_publico=nombre,
                bio=bio,
                activo=False,
            )
            iniciar_sesion_cuenta(request, cuenta)
            messages.success(
                request,
                'Solicitud recibida. El equipo eki activará tu espacio de creador pronto.',
            )
            return redirect('/studio/creador/panel/')
        error = err or 'No se pudo crear la cuenta.'

    return render(request, 'studio/creador_registro.html', {'error': error})
