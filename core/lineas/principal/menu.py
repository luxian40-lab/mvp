"""Menú de la línea principal y carrusel de formación.

Los envíos y la sesión se buscan en `core.sandbox_menu` al momento de llamar:
los tests parchean ahí.
"""
from __future__ import annotations

import logging

from core.lineas.principal.cursos import _tiene_curso_abierto

logger = logging.getLogger(__name__)


def _menu():
    from core import sandbox_menu

    return sandbox_menu


def _linea() -> str:
    from core.sandbox_canal import phone_id_de_salida

    return phone_id_de_salida()


def _olvidar_eleccion(telefono: str) -> None:
    from core.lineas.principal.confirmar_curso import olvidar

    olvidar(telefono, _linea())


def aplicar_ruta_catalogo(decision, sesion, body: str) -> bool:
    """True si el turno es del catálogo (ver, info, sí o otro)."""
    from core.cursos_generales import payload_catalogo
    from core.lineas.principal.confirmar_curso import cuerpo_catalogo

    cuerpo = cuerpo_catalogo(decision.telefono_usuario, _linea(), body, sesion.modo)
    if sesion.modo not in (_menu().MODO_MENU, _menu().MODO_FORMACION, _menu().MODO_CURSOS):
        return False
    if not payload_catalogo(cuerpo):
        return False
    decision.action = 'catalogo_general'
    decision.texto_menu = (cuerpo or '').strip()
    return True


def _curso_abierto(telefono: str, curso_id: int) -> bool:
    from core.models import Estudiante, ProgresoEstudiante
    from core.nati import normalizar_telefono_whatsapp

    est = Estudiante.objects.filter(telefono=normalizar_telefono_whatsapp(telefono)).first()
    if est is None:
        return False
    return ProgresoEstudiante.objects.filter(
        estudiante=est, curso_id=curso_id, completado=False,
    ).exists()


def _preguntar_curso(telefono: str, from_number: str, clave: str) -> None:
    from core.cursos_generales import evaluar_catalogo
    from core.lineas.principal.confirmar_curso import BOTON_OTRO, BOTON_SI, ID_OTRO, recordar, texto_pregunta
    from core.lineas.variante import perfil_de
    from core.planes_linea import resolver_plan
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    visto = evaluar_catalogo(telefono, clave)
    if not visto.get('ok'):
        return
    curso_id = int(visto['curso_id'])
    recordar(telefono, _linea(), curso_id)
    _menu()._set_modo(_menu()._get_or_create_sesion(telefono), _menu().MODO_FORMACION)
    cursos_mes = resolver_plan(telefono).cursos_mes if perfil_de().planes else 1
    texto = texto_pregunta(visto.get('nombre') or '', cursos_mes or 1)
    botones = [(f'si_curso_{curso_id}', BOTON_SI), (ID_OTRO, BOTON_OTRO)]
    if sandbox_via_meta():
        enviar_meta_botones(telefono, texto, botones, agente_evento='sandbox_formacion')
        return
    _menu().enviar_texto_sandbox(
        telefono,
        from_number,
        texto + '\n\nEscriba *sí* para arrancar o *otro* para ver los cursos.',
        agente='sandbox_formacion',
    )


def _interceptar_confirmacion(telefono: str, from_number: str, dato: dict) -> bool:
    """True si este turno ya respondió y no hay que inscribir."""
    from core.cursos_generales import evaluar_catalogo
    from core.lineas.principal.confirmar_curso import decidir, leer, olvidar
    from core.lineas.variante import perfil_de

    accion = dato.get('accion') or ''
    clave = str(dato.get('clave') or '')
    curso_id = int(clave[6:]) if clave.startswith('curso_') and clave[6:].isdigit() else None
    visto = evaluar_catalogo(telefono, clave) if accion == 'ver' else {}
    if accion == 'ver' and visto.get('ok'):
        curso_id = int(visto['curso_id'])
    puede = bool(visto.get('ok'))
    abierto = bool(curso_id is not None and _curso_abierto(telefono, curso_id))
    pendiente = leer(telefono, _linea())
    paso = decidir(
        accion,
        confirma=perfil_de().confirmar_curso,
        puede=puede,
        curso_id=curso_id,
        abierto=abierto,
        pendiente=pendiente,
    )
    if paso == 'preguntar':
        _preguntar_curso(telefono, from_number, clave)
        return True
    if paso == 'repetir':
        elegido = int(pendiente) if pendiente and pendiente.isdigit() else curso_id
        if elegido is not None:
            _preguntar_curso(telefono, from_number, f'curso_{elegido}')
            return True
    if accion == 'confirmar':
        olvidar(telefono, _linea())
    return False


def enviar_menu_sandbox(telefono_usuario: str, from_number: str) -> dict:
    from core.lineas.variante import TEXTO_LINEA_MODO_TWILIO, perfil_de
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    _olvidar_eleccion(telefono_usuario)

    if not perfil_de().menu:
        # Sin carrusel ni menú Meta: el curso sigue en el camino lineal.
        return _menu().enviar_texto_sandbox(
            telefono_usuario, from_number, TEXTO_LINEA_MODO_TWILIO, agente='sandbox_cursos',
        )
    plan = _menu().resolver_plan(telefono_usuario)
    if not plan.activo:
        return _menu().enviar_texto_sandbox(telefono_usuario, from_number, _menu().TEXTO_SIN_PLAN, agente='sandbox_plan')
    botones = []
    if plan.incluye_cursos:
        botones.append(('formacion', 'Formación'))
    if plan.incluye_asesor:
        from core.lineas.oferta import filas_agentes

        if filas_agentes(telefono_usuario):
            botones.append(('asesoria', 'Asesoría'))
    if not plan.incluye_cursos and _tiene_curso_abierto(telefono_usuario):
        botones.append(('seguir', 'Seguir mi curso'))
    texto = _menu().texto_menu_plan(plan)
    if sandbox_via_meta():
        return enviar_meta_botones(
            telefono_usuario,
            texto,
            botones,
            agente_evento='sandbox_menu',
        )
    palabras = ' o '.join(f"*{titulo.lower()}*" for _, titulo in botones)
    return _menu().enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"{texto}\n\nEscriba {palabras}.",
    )


def enviar_catalogo_formacion(telefono_usuario: str, from_number: str) -> None:
    """De 2 a 10 cursos: carrusel. Más de 10: lista. Ver curso pide confirmar."""
    _olvidar_eleccion(telefono_usuario)
    from core.cursos_generales import (
        filas_de_tarjetas,
        modo_catalogo,
        paginas_carrusel,
        paginas_lista,
        tarjetas_catalogo,
    )
    from core.sandbox_canal import (
        enviar_meta_botones,
        enviar_meta_carrusel,
        enviar_meta_lista,
        sandbox_via_meta,
    )

    tarjetas = tarjetas_catalogo(telefono_usuario)
    cuerpo = (
        "Deslice los cursos de eki. "
        "*Más información* abre la página del programa."
    )
    if not tarjetas:
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            "Aún no hay cursos de formación publicados.\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if sandbox_via_meta() and modo_catalogo(len(tarjetas)) == 'lista':
        aviso = "Elija el curso en la lista."
        for i, pagina in enumerate(paginas_lista(filas_de_tarjetas(tarjetas))):
            intro = aviso if i == 0 else "Siguen más cursos."
            enviar_meta_lista(
                telefono_usuario,
                intro,
                'Ver cursos',
                pagina,
                texto_respaldo=intro,
                agente_evento='sandbox_formacion',
            )
        return
    if sandbox_via_meta() and len(tarjetas) >= 2:
        fallo = None
        for i, pagina in enumerate(paginas_carrusel(tarjetas)):
            intro = cuerpo if i == 0 else "Siguen más cursos. Deslice."
            resultado = enviar_meta_carrusel(
                telefono_usuario,
                intro,
                pagina,
                agente_evento='sandbox_formacion',
            )
            if not resultado.get('success'):
                fallo = resultado.get('response')
                break
        if fallo is None:
            return
        logger.warning('sandbox_carrusel_fallback %s', fallo)
    if sandbox_via_meta() and len(tarjetas) == 1:
        tarjeta = tarjetas[0]
        enviar_meta_botones(
            telefono_usuario,
            tarjeta['body'],
            tarjeta['botones'],
            agente_evento='sandbox_formacion',
        )
        return
    lineas = [cuerpo, '']
    for tarjeta in tarjetas:
        ver = tarjeta['botones'][0][0]
        lineas.append(f"{tarjeta['body']}\nEscriba {ver} para empezar.")
    _menu().enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        '\n\n'.join(lineas),
        agente='sandbox_formacion',
    )


def responder_catalogo_general(telefono_usuario: str, from_number: str, body: str) -> None:
    from core.cursos_generales import inscribir_en_catalogo, item_catalogo, payload_catalogo

    dato = payload_catalogo(body) or {}
    item = item_catalogo(dato.get('clave') or '')
    if item is None:
        from core.cursos_generales import resolver_curso_menu

        curso_linea = resolver_curso_menu(dato.get('clave') or '', telefono_usuario)
        if curso_linea is not None:
            item = {
                'clave': dato.get('clave') or '',
                'nombre': curso_linea.nombre,
                'url': '',
            }
    if item is None:
        enviar_catalogo_formacion(telefono_usuario, from_number)
        return
    if dato.get('accion') == 'info':
        from core.cursos_generales import _url_de_curso
        from core.sandbox_canal import enviar_meta_url, sandbox_via_meta

        destino = str(item.get('url') or '') or _url_de_curso(item.get('nombre') or '')
        if sandbox_via_meta() and destino.startswith('https://'):
            enviar_meta_url(
                telefono_usuario,
                item['nombre'],
                destino,
                boton='Más información',
                agente_evento='sandbox_formacion',
            )
            return
        if destino.startswith('https://'):
            _menu().enviar_texto_sandbox(
                telefono_usuario,
                from_number,
                destino,
                agente='sandbox_formacion',
            )
            return
        logger.warning('sandbox_formacion_sin_url clave=%s nombre=%s', item.get('clave'), item.get('nombre'))
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            (item.get('nombre') or 'Este programa') + '.\n\n_*menu* para volver._',
            agente='sandbox_formacion',
        )
        return
    if _interceptar_confirmacion(telefono_usuario, from_number, dato):
        return
    resultado = inscribir_en_catalogo(telefono_usuario, item['clave'])
    if resultado.get('error') == 'otra_empresa':
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{resultado.get('nombre') or 'Ese curso'}* no está en esta línea.\n\n"
            "Escriba *formacion* para ver los cursos de su empresa.\n\n"
            "_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if resultado.get('error') == 'sin_plan_cursos':
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            _menu().TEXTO_PLAN_SIN_CURSOS if _menu().resolver_plan(telefono_usuario).activo else _menu().TEXTO_SIN_PLAN,
            agente='sandbox_plan',
        )
        return
    if resultado.get('error') == 'cupo_mes':
        cupo = resultado.get('cursos_mes') or 1
        cuantos = 'uno por mes' if cupo == 1 else f'{cupo} por mes'
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"Este mes ya eligió *{resultado.get('nombre_activo') or 'un curso'}*.\n\n"
            f"Su plan incluye cursos {cuantos} (de eki o de su organización). "
            "El próximo mes puede escoger otro.\n\n"
            "Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]\n\n"
            "_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if not resultado.get('ok'):
        _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{item['nombre']}* todavía no está publicado en esta línea.\n\n"
            f"Puede ver la ficha:\n{item['url']}\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    sesion = _menu()._get_or_create_sesion(telefono_usuario)
    _menu()._set_modo(sesion, _menu().MODO_CURSOS)
    _menu().enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"Quedó en *{resultado['nombre']}*.\n\n"
        "Pulse continuar, para seguir aprendiendo. No se borra el avance de sus otros cursos.\n\n[SEND_BUTTON:continuemos]\n\n"
        "_*menu* para volver._",
        agente='sandbox_formacion',
    )
