"""Enrutado WhatsApp: Nat comercial vs bot educativo.

El webhook compartido (`/webhook/whatsapp/`) decide el canal por el número destino (To).
Debe incluir la línea global, sandbox y cada `Cliente.numero_whatsapp_nat`.
"""

from __future__ import annotations

from django.conf import settings

from core.nati import normalizar_telefono_whatsapp


def _sandbox_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '14155238886') or '14155238886'
    )


def _global_comercial_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_WHATSAPP_NUMBER', '') or ''
    )


def numeros_destino_comercial(*, incluir_orgs: bool = True) -> set[str]:
    """
    Conjunto de números Twilio (solo dígitos) que deben ir a Nat.
    """
    out: set[str] = set()
    global_n = _global_comercial_number()
    if global_n:
        out.add(global_n)
    sandbox = _sandbox_number()
    if sandbox:
        out.add(sandbox)

    if incluir_orgs:
        from core.models import Cliente

        for raw in (
            Cliente.objects.filter(activo=True)
            .exclude(numero_whatsapp_nat='')
            .values_list('numero_whatsapp_nat', flat=True)
        ):
            n = normalizar_telefono_whatsapp(raw)
            if n:
                out.add(n)
    return out


def es_destino_bot_comercial(to_or_payload) -> bool:
    """
    True si el mensaje debe procesarse como Nat (no educativo).

    Acepta el string `To` o un mapping estilo Twilio (dict / QueryDict) con clave `To`.
    """
    if bool(getattr(settings, 'BOT_COMERCIAL_FORCE_ROUTING', False)):
        return True

    if isinstance(to_or_payload, str):
        to_raw = to_or_payload
    elif to_or_payload is None:
        to_raw = ''
    else:
        try:
            to_raw = to_or_payload.get('To', '')  # type: ignore[union-attr]
        except Exception:
            to_raw = ''

    to_limpio = normalizar_telefono_whatsapp(to_raw)
    if not to_limpio:
        return False

    return to_limpio in numeros_destino_comercial(incluir_orgs=True)


def es_numero_comercial_conocido(to: str) -> bool:
    """Defensa en profundidad dentro del processor (incluye org + sandbox + global)."""
    to_limpio = normalizar_telefono_whatsapp(to)
    if not to_limpio:
        return False
    return to_limpio in numeros_destino_comercial(incluir_orgs=True)
