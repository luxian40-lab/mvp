"""Número que no es Estudiante: prospecto B2B (carrusel demo, empresa, correo, ventas). Siempre corta. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from django.conf import settings
from django.utils import timezone

from core.conversacion.contexto import CORTAR, Contexto, Respuesta

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    post_data = contexto.locales['post_data']
    telefono_limpio = contexto.telefono_limpio
    # Verificar si ya es un prospecto B2B existente
    from core.models import ProspectoB2B
    from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

    prospecto = None
    try:
        prospecto = ProspectoB2B.objects.get(telefono=telefono_limpio)
    except ProspectoB2B.DoesNotExist:
        pass

    btn_payload = (
        post_data.get('ButtonPayload')
        or post_data.get('ButtonText')
        or ''
    )
    if intentar_flujo_prospecto_carrusel(
        telefono=telefono_limpio,
        msg_from=msg_from,
        msg_body=msg_body,
        button_payload=str(btn_payload),
    ):
        if not prospecto:
            ProspectoB2B.objects.get_or_create(
                telefono=telefono_limpio,
                defaults={
                    'mensaje_original': (msg_body or btn_payload or 'carrusel_demo')[:500],
                    'origen': 'whatsapp_bot',
                },
            )
        return CORTAR

    msg_lower = msg_body.strip().lower()
    
    if prospecto:
        # Prospecto existente - procesar su respuesta
        if prospecto.esperando_email:
            # Validar si parece un email
            import re as re_email
            email_match = re_email.search(r'[\w.+-]+@[\w-]+\.[\w.]+', msg_body)
            if email_match:
                prospecto.email = email_match.group(0)
                prospecto.esperando_email = False
                prospecto.fecha_ultimo_contacto = timezone.now()
                prospecto.save()
                
                # Notificar al equipo de ventas por email
                try:
                    from django.core.mail import send_mail
                    send_mail(
                        subject=f"🏢 Nuevo Lead B2B - {prospecto.empresa or prospecto.telefono}",
                        message=f"Nuevo prospecto capturado por el bot:\n\nTeléfono: {prospecto.telefono}\nEmpresa: {prospecto.empresa}\nEmail: {prospecto.email}\nMensaje: {prospecto.mensaje_original}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[getattr(settings, 'EMAIL_SOPORTE', 'comunidad.educativa@eki.com.co')],
                        fail_silently=True
                    )
                except Exception:
                    pass
                
                texto_respuesta = (
                    "✅ *¡Perfecto!*\n\n"
                    f"Hemos registrado tu correo: *{prospecto.email}*\n\n"
                    "Nuestro equipo de ventas te contactará muy pronto "
                    "para contarte todo sobre las capacitaciones de eki. 🚜\n\n"
                    "¡Gracias por tu interés! 🌱"
                )
            else:
                texto_respuesta = "📧 Por favor envía un correo electrónico válido (ej: nombre@empresa.com)"
        elif msg_lower in ['1', 'empresa', 'eki para mi empresa']:
            prospecto.esperando_email = True
            prospecto.fecha_ultimo_contacto = timezone.now()
            prospecto.save()
            texto_respuesta = (
                "🏢 *¡Excelente!*\n\n"
                "Nos encantaría ayudar a capacitar a tu equipo.\n\n"
                "📧 Por favor envíanos tu *correo electrónico* "
                "y un asesor de ventas te contactará:\n\n"
                "👉 Ejemplo: juan@miempresa.com"
            )
        elif msg_lower in ['3', 'ayuda', 'soy estudiante', 'estudiante']:
            texto_respuesta = (
                "🙋‍♂️ *¡Entendido!*\n\n"
                "Si eres estudiante y cambiaste de número, "
                "por favor contacta a tu coordinador o escribe a:\n\n"
                "📧 comunidad.educativa@eki.com.co\n\n"
                "Incluye tu nombre completo y número de cédula para que podamos ayudarte."
            )
        elif msg_lower in ['2', 'web', 'sitio', 'visitar sitio web', 'www.eki.com.co']:
            texto_respuesta = (
                "🌐 Conoce más en *www.eki.com.co*\n\n"
                "Si quiere ver programas de ejemplo, escriba *4*.\n"
                "Si es empresa, escriba *1*."
            )
        elif msg_lower in ['4', 'programas', 'programa', 'catalogo', 'catálogo']:
            if intentar_flujo_prospecto_carrusel(
                telefono=telefono_limpio,
                msg_from=msg_from,
                msg_body='programas',
                button_payload='',
            ):
                return CORTAR
            from core.whatsapp_service import enviar_mensaje_ventas
            enviar_mensaje_ventas(msg_from)
            return CORTAR
        else:
            from core.whatsapp_service import enviar_mensaje_ventas
            enviar_mensaje_ventas(msg_from)
            return CORTAR
        
        # Enviar respuesta al prospecto
        try:
            from twilio.rest import Client as TwilioClient
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
            client_tw = TwilioClient(account_sid, auth_token)
            destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
        except Exception as e:
            print(f"❌ Error enviando a prospecto: {e}")
        return CORTAR
    
    else:
        # Nuevo prospecto - crear y enviar mensaje de ventas (o carrusel si keyword)
        ProspectoB2B.objects.create(
            telefono=telefono_limpio,
            mensaje_original=msg_body,
            origen='whatsapp_bot'
        )
        if intentar_flujo_prospecto_carrusel(
            telefono=telefono_limpio,
            msg_from=msg_from,
            msg_body=msg_body,
            button_payload=str(btn_payload),
        ):
            logger.info(f"🏢 Nuevo prospecto + carrusel demo: {telefono_limpio}")
            return CORTAR
        from core.whatsapp_service import enviar_mensaje_ventas
        enviar_mensaje_ventas(msg_from)
        logger.info(f"🏢 Nuevo prospecto B2B capturado: {telefono_limpio}")
        return CORTAR
