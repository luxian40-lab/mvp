from urllib.parse import quote

from django.conf import settings

from core.models import SolicitudSoporte

from .branding import branding_portal_completo, pasos_branding
from .capabilities import categorias_pqrs_portal, modulos_portal, portal_home_url, portal_solo_nat


def _resumen_header_org(org):
    """Cifras ligeras (solo COUNT) para la cabecera editorial. Nunca rompe la página."""
    try:
        from django.db.models import Count, Q

        from core.models import Curso, Estudiante, ProgresoEstudiante
        from core.models_certificados import Certificado

        participantes = Estudiante.objects.filter(cliente=org).count()
        cursos = Curso.objects.filter(cliente=org, activo=True).count()
        certificados = Certificado.objects.filter(
            estudiante__cliente=org, emitido=True,
        ).count()
        agg = ProgresoEstudiante.objects.filter(curso__cliente=org).aggregate(
            total=Count('id'),
            completos=Count('id', filter=Q(completado=True)),
        )
        total = agg['total'] or 0
        avance_pct = round((agg['completos'] or 0) / total * 100) if total else 0
        return {
            'participantes': participantes,
            'cursos': cursos,
            'certificados': certificados,
            'avance_pct': avance_pct,
        }
    except Exception:
        return None


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
    es_eki_ops = pu.rol == 'eki_ops'
    es_docente = pu.rol in ('admin', 'profesor')
    branding_ok = branding_portal_completo(org)

    user = getattr(pu, 'user', None)
    user_nombre = ''
    if user is not None:
        user_nombre = (user.get_full_name() or user.username or '').strip()
    partes = [p for p in user_nombre.replace('.', ' ').replace('_', ' ').split() if p]
    if partes:
        user_iniciales = (partes[0][0] + (partes[1][0] if len(partes) > 1 else '')).upper()
    else:
        user_iniciales = 'U'

    mods_cursos = mods['cursos']
    header_stats = None if es_eki_ops else (_resumen_header_org(org) if mods_cursos else None)

    from .capabilities import portal_home_url_para_usuario
    from .provision import cupos_restantes, cupos_totales, cupos_usados
    from datetime import date

    fin = org.fecha_fin_suscripcion
    dias_restantes = (fin - date.today()).days if fin else None

    return {
        'org': org,
        'portal_usuario': pu,
        'portal_user_nombre': user_nombre or 'Usuario',
        'portal_user_iniciales': user_iniciales,
        'portal_header_stats': header_stats,
        'portal_es_admin': es_admin,
        'portal_es_eki_ops': es_eki_ops,
        'portal_es_docente': es_docente,
        'portal_solo_lectura': pu.rol == 'viewer',
        'org_iniciales': ''.join(p[0].upper() for p in (org.nombre or 'E')[:2].split()[:2]) or 'E',
        'portal_whatsapp_url': f'https://wa.me/{tel}?text={msg}',
        'portal_mod_cursos': mods['cursos'] and not es_eki_ops,
        'portal_mod_gei': mods['gei'] and not es_eki_ops,
        'portal_mod_nat': mods['nat'] and not es_eki_ops,
        'portal_mod_empleabilidad': mods['empleabilidad'] and not es_eki_ops,
        'portal_mod_facilitador': (mods['cursos'] or mods['gei']) and not es_eki_ops,
        'portal_solo_nat': portal_solo_nat(org) and not es_eki_ops,
        'portal_home_url': portal_home_url_para_usuario(pu),
        'portal_branding_completo': branding_ok if not es_eki_ops else True,
        'portal_branding_pasos': [] if es_eki_ops else pasos_branding(org),
        'portal_branding_pendientes': 0 if es_eki_ops else sum(1 for p in pasos_branding(org) if not p['done']),
        'portal_suscripcion_activa': org.suscripcion_activa,
        'portal_fecha_fin_suscripcion': fin,
        'portal_dias_restantes': dias_restantes,
        'portal_cupos_usados': cupos_usados(org),
        'portal_cupos_totales': cupos_totales(org),
        'portal_cupos_restantes': cupos_restantes(org),
    }
