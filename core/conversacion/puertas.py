"""Puertas compartidas por las líneas Meta: opt-out, habeas, cédula, confirmación y aula.

Corren antes del menú y del curso. Los envíos y la sesión se buscan en
`core.sandbox_menu` al momento de llamar: los tests parchean ahí.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

_SI_CONFIRMA_DATOS = frozenset({
    'si', 'sí', 'todo bien', 'correcto', 'ok', 'yes', 'confirmo', 'confirmar',
})
_NO_CONFIRMA_DATOS = frozenset({
    'no', 'modificar', 'error', 'mal', 'incorrecto', 'cambiar',
})


def _menu():
    from core import sandbox_menu

    return sandbox_menu


def correr_puertas(telefono: str, body: str) -> str | None:
    """'handled' si una puerta respondió este turno; None si el turno sigue."""
    if _responder_optout(telefono, body) == 'handled':
        return 'handled'
    corte = _responder_habeas(telefono, _menu().sandbox_number(), body)
    if corte == 'handled':
        return 'handled'
    corte = _responder_cedula(telefono, _menu().sandbox_number(), body)
    if corte == 'handled':
        return 'handled'
    corte = _responder_confirmacion(telefono, _menu().sandbox_number(), body)
    if corte == 'handled':
        return 'handled'
    if _avisar_aula_es_twilio(telefono, _menu().sandbox_number(), body):
        return 'handled'
    return None


def _responder_optout(telefono: str, body: str) -> str | None:
    from core.consentimiento_wa import es_optout, registrar_optout
    from core.utils_telefono import estudiante_por_telefono

    if es_optout(body):
        est = estudiante_por_telefono(telefono)
        if est is not None and not getattr(est, 'wa_optout_fecha', None):
            registrar_optout(est)
            try:
                _menu().enviar_texto_sandbox(
                    telefono,
                    _menu().sandbox_number(),
                    'Listo. No le enviaremos más recordatorios ni plantillas por esta línea.',
                    agente='optout',
                )
            except Exception:
                logger.exception('sandbox_optout_fail')
        return 'handled'
    return None


def _habeas_listo(telefono: str) -> bool:
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is not None and not est.acepto_terminos:
        return False
    sesion = _menu()._get_or_create_sesion(telefono)
    if getattr(sesion, 'habeas_aceptado', False):
        return True
    if est is not None and est.acepto_terminos:
        sesion.habeas_aceptado = True
        sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
        return True
    return False


def alinear_ficha_con_sesion_habeas(telefono: str) -> None:
    """Si la línea ya aceptó, la ficha no se queda en habeas.

    No toca ESPERANDO_CEDULA ni CONFIRMANDO_DATOS: esa identidad sigue.
    """
    if not telefono or not _habeas_listo(telefono):
        return
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None:
        return
    campos = []
    if not est.acepto_terminos:
        from core.consentimiento_wa import registrar_optin

        est.acepto_terminos = True
        est.fecha_aceptacion_terminos = timezone.now()
        campos.extend(['acepto_terminos', 'fecha_aceptacion_terminos'])
        registrar_optin(est, 'sesion_linea')
    if (est.estado_chat or '') == 'ESPERANDO_HABEAS_DATA':
        est.estado_chat = 'ACTIVO'
        campos.append('estado_chat')
    if campos:
        est.save(update_fields=campos)


def _aceptar_habeas_y_abrir_menu(telefono: str, from_number: str, est) -> str:
    """Sin ficha no hay cédula que verificar: abre el menú."""
    sesion = _menu()._get_or_create_sesion(telefono)
    sesion.habeas_aceptado = True
    sesion.modo = _menu().MODO_MENU
    sesion.save(update_fields=['habeas_aceptado', 'modo', 'actualizado_en'])
    _menu().enviar_menu_sandbox(telefono, from_number)
    return 'handled'


def _aceptar_habeas_y_pedir_cedula(telefono: str, from_number: str, est) -> str:
    """Aceptó: pide la cédula. El menú sale cuando confirme los datos."""
    from core.consentimiento_wa import registrar_optin
    from core.habeas_respuestas import MSG_ACEPTO_CEDULA

    registrar_optin(est, 'habeas')
    est.acepto_terminos = True
    est.fecha_aceptacion_terminos = timezone.now()
    est.estado_chat = 'ESPERANDO_CEDULA'
    est.save(update_fields=['acepto_terminos', 'fecha_aceptacion_terminos', 'estado_chat'])
    sesion = _menu()._get_or_create_sesion(telefono)
    sesion.habeas_aceptado = True
    sesion.modo = _menu().MODO_CURSOS
    sesion.save(update_fields=['habeas_aceptado', 'modo', 'actualizado_en'])
    _menu().enviar_texto_sandbox(telefono, from_number, MSG_ACEPTO_CEDULA, agente='habeas_meta')
    return 'handled'


def _enviar_confirma_numero(telefono: str, from_number: str, est) -> None:
    from core.habeas_respuestas import texto_confirma_numero
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    texto = texto_confirma_numero(est, telefono)
    if sandbox_via_meta():
        enviar_meta_botones(
            telefono,
            texto,
            [('si', 'Sí'), ('no', 'No')],
            agente_evento='habeas_meta',
        )
        return
    _menu().enviar_texto_sandbox(
        telefono, from_number,
        f"{texto}\n\nEscriba *sí* o *no*.",
        agente='habeas_meta',
    )


def _responder_cedula(telefono: str, from_number: str, body: str) -> str | None:
    """None si no está en cédula. 'handled' si esta vuelta fue la cédula."""
    import re

    from core.habeas_respuestas import MSG_ACEPTO_CEDULA, MSG_CEDULA_NO_COINCIDE
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None or (est.estado_chat or '') != 'ESPERANDO_CEDULA':
        return None
    t = (body or '').strip().lower()
    if _menu()._es_boton_inicio_flujo(body) or t in ('continuemos', 'continuar'):
        _menu().enviar_texto_sandbox(telefono, from_number, MSG_ACEPTO_CEDULA, agente='habeas_meta')
        return 'handled'
    cedula_input = re.sub(r'[\s.\-]', '', (body or '').strip())
    if cedula_input and cedula_input == (est.cedula or ''):
        est.estado_chat = 'CONFIRMANDO_DATOS'
        est.save(update_fields=['estado_chat'])
        _menu()._set_modo(_menu()._get_or_create_sesion(telefono), _menu().MODO_CURSOS)
        _enviar_confirma_numero(telefono, from_number, est)
        return 'handled'
    _menu().enviar_texto_sandbox(telefono, from_number, MSG_CEDULA_NO_COINCIDE, agente='habeas_meta')
    return 'handled'


def abrir_tras_confirmar(est, telefono: str, from_number: str) -> None:
    """El sí de los datos abre el menú; en la línea de curso lineal, el curso que no ha empezado."""
    from core.lineas.variante import perfil_de

    sesion = _menu()._get_or_create_sesion(telefono)
    sesion.habeas_aceptado = True
    sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
    if perfil_de().curso_directo:
        from core.inicio_curso import primera_entrega_al_confirmar

        texto = primera_entrega_al_confirmar(est)
        if texto:
            _menu()._set_modo(sesion, _menu().MODO_CURSOS)
            _menu().enviar_texto_sandbox(telefono, from_number, texto, agente='sandbox_cursos')
            return
    _menu()._set_modo(sesion, _menu().MODO_MENU)
    _menu().enviar_menu_sandbox(telefono, from_number)


def _responder_confirmacion(telefono: str, from_number: str, body: str) -> str | None:
    """None si no está confirmando. 'handled' si esta vuelta fue la verificación."""
    from core.habeas_respuestas import MSG_DATOS_NO
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None or (est.estado_chat or '') != 'CONFIRMANDO_DATOS':
        return None
    t = (body or '').strip().lower()
    if t in _SI_CONFIRMA_DATOS:
        est.estado_chat = 'ACTIVO'
        est.estado_onboarding = 'completado'
        est.save(update_fields=['estado_chat', 'estado_onboarding'])
        abrir_tras_confirmar(est, telefono, from_number)
        return 'handled'
    if t in _NO_CONFIRMA_DATOS:
        _menu().enviar_texto_sandbox(telefono, from_number, MSG_DATOS_NO, agente='habeas_meta')
        return 'handled'
    _enviar_confirma_numero(telefono, from_number, est)
    return 'handled'


def _responder_habeas(telefono: str, from_number: str, body: str) -> str | None:
    """None si ya puede ver el menú. 'handled' si esta vuelta fue solo habeas."""
    from core.utils_telefono import estudiante_por_telefono

    t = (body or '').strip().lower()
    est = estudiante_por_telefono(telefono)
    if t in ('continuemos', 'continuar') and est is not None and not est.acepto_terminos:
        from core.sandbox_canal import enviar_sandbox_habeas

        enviar_sandbox_habeas(telefono)
        return 'handled'
    if t in ('acepto', 'aceptó', 'si', 'sí', 'de acuerdo') and (
        est is None or not est.acepto_terminos
    ):
        if est is None:
            return _aceptar_habeas_y_abrir_menu(telefono, from_number, est)
        return _aceptar_habeas_y_pedir_cedula(telefono, from_number, est)
    if _habeas_listo(telefono):
        return None
    if t in ('acepto', 'aceptó', 'si', 'sí', 'de acuerdo'):
        if est is None:
            return _aceptar_habeas_y_abrir_menu(telefono, from_number, est)
        return _aceptar_habeas_y_pedir_cedula(telefono, from_number, est)
    if t in ('no_acepto', 'no acepto', 'no'):
        _menu().enviar_texto_sandbox(
            telefono,
            from_number,
            "Sin la autorización no podemos abrir la formación ni la asesoría.\n\n"
            "Cuando quiera, escriba *acepto*.",
            agente='sandbox_menu',
        )
        return 'handled'
    from core.sandbox_canal import enviar_sandbox_habeas

    enviar_sandbox_habeas(telefono)
    return 'handled'


def _avisar_aula_es_twilio(telefono: str, from_number: str, body: str) -> bool:
    """*aula* en Meta no emite código: el aula vive en la línea Twilio."""
    from aprende.acceso_whatsapp import mensaje_pide_acceso_aula

    if not mensaje_pide_acceso_aula(body):
        return False
    from core.lineas.variante import perfil_de

    if not perfil_de().menu:
        aviso = (
            'El *aula* se pide por la otra línea. Escriba *aula* allá para recibir el código. '
            'Esta línea es solo del curso (Formador y Compañero). '
            'Escriba *continuar* si ya está inscrito.'
        )
    else:
        aviso = (
            'El *aula* (eki Aprende) se pide por la línea de cursos. '
            'Escriba *aula* allá para recibir el código. '
            'En esta línea están *Formación* y *Asesoría*.'
        )
    try:
        _menu().enviar_texto_sandbox(
            telefono,
            from_number,
            aviso,
            agente='sandbox_menu',
        )
    except Exception:
        logger.exception('sandbox_aula_aviso_fail')
    return True
