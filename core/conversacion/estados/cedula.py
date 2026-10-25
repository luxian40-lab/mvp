"""Estado ESPERANDO_CEDULA. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging
import re

from django.conf import settings

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    # Limpiar input del usuario
    cedula_input = re.sub(r'[\s\.\-]', '', msg_body.strip())
    msg_lower_cedula = msg_body.strip().lower()

    # Detectar "ayuda" → crear ticket de soporte
    if msg_lower_cedula in ['ayuda', 'help', 'soporte']:
        from core.models import SolicitudSoporte
        solicitud = SolicitudSoporte.objects.create(
            estudiante=estudiante,
            mensaje_original=f"Ayuda en verificación de cédula - no coincide con registros",
            keyword_usada='ayuda_cedula',
            asunto='Problema con verificación de cédula',
            prioridad='media'
        )
        texto_respuesta = (
            f"🆘 *Ticket de Soporte #{solicitud.id}*\n\n"
            f"Hola {estudiante.nombre}, hemos registrado tu solicitud.\n\n"
            "📝 Un asesor revisará tu caso y te contactará pronto.\n"
            "🕐 *Tiempo de respuesta:* menos de 24 horas.\n\n"
            "Si recuerdas tu cédula, puedes intentar de nuevo escribiéndola aquí."
        )
    # Comparar con la cédula sanitizada en BD
    elif cedula_input == estudiante.cedula:
        estudiante.estado_chat = 'CONFIRMANDO_DATOS'
        estudiante.save()

        # Enviar confirmación con datos + botones (5 variables)
        org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
        from core.whatsapp_service import enviar_confirmacion_datos
        resultado = enviar_confirmacion_datos(
            msg_from,
            estudiante.nombre,
            f"{estudiante.tipo_documento} {estudiante.cedula}",
            org_nombre,
            edad=estudiante.edad,
            municipio=estudiante.municipio,
        )
        if resultado.get('success'):
            return CORTAR  # Template enviado

        # Fallback texto plano
        texto_respuesta = (
            "✅ *¡Cédula verificada!*\n\n"
            "Tus datos registrados:\n\n"
            f"👤 *Nombre:* {estudiante.nombre}\n"
            f"🆔 *Documento:* {estudiante.tipo_documento} {estudiante.cedula}\n"
            f"📍 *Municipio:* {estudiante.municipio or 'No registrado'}\n"
            f"🏢 *Organización:* {org_nombre}\n"
            f"🎂 *Edad:* {estudiante.edad or 'No registrada'}\n"
            f"👫 *Género:* {estudiante.get_genero_display() if estudiante.genero else 'No registrado'}\n\n"
            "*¿Tus datos están correctos?*\n\n"
            "👉 Escribe *Sí* si todo está bien\n"
            "👉 Escribe *No* si hay un error"
        )
    else:
        texto_respuesta = (
            "❌ *Cédula no coincide*\n\n"
            "El número que ingresaste no coincide con "
            "nuestros registros.\n\n"
            "Por favor verifica y escribe tu cédula nuevamente "
            "(solo números, sin puntos ni espacios).\n\n"
            "👉 Ejemplo: 1234567890\n\n"
            "Si crees que hay un error, escribe *ayuda*"
        )

    try:
        from twilio.rest import Client as TwilioClient
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
        client_tw = TwilioClient(account_sid, auth_token)
        destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
        client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
        WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
    except Exception as e:
        logger.error(f"❌ Error enviando validación 2FA: {e}")
        import traceback; traceback.print_exc()
    return CORTAR  # CORTAR EJECUCIÓN
