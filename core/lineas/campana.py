"""Campañas Meta por línea. Una plantilla no cruza de WABA."""
from __future__ import annotations


def waba_de_linea(phone_id: str) -> str:
    """WABA de esa línea. Vacío en la 2 si el entorno no la tiene."""
    from django.conf import settings

    from core.lineas.variante import es_modo_twilio
    from core.meta_waba import _waba

    if es_modo_twilio(phone_id):
        return (getattr(settings, 'WHATSAPP_BUSINESS_ACCOUNT_ID_2', '') or '').strip()
    return _waba()


def plantillas_aprobadas_de_linea(phone_id: str):
    """Solo plantillas de la WABA de esa línea. Vacío = no hay nada que ofrecer."""
    from core.lineas.variante import es_modo_twilio
    from core.meta_waba import _waba
    from core.models_campana_meta import PlantillaMeta

    qs = PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
    principal = _waba()
    if es_modo_twilio(phone_id):
        waba_2 = waba_de_linea(phone_id)
        if waba_2:
            return qs.filter(waba_id=waba_2)
        if principal:
            return qs.exclude(waba_id__in=['', principal])
        return qs.none()
    if principal:
        return qs.filter(waba_id__in=['', principal])
    return qs


def plantilla_sirve_en_linea(plantilla, phone_id: str) -> str:
    """Vacío si puede salir por esa línea. Si no, el motivo."""
    if plantilla is None:
        return ''
    from core.lineas.variante import es_modo_twilio
    from core.meta_waba import _waba

    waba_plantilla = (getattr(plantilla, 'waba_id', '') or '').strip()
    principal = _waba()
    if es_modo_twilio(phone_id):
        waba_2 = waba_de_linea(phone_id)
        if waba_2:
            if waba_plantilla != waba_2:
                return (
                    'Esa plantilla no está en la cuenta de la línea 2. '
                    'Las plantillas no cruzan de WABA.'
                )
            return ''
        if principal and waba_plantilla in ('', principal):
            return (
                'Esa plantilla es de la línea principal. '
                'En la línea 2 (modo Twilio) no se puede usar.'
            )
        return ''
    if principal and waba_plantilla and waba_plantilla != principal:
        return 'Esa plantilla no está en la cuenta de la línea principal.'
    return ''


def wabas_configuradas() -> list[str]:
    """WABAs de las líneas que tienen cuenta. Sin duplicar."""
    from core.lineas.meta import lineas_producto
    from core.meta_waba import _waba

    vistos: list[str] = []
    for linea in lineas_producto():
        waba = waba_de_linea(linea.phone_id)
        if waba and waba not in vistos:
            vistos.append(waba)
    principal = _waba()
    if principal and principal not in vistos:
        vistos.insert(0, principal)
    return vistos


def fichas_admin() -> list[dict]:
    """Lo que el admin muestra. No crea filas: lee el registro de entorno."""
    from core.lineas.meta import USO_SOLO_CURSOS, lineas_producto
    from core.lineas.variante import es_modo_twilio

    filas = []
    for linea in lineas_producto():
        lineal = es_modo_twilio(linea.phone_id) or linea.uso == USO_SOLO_CURSOS
        waba = waba_de_linea(linea.phone_id)
        if lineal:
            modo = 'Curso lineal'
            entra = (
                'eki inicia con una campaña. La persona sigue hasta acabar el curso. '
                'Sin menú de planes ni agentes aparte.'
            )
        else:
            modo = 'Versión Meta'
            entra = (
                'eki inicia con una campaña. Después puede seguir con planes mensuales, '
                'carrusel de cursos y agentes.'
            )
        filas.append({
            'nombre': linea.nombre,
            'e164': linea.e164,
            'phone_id': linea.phone_id,
            'modo': modo,
            'lineal': lineal,
            'waba': waba,
            'entra': entra,
            'sin_waba': lineal and not waba,
        })
    return filas
