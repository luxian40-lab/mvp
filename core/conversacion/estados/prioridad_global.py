"""Prioridad global tras el habeas: normaliza *listo* con curso abierto, flujo de corrección, formulario GEI, retomar B2B y menú. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estado_chat = contexto.estado_chat
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    # ============================================================
    # PRIORIDAD GLOBAL: menu + corregir datos (post-habeas)
    # Debe funcionar en cualquier estado del bot una vez el usuario
    # aceptó términos.
    # ============================================================
    from core.correccion_datos import (
        construir_menu_principal_texto,
        es_keyword_correccion,
        es_keyword_menu,
        estudiante_en_flujo_correccion,
        iniciar_flujo_correccion,
        normalizar_texto,
        procesar_flujo_correccion,
    )
    texto_norm = normalizar_texto(msg_body)

    # Si el usuario quedó en estado legacy por PQRS/corrección, normalizar
    # chat a ACTIVO para que "listo" retome el curso. NUNCA pisar estados
    # de agentes (Darío / facilitadora / tutor): eso saltaba la evaluación.
    _ESTADOS_AGENTE_NO_FORZAR = frozenset({
        'completado',
        'esperando_respuesta_asistente',
        'esperando_respuesta_reto',
        'esperando_respuesta_modulo',
        'esperando_respuesta_pregunta_abierta_final',
        'esperando_seleccion_curso',
        'curso_finalizado',
    })
    from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_estados
    if not _emp_pausa_estados():
        _ESTADOS_AGENTE_NO_FORZAR = _ESTADOS_AGENTE_NO_FORZAR | {
            'esperando_codigo_empleabilidad',
        }
    if texto_norm in {"listo", "continuar"}:
        from core.models import ProgresoEstudiante
        if ProgresoEstudiante.objects.filter(
            estudiante=estudiante, completado=False, curso__activo=True
        ).exists():
            cambios = []
            if estudiante.estado_chat != "ACTIVO":
                estudiante.estado_chat = "ACTIVO"
                cambios.append("estado_chat")
            if estudiante.estado_onboarding not in _ESTADOS_AGENTE_NO_FORZAR:
                estudiante.estado_onboarding = "completado"
                cambios.append("estado_onboarding")
            if cambios:
                estudiante.save(update_fields=cambios)

    if estudiante.acepto_terminos:
        from core.utils import enviar_whatsapp_twilio
        if estudiante_en_flujo_correccion(estudiante):
            texto_respuesta = procesar_flujo_correccion(estudiante, msg_body)
            enviar_whatsapp_twilio(msg_from, texto_respuesta)
            return CORTAR

        if es_keyword_correccion(texto_norm):
            texto_respuesta = iniciar_flujo_correccion(estudiante)
            enviar_whatsapp_twilio(msg_from, texto_respuesta)
            return CORTAR

        # GEI / formulario activo: tiene prioridad sobre *hola*/*menú*/retomar B2B.
        # Si no, "hola" (keyword retomar) saltaba la ficha y dejaba la sesión pegada.
        try:
            from core.puentes import debe_usar_agente_formulario
            if estado_chat == 'ACTIVO' and debe_usar_agente_formulario(estudiante):
                from core.puentes import manejar_mensaje_formulario
                texto_respuesta = manejar_mensaje_formulario(estudiante, msg_body)
                enviar_whatsapp_twilio(msg_from, texto_respuesta)
                WhatsappLog.objects.create(
                    telefono=telefono_limpio,
                    mensaje=(texto_respuesta or '')[:500],
                    tipo='SENT',
                )
                return CORTAR
        except Exception:
            logger.exception('Agente formulario GEI (prioridad temprana) omitido')

        from core.flujo_whatsapp_b2b import (
            es_estudiante_b2b,
            es_keyword_retomar,
            salir_seleccion_curso_legacy,
        )
        from core.response_templates import get_response_for_intent

        if es_estudiante_b2b(estudiante) and es_keyword_retomar(texto_norm):
            salir_seleccion_curso_legacy(estudiante)
            texto_respuesta = get_response_for_intent(
                'continuar_leccion',
                estudiante.nombre,
                estudiante_id=estudiante.id,
                mensaje_original=msg_body,
            )
            enviar_whatsapp_twilio(msg_from, texto_respuesta)
            return CORTAR

        if es_keyword_menu(texto_norm):
            texto_respuesta = construir_menu_principal_texto(estudiante)
            enviar_whatsapp_twilio(msg_from, texto_respuesta)
            return CORTAR
    return None
