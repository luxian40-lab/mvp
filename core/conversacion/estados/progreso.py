"""Estado esperando_respuesta_progreso. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    from core.gamificacion import PerfilGamificacion
    print(f"�‍🏫 Evaluando respuesta de María (Revisión de Progreso)")
    ctx = estudiante.contexto_temporal or {}
    pregunta_tutor = ctx.get('pregunta_tutor', '')
    modulos_info = ctx.get('modulos_info', '')
    intentos = ctx.get('intentos_tutor', 0)
    modulos_reto_ids = ctx.get('modulos_reto_ids', [])
    progreso_id = ctx.get('progreso_id')
    es_reto_final = ctx.get('es_reto_final', False)

    def _activar_reto_despues_de_maria(prefijo=""):
        from core.lineas.reto import activar_reto_despues_de_maria
        return activar_reto_despues_de_maria(
            estudiante, prefijo, progreso_id, modulos_reto_ids, es_reto_final,
        )

    # Detectar si el usuario quiere omitir
    msg_lower = msg_body.strip().lower()
    palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']

    if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        texto_respuesta = (
            "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
            "o escríbeme tu respuesta.\n\n"
            "Si prefiere continuar sin responder, pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
        )
    elif any(p in msg_lower for p in palabras_skip):
        print(f"⏭️ María omitida por usuario → activando reto")

        if msg_lower in ['menu', 'menú']:
            from core.flujo_whatsapp_b2b import respuesta_tras_keyword_menu
            texto_respuesta = respuesta_tras_keyword_menu(
                estudiante, estudiante.nombre, msg_body
            )
        else:
            texto_respuesta = _activar_reto_despues_de_maria("👍 Perfecto, pasemos al reto de la facilitadora.")
    else:
        from core.tutor_ia_modulo import evaluar_respuesta_progreso

        resuelta, feedback = evaluar_respuesta_progreso(
            modulos_info, msg_body, pregunta_tutor,
            estudiante_nombre=estudiante.nombre or "Estudiante"
        )

        if resuelta:
            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            perfil.agregar_puntos(3, "Revisión de progreso - María")
            texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n💰 *+3 puntos* por tu reflexión 💪")
            print(f"✅ María resuelta — activando reto", flush=True)
        else:
            texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n✅ *Buena reflexión!*")
            print(f"✅ María evaluada — activando reto", flush=True)
    return Respuesta(texto=texto_respuesta)
