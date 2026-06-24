"""Estado de identidad visual del portal clientes por organización."""

from __future__ import annotations

from core.models import Cliente


def branding_portal_completo(org: Cliente | None) -> bool:
    if not org:
        return True
    tiene_logo = bool((org.logo_url or '').strip())
    tiene_subtitulo = bool((org.portal_subtitulo or '').strip())
    return tiene_logo and tiene_subtitulo


def pasos_branding(org: Cliente | None) -> list[dict]:
    if not org:
        return []
    logo_ok = bool((org.logo_url or '').strip())
    subtitulo_ok = bool((org.portal_subtitulo or '').strip())
    return [
        {
            'id': 'logo',
            'label': 'Logo de su organización',
            'done': logo_ok,
            'hint': 'PNG o JPG, máximo 5 MB. Aparece en la barra lateral.',
        },
        {
            'id': 'subtitulo',
            'label': 'Subtítulo del programa',
            'done': subtitulo_ok,
            'hint': 'Ej: «Programa de aceleración 2026». Su equipo lo verá debajo del nombre.',
        },
    ]
