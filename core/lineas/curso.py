"""Puerta del curso en Meta. Twilio no entra por aquí."""


def procesar_curso_meta(post_data):
    from core.views.webhook_twilio import _procesar_twilio_webhook
    return _procesar_twilio_webhook(post_data)
