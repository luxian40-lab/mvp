"""
App proxy admin + fachada de IA comercial (Nat).

La lógica de runtime (routing, webhook, RAG) vive principalmente en ``core``
(``core.bot_comercial``, ``core.nati``, ``core.nat_router``, …).
Esta app agrupa modelos proxy en Jazzmin para operación comercial.
"""

from django.apps import AppConfig


class AgentsCommercialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents_commercial'
    verbose_name = 'IA Comercial (Nat)'
