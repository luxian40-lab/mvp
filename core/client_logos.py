"""Logos de organizaciones conocidas (vitrina / clientes con curso)."""
from __future__ import annotations

# needle en nombre del Cliente (minúsculas) → path estático
LOGOS_CLIENTE = (
    ('agrosavia', 'clientes/logos/agrosavia.png'),
    ('fedepalma', 'clientes/logos/fedepalma.png'),
    ('cenipalma', 'clientes/logos/cenipalma.png'),
    ('profamilia', 'clientes/logos/profamilia.png'),
    ('eki demo', 'clientes/logos/eki.png'),
    ('eki', 'clientes/logos/eki.png'),
)


def logo_estatico_para_nombre(nombre: str) -> str | None:
    n = (nombre or '').strip().lower()
    if not n:
        return None
    for needle, path in LOGOS_CLIENTE:
        if needle in n:
            return path
    return None
