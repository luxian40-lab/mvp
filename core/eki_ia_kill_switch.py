"""
Kill switch LLM de eki.ia (línea comercial / Nat).

Cuando está activo: no se llama al LLM; el bot responde con reglas + RAG/catálogo
(Plan B) y se registra EventoIA con regla ``llm_disabled``.

Activación (cualquiera basta):
1. Env global ``EKI_IA_LLM_DISABLED=1`` (alias ``EKI_NAT_LLM_DISABLED``) → settings.
2. Flag por organización ``Cliente.desactivar_llm_comercial`` (admin, sin redeploy de código).
"""

from __future__ import annotations

from django.conf import settings


def eki_ia_llm_kill_activo(*, cliente=None) -> bool:
    """True = no llamar LLM en la línea comercial (eki.ia / Nat)."""
    if bool(getattr(settings, 'EKI_IA_LLM_DISABLED', False)):
        return True
    if cliente is not None and bool(getattr(cliente, 'desactivar_llm_comercial', False)):
        return True
    return False


def motivo_kill_switch(*, cliente=None) -> str:
    """Código corto para metadata / regla_aplicada."""
    if bool(getattr(settings, 'EKI_IA_LLM_DISABLED', False)):
        return 'llm_disabled_global'
    if cliente is not None and bool(getattr(cliente, 'desactivar_llm_comercial', False)):
        return 'llm_disabled_org'
    return 'llm_disabled'
