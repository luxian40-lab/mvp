"""Contexto OG / WhatsApp y branding de sesión estudiante para plantillas Aprende."""

from __future__ import annotations


def aprende_social(request):
    path = request.path or ''
    if not path.startswith('/aprende'):
        return {}
    from aprende.og_preview import url_og_image_aprende

    ctx = {
        'aprende_og_image': url_og_image_aprende(request),
        'aprende_og_url': request.build_absolute_uri(path.split('?')[0] or '/aprende/'),
        'aprende_wallpaper_url': '',
        'aprende_es_estudiante': False,
        'aprende_tiene_modo_clases': False,
        'aprende_tiene_modo_modulos': False,
    }

    # Wallpaper solo en sesión estudiante (no login público ni profesor).
    est = getattr(request, 'aprende_estudiante', None)
    if est is None:
        try:
            from aprende.session_auth import estudiante_desde_sesion

            est = estudiante_desde_sesion(request)
        except Exception:
            est = None
    if est is not None and getattr(est, 'cliente_id', None):
        url = (getattr(est.cliente, 'wallpaper_aula_url', None) or '').strip()
        ctx['aprende_es_estudiante'] = True
        ctx['aprende_wallpaper_url'] = url
        try:
            from core.models import Curso, ProgresoEstudiante

            modos = list(
                ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
                .values_list('curso__modo_aula', flat=True)
            )
            ctx['aprende_tiene_modo_clases'] = any(
                (m or '') == Curso.MODO_AULA_CLASES for m in modos
            )
            ctx['aprende_tiene_modo_modulos'] = any(
                (m or Curso.MODO_AULA_MODULOS) != Curso.MODO_AULA_CLASES for m in modos
            )
        except Exception:
            ctx['aprende_tiene_modo_clases'] = False
            ctx['aprende_tiene_modo_modulos'] = True

    return ctx
