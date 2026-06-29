"""eki Studio: catálogo, inscripción y onboarding de creadores (separado del aula)."""

from __future__ import annotations

import re

from django.contrib import messages
from django.shortcuts import redirect, render

from core.models import Estudiante
from core.utils_telefono import normalizar_telefono, variantes_telefono

from aprende.middleware import APRENDE_EST_SESSION_KEY

from .catalogo_service import (
    cursos_catalogo_studio,
    curso_disponible_en_studio,
    ids_cursos_inscritos,
    inscribir_estudiante_en_curso,
)


def _telefonos_coinciden(a: str, b: str) -> bool:
    va = set(variantes_telefono(a))
    vb = set(variantes_telefono(b))
    return bool(va & vb)


def _estudiante_sesion(request) -> Estudiante | None:
    return getattr(request, 'aprende_estudiante', None)


def inicio(request):
    est = _estudiante_sesion(request)
    catalogo = cursos_catalogo_studio(est)[:6]
    return render(request, 'studio/inicio.html', {
        'estudiante': est,
        'destacados': catalogo,
    })


def catalogo(request):
    est = _estudiante_sesion(request)
    inscritos = ids_cursos_inscritos(est) if est else set()
    todos = cursos_catalogo_studio(est)
    return render(request, 'studio/catalogo.html', {
        'estudiante': est,
        'cursos': todos,
        'inscritos': inscritos,
    })


def estudiante_login(request):
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
            next_url = request.GET.get('next', '/studio/cursos/')
            return redirect(next_url)
        error = (
            'Cédula o teléfono no coinciden. Use el mismo número de WhatsApp registrado.'
        )

    return render(request, 'studio/estudiante_login.html', {'error': error})


def inscribir(request, curso_id: int):
    if request.method != 'POST':
        return redirect('/studio/cursos/')

    est = _estudiante_sesion(request)
    if not est:
        request.session['studio_pending_curso'] = curso_id
        return redirect('/studio/estudiante/login/?next=/studio/cursos/')

    curso = curso_disponible_en_studio(est, curso_id)
    if not curso:
        messages.error(request, 'Ese curso no está disponible en Studio.')
        return redirect('/studio/cursos/')

    if curso.pk in ids_cursos_inscritos(est):
        messages.info(request, f'Ya estás inscrito en «{curso.nombre}».')
        return redirect(f'/aprende/estudiante/curso/{curso.pk}/')

    inscribir_estudiante_en_curso(est, curso)
    messages.success(
        request,
        f'Te inscribiste en «{curso.nombre}». Continúa en el aula virtual.',
    )
    return redirect(f'/aprende/estudiante/curso/{curso.pk}/')


def creador(request):
    """Landing para profesores / creadores (MVP: solicitud manual)."""
    return render(request, 'studio/creador.html')
