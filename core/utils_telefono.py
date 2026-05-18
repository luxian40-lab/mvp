"""Normalización de teléfonos WhatsApp (Colombia) para emparejar logs y estudiantes."""
from __future__ import annotations

import re


def normalizar_telefono(raw: str) -> str:
    """Solo dígitos; si son 10 dígitos locales, antepone 57."""
    t = re.sub(r"\D", "", (raw or "").strip())
    if len(t) == 10 and not t.startswith("57"):
        t = f"57{t}"
    return t


def variantes_telefono(raw: str) -> list[str]:
    """Variantes usadas en WhatsappLog / Estudiante para el mismo número."""
    base = normalizar_telefono(raw)
    if not base:
        return []
    out = {base}
    if base.startswith("57") and len(base) > 2:
        out.add(base[2:])
        out.add(f"+{base}")
    if len(base) == 10:
        out.add(f"57{base}")
    return sorted(out)
