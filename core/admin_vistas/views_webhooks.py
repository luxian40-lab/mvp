"""
Wrapper module para aislar endpoints de webhooks.
Mantiene compatibilidad importando implementaciones existentes.
"""

from core.views import bot_comercial_webhook, whatsapp_webhook

__all__ = ["whatsapp_webhook", "bot_comercial_webhook"]
