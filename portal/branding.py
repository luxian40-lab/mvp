"""Estado de identidad visual del portal clientes por organización."""

from __future__ import annotations

from core.models import Cliente


def identidad_org(org: Cliente | None) -> dict:
    """Logo, inicial y textos de marca para admin y portal."""
    nombre = (getattr(org, 'nombre', None) or '').strip() if org else ''
    return {
        'logo': (getattr(org, 'logo_url', None) or '').strip() if org else '',
        'wallpaper': (getattr(org, 'wallpaper_aula_url', None) or '').strip() if org else '',
        'subtitulo': (getattr(org, 'portal_subtitulo', None) or '').strip() if org else '',
        'inicial': (nombre[:1] or '?').upper(),
        'nombre': nombre,
    }


def contexto_identidad_org(org: Cliente | None) -> dict:
    ident = identidad_org(org)
    return {
        'eki_org_logo': ident['logo'],
        'eki_org_wallpaper': ident['wallpaper'],
        'eki_org_inicial': ident['inicial'],
        'eki_org_nombre': ident['nombre'],
        'eki_org_subtitulo': ident['subtitulo'],
    }


def branding_portal_completo(org: Cliente | None) -> bool:
    if not org:
        return True
    ident = identidad_org(org)
    return bool(ident['logo'] and ident['subtitulo'])


def pasos_branding(org: Cliente | None) -> list[dict]:
    if not org:
        return []
    ident = identidad_org(org)
    return [
        {
            'id': 'logo',
            'label': 'Logo de su organización',
            'grupo': 'portal',
            'done': bool(ident['logo']),
            'hint': 'PNG o JPG, máximo 5 MB. Aparece en la barra lateral del portal.',
        },
        {
            'id': 'subtitulo',
            'label': 'Subtítulo del programa',
            'grupo': 'portal',
            'done': bool(ident['subtitulo']),
            'hint': 'Ej: «Programa de aceleración 2026». Debajo del nombre, en el portal.',
        },
        {
            'id': 'wallpaper',
            'label': 'Fondo del aula Aprende',
            'grupo': 'aprende',
            'done': bool(ident['wallpaper']),
            'hint': 'Lo ven los estudiantes al entrar al aula. No es el fondo de este portal.',
        },
    ]
