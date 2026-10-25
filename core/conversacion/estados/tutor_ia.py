"""Estado esperando_respuesta_tutor_ia. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    from core.gamificacion import PerfilGamificacion
    print(f"🎓 Evaluando respuesta del Facilitador (legacy tutor IA)")
    ctx = estudiante.contexto_temporal or {}
    modulo_id = ctx.get('modulo_id')
    pregunta_tutor = ctx.get('pregunta_tutor', '')
    intentos = ctx.get('intentos_tutor', 0)

    # Detectar si el usuario quiere omitir el tutor
    msg_lower = msg_body.strip().lower()
    palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']

    if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        # Audio no pudo ser transcrito — pedir reintento
        texto_respuesta = (
            "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
            "o escríbeme tu respuesta.\n\n"
            "Si prefiere continuar sin responder, pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
        )
    elif any(p in msg_lower for p in palabras_skip):
        # Usuario quiere seguir sin responder al tutor
        estudiante.contexto_temporal = None
        estudiante.estado_onboarding = 'completado'
        estudiante.save()
        print(f"⏭️ Profesor Gerónimo omitido por usuario")

        # Si dijo "menu", retomar curso (B2B) o menú sandbox
        if msg_lower in ['menu', 'menú']:
            from core.flujo_whatsapp_b2b import respuesta_tras_keyword_menu
            texto_respuesta = respuesta_tras_keyword_menu(
                estudiante, estudiante.nombre, msg_body
            )
        else:
            # v1.9.6: NO llamar continuar_leccion — el skip solo cierra el tutor.
            # El estudiante ya tiene el contenido del módulo. Cuando lo estudie
            # y escriba "listo" de nuevo, avanzará por el flujo normal (estado=completado).
            texto_respuesta = (
                "👍 Sin problema.\n\nContinúa revisando el contenido del módulo 👆\n\n"
                "Cuando termine, pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
            )
            print(f"✅ v1.9.6: Skip Gerónimo sin avance automático", flush=True)
    else:
        from core.tutor_ia_modulo import evaluar_respuesta_modulo
        from core.models import Modulo

        try:
            modulo = Modulo.objects.get(id=modulo_id) if modulo_id else None
        except Modulo.DoesNotExist:
            modulo = None

        if modulo:
            aprobado, feedback = evaluar_respuesta_modulo(
                modulo, msg_body, pregunta_tutor,
                estudiante_nombre=estudiante.nombre or "Estudiante"
            )

            # v1.9.8: Siempre 1 sola interacción — feedback y continúa
            estudiante.contexto_temporal = None
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            if aprobado:
                perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                perfil.agregar_puntos(5, "Respuesta correcta - Profesor Gerónimo")
                texto_respuesta = (
                    f"{feedback}\n\n💰 *+5 puntos bonus* por tu respuesta 💪\n\n"
                    "Continúa revisando el módulo 👆\nCuando termines, Pulse continuar, para seguir aprendiendo.\n\n"
                    + _MARCADOR_CONTINUEMOS
                )
                print(f"✅ v1.9.8: Gerónimo aprobado — 1 interacción", flush=True)
            else:
                texto_respuesta = (
                    f"{feedback}\n\n✅ *¡Buen esfuerzo!* Sigue estudiando el módulo 👆\n\n"
                    "Cuando termine, pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
                )
                print(f"✅ v1.9.8: Gerónimo incorrecto — feedback y continúa", flush=True)
        else:
            estudiante.contexto_temporal = None
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            # v1.9.6: Solo enviar feedback, NO auto-avanzar
            texto_respuesta = (
                "✅ Gracias por tu respuesta!\n\nContinúa revisando el módulo 👆\n"
                "Cuando termine, pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
            )
            print(f"✅ v1.9.6: Gerónimo sin módulo — feedback sin auto-avance", flush=True)
    return Respuesta(texto=texto_respuesta)
