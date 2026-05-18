"""Envío del balance GEI por WhatsApp."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_balance_gei_whatsapp(ficha, estudiante=None) -> bool:
    """
    Persiste resultado, arma mensaje y envía por Twilio.
    Returns True si se envió, False si no había teléfono o está deshabilitado.
    """
    if not getattr(settings, "GEI_RESULTADO_WHATSAPP_ENABLED", True):
        return False

    est = estudiante or ficha.estudiante
    tel = (getattr(est, "telefono", None) or "").strip()
    if not tel:
        logger.warning("Sin teléfono para balance GEI estudiante_id=%s", getattr(est, "pk", "?"))
        return False

    from formulario.calculadora import generar_mensaje_resultado_whatsapp, persistir_resultado_gei

    try:
        persistir_resultado_gei(ficha)
        texto = generar_mensaje_resultado_whatsapp(ficha)
        if not tel.startswith("+"):
            tel = f"+{tel}"
        from core.utils import enviar_whatsapp_twilio

        enviar_whatsapp_twilio(tel, texto)
        return True
    except Exception as e:
        logger.exception("Error enviando balance GEI por WhatsApp: %s", e)
        return False
