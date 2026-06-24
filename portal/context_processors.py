from urllib.parse import quote

from django.conf import settings

from core.models import SolicitudSoporte

from .branding import branding_portal_completo, pasos_branding
from .capabilities import categorias_pqrs_portal, modulos_portal


def pqrs_pendientes(request):
    if getattr(request, 'portal_usuario', None):
        try:
            org = request.portal_usuario.organizacion
            pqrs_q = SolicitudSoporte.objects.filter(
                estudiante__cliente=org,
                estado='pendiente',
            )
            cats = categorias_pqrs_portal(org)
            if cats is not None:
                pqrs_q = pqrs_q.filter(categoria__in=cats)
            count = pqrs_q.count()
            return {'pendientes_count': count}
        except Exception:
            pass
    return {'pendientes_count': 0}


def portal_organizacion(request):
    """Contexto común del portal: organización, rol y permisos de edición."""
    pu = getattr(request, 'portal_usuario', None)
    if not pu:
        return {}
    org = pu.organizacion
    tel = getattr(settings, 'PORTAL_WHATSAPP_SOPORTE', '573103844274') or '573103844274'
    msg = quote(f'Hola eki, necesito apoyo desde el portal — {org.nombre}.')
    mods = modulos_portal(org)
    es_admin = pu.rol == 'admin'
    branding_ok = branding_portal_completo(org)
    return {
        'org': org,
        'portal_usuario': pu,
        'portal_es_admin': es_admin,
        'portal_solo_lectura': not es_admin,
        'org_iniciales': ''.join(p[0].upper() for p in (org.nombre or 'E')[:2].split()[:2]) or 'E',
        'portal_whatsapp_url': f'https://wa.me/{tel}?text={msg}',
        'portal_mod_cursos': mods['cursos'],
        'portal_mod_gei': mods['gei'],
        'portal_mod_nat': mods['nat'],
        'portal_mod_empleabilidad': mods['empleabilidad'],
        'portal_branding_completo': branding_ok,
        'portal_branding_pasos': pasos_branding(org),
        'portal_branding_pendientes': sum(1 for p in pasos_branding(org) if not p['done']),
    }
