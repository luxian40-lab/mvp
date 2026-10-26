"""Sin estado de agente: detecta el intent y responde con plantilla, o con la IA si quedan preguntas. Movido tal cual del cuerpo del webhook (fase D7)."""

from core.conversacion.contexto import CORTAR, Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    LECCION_EN_CURSO = contexto.locales['LECCION_EN_CURSO']
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_sid = contexto.msg_sid
    telefono_limpio = contexto.telefono_limpio
    from core.eventos_ia import detectar_intent_con_evento
    from core.response_templates import get_response_for_intent

    _prog = None
    try:
        _prog = estudiante.progresos.order_by('-fecha_inicio').first()
    except Exception:
        pass
    intent = detectar_intent_con_evento(
        msg_body,
        estudiante=estudiante,
        curso=_prog.curso if _prog else None,
        modulo=_prog.modulo_actual if _prog else None,
    )
    print(f"🎯 Intent detectado: {intent}")

    # Intent especial: corregir datos → redirigir al flujo de corrección
    if intent == 'corregir_datos':
        estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
        estudiante.save()
        texto_respuesta = (
            "📝 *Corrección de Datos*\n\n"
            "Puedes corregir cualquiera de tus datos.\n\n"
            "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
            "1️⃣ *nombre:* Tu nombre completo\n"
            "2️⃣ *municipio:* Tu municipio\n"
            "3️⃣ *departamento:* Tu departamento\n"
            "4️⃣ *documento:* Tipo y número (CC, TI, CE, PP)\n"
            "5️⃣ *edad:* Tu edad\n"
            "6️⃣ *genero:* M, F, Otro, NR\n\n"
            "📝 _Ejemplos:_\n"
            "_nombre: María García López_\n"
            "_municipio: Bogotá_\n"
            "_edad: 35_\n\n"
            "👉 Escribe *menú* cuando termines"
        )
    # Si hay un intent conocido, usar template
    elif intent != 'desconocido':
        texto_respuesta = get_response_for_intent(
            intent, 
            estudiante.nombre,
            estudiante_id=estudiante.id,
            mensaje_original=msg_body
        )
        print(f"✅ Respuesta desde template: {texto_respuesta[:50]}...")
        if texto_respuesta == LECCION_EN_CURSO:
            from core.sandbox_canal import descartar_reaccion_espera

            descartar_reaccion_espera(telefono_limpio)
            return CORTAR
    else:
        # Solo si no hay intent, usar IA para preguntas sobre agricultura
        # 🛑 ANTI-ABUSO IA: Verificar preguntas restantes
        print(f"🤖 Usando IA para pregunta sobre agricultura")
        if estudiante.preguntas_ia_restantes <= 0:
            # Freno de mano: IA pausada
            from core.avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo
            _prog_ia = estudiante.progresos.order_by('-fecha_inicio').first()
            _curso_ia = _prog_ia.curso if _prog_ia else None
            texto_respuesta = (
                "[MULTI_MSG]⚠️ *Has agotado tus preguntas libres a la IA para este modulo.*\n\n"
                "Para desbloquear mas preguntas, necesitas responder "
                "la pregunta de evaluacion del modulo actual."
                "[SEP]"
                + resolver_cta_listo(estudiante, _curso_ia, CTX_FIN_ENTREGA_MODULO)
            )
        else:
            try:
                from core.sandbox_canal import poner_reaccion_espera
                from core.ai_assistant import responder_con_ia

                poner_reaccion_espera(telefono_limpio, msg_sid)
                texto_respuesta = responder_con_ia(msg_body, telefono_limpio)
                # Restar pregunta usada (anti-abuso silencioso)
                estudiante.preguntas_ia_restantes = max(0, estudiante.preguntas_ia_restantes - 1)
                estudiante.save()
                print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
            except Exception as e:
                print(f"❌ Error IA: {e}, usando respuesta genérica")
                texto_respuesta = "Disculpa, tengo problemas técnicos. Vuelve a escribir tu mensaje para continuar."
    return Respuesta(texto=texto_respuesta)
