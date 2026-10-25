"""Cursos ya empezados en la línea principal: seguir, elegir cuál, entrar.

Los envíos y la sesión se buscan en `core.sandbox_menu` al momento de llamar:
los tests parchean ahí.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _menu():
    from core import sandbox_menu

    return sandbox_menu


def _abiertos_del_mes(telefono: str):
    from core.planes_linea import cursos_iniciados_en_el_mes

    return list(
        cursos_iniciados_en_el_mes(telefono).filter(completado=False).select_related('estudiante', 'curso')[:6]
    )


def _entrar_en_progreso(telefono: str, from_number: str, progreso) -> None:
    est = progreso.estudiante
    ctx = dict(est.contexto_temporal or {})
    ctx['curso_activo_id'] = progreso.curso_id
    est.contexto_temporal = ctx
    est.save(update_fields=['contexto_temporal'])
    _menu()._set_modo(_menu()._get_or_create_sesion(telefono), _menu().MODO_CURSOS)
    from core.lineas.variante import perfil_de

    extra = ''
    if perfil_de().asesores and _menu().resolver_plan(telefono).incluye_asesor:
        extra = "\nEscriba *asesoria* si quiere hablar con el asesor.\n"
    _menu().enviar_texto_sandbox(
        telefono,
        from_number,
        f"Seguimos *{progreso.curso.nombre}*.\n\n"
        "Pulse continuar, para seguir aprendiendo. No se reinicia su avance.\n"
        f"{extra}\n_*menu* para volver._\n\n[SEND_BUTTON:continuemos]",
        agente='sandbox_cursos',
    )


def _preguntar_cual_curso(telefono: str, from_number: str, abiertos) -> None:
    from core.sandbox_canal import enviar_meta_lista, sandbox_via_meta

    _menu()._set_modo(_menu()._get_or_create_sesion(telefono), _menu().MODO_FORMACION)
    lineas = [f"{i}. {p.curso.nombre}" for i, p in enumerate(abiertos, start=1)]
    texto = (
        "¿Cuál curso sigue?\n\n"
        + "\n".join(lineas)
        + "\n\nElija en la lista o escriba el número. No se reinicia su avance.\n\n"
        "_*menu* para volver._"
    )
    filas = [
        (f"seguir_{p.curso_id}", (p.curso.nombre or 'Curso')[:24], 'Continuar donde iba')
        for p in abiertos[:10]
    ]
    if sandbox_via_meta():
        enviar_meta_lista(
            telefono, texto, 'Sus cursos', filas, texto_respaldo=texto, agente_evento='sandbox_cursos'
        )
        return
    _menu().enviar_texto_sandbox(telefono, from_number, texto, agente='sandbox_cursos')


def ofrecer_cursos_en_curso(telefono: str, from_number: str) -> bool:
    """Si este mes ya va en uno o dos cursos, no abre el carrusel de cero."""
    abiertos = _abiertos_del_mes(telefono)
    if not abiertos:
        return False
    if len(abiertos) == 1:
        _entrar_en_progreso(telefono, from_number, abiertos[0])
    else:
        _preguntar_cual_curso(telefono, from_number, abiertos)
    return True


def _tiene_curso_abierto(telefono: str) -> bool:
    """Curso ya empezado y sin completar. No abre el catálogo."""
    _est, progresos = _progresos_del_telefono(telefono)
    return any(not p.completado for p in progresos)


def _progresos_del_telefono(telefono: str):
    from core.models import Estudiante, ProgresoEstudiante

    tel = _menu().normalizar_telefono_whatsapp(telefono)
    est = Estudiante.objects.filter(telefono=tel).first()
    if est is None:
        return None, []
    progresos = list(
        ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
        .select_related('curso')
        .order_by('curso__orden', 'curso__nombre', 'id')
    )
    return est, progresos


def entrar_cursos_inscrito(telefono_usuario: str, from_number: str) -> bool:
    """Continúa cursos ya inscritos. No abre demo Riendas ni crea estudiantes."""
    from core.sandbox_canal import canal_sandbox_si_meta

    est, progresos = _progresos_del_telefono(telefono_usuario)
    abiertos = [p for p in progresos if not p.completado]
    sesion = _menu()._get_or_create_sesion(telefono_usuario)

    if not progresos:
        _menu()._set_modo(sesion, _menu().MODO_MENU)
        with canal_sandbox_si_meta():
            _menu().enviar_menu_sandbox(telefono_usuario, from_number)
        return True

    if not abiertos:
        _menu()._set_modo(sesion, _menu().MODO_MENU)
        nombres = ', '.join((p.curso.nombre or 'Curso')[:60] for p in progresos[:4])
        with canal_sandbox_si_meta():
            _menu().enviar_texto_sandbox(
                telefono_usuario,
                from_number,
                f"Ya completó su curso en eki ({nombres}).\n\n"
                "Si necesita reactivar avance, pida a su coordinador.\n\n"
                "_*menu* para volver._",
                agente='sandbox_cursos',
            )
        return True

    _menu()._set_modo(sesion, _menu().MODO_CURSOS)
    if len(abiertos) == 1:
        p = abiertos[0]
        ctx = dict(est.contexto_temporal or {})
        ctx['curso_activo_id'] = p.curso_id
        est.contexto_temporal = ctx
        est.save(update_fields=['contexto_temporal'])
        texto = (
            f"Seguimos *{p.curso.nombre}*.\n\n"
            "Pulse continuar, para seguir aprendiendo. "
            "No se reinicia su avance.\n\n"
            "_*menu* para volver._"
        )
    else:
        lineas = []
        for i, p in enumerate(abiertos[:6], start=1):
            lineas.append(f"{i}. {p.curso.nombre}")
        texto = (
            "Tiene más de un curso activo:\n"
            + "\n".join(lineas)
            + "\n\nPulse continuar, para seguir aprendiendo, y elija cuál seguir. "
            "No se reinicia su avance.\n\n_*menu* para volver._"
        )
    with canal_sandbox_si_meta():
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            texto + "\n\n[SEND_BUTTON:continuemos]",
            agente='sandbox_cursos',
        )
    return True


def bootstrap_cursos_sandbox(telefono_usuario: str, from_number: str) -> bool:
    """Alias: continuar inscritos (ya no arranca demo Riendas)."""
    return _menu().entrar_cursos_inscrito(telefono_usuario, from_number)


def _sticky_cursos_solo_si_inscrito_demo(telefono: str, curso) -> None:
    """Compat tests antiguos: no dejar modo cursos sin progreso real."""
    _est, progresos = _progresos_del_telefono(telefono)
    sesion = _menu()._get_or_create_sesion(telefono)
    if not any(not p.completado for p in progresos):
        _menu()._set_modo(sesion, _menu().MODO_MENU)
