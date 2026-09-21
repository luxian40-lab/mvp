"""
Mensajes de agentes WhatsApp (Darío, Claudia, Carlos, etc.).

Canon eki: el cuerpo va directo. No abrir con el nombre como título
(*Carlos* / Darío / Claudia en la primera línea).
"""
from __future__ import annotations

import re


def cuerpo_sin_titular_agente(nombre: str | None, cuerpo: str | None) -> str:
    """
    Devuelve solo el cuerpo. Quita un titular inicial *Nombre* / Nombre / Nombre:
    si el modelo o un template viejo lo pusieron.
    """
    nombre = (nombre or '').strip()
    cuerpo = (cuerpo or '').strip()
    if not cuerpo:
        return ''
    if not nombre:
        return cuerpo
    cuerpo = re.sub(
        rf'^\*?{re.escape(nombre)}\*?(?:\s*[:\-–])?\s*\n+',
        '',
        cuerpo,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    cuerpo = re.sub(
        rf'^\*?{re.escape(nombre)}\*?\s*[:\-–]\s*',
        '',
        cuerpo,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    return cuerpo


# Compat: llamadas viejas no deben volver a titular.
def mensaje_con_titular_agente(nombre: str | None, cuerpo: str | None) -> str:
    return cuerpo_sin_titular_agente(nombre, cuerpo)


def titular_agente_al_inicio(texto: str | None, nombre: str | None) -> bool:
    """True si el mensaje abre con el titular del agente (formato a evitar)."""
    nombre = (nombre or '').strip()
    texto = (texto or '').lstrip()
    if not nombre or not texto:
        return False
    return bool(
        re.match(rf'^\*{re.escape(nombre)}\*\s*\n', texto, flags=re.IGNORECASE)
    )
