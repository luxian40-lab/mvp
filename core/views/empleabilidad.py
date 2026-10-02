import math
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

from .ventana_drip import _cliente_en_ventana

def _cliente_habilita_proximidad(cliente):
    from core.empleabilidad_pausa import empleabilidad_en_pausa

    # PAUSA: radar/empleabilidad territorial fuera de circulación.
    if empleabilidad_en_pausa():
        return False
    habilitado_legacy = _cliente_en_ventana(
        cliente,
        'habilitar_gamificacion_proximidad',
        'fecha_inicio_gamificacion_proximidad',
        'fecha_fin_gamificacion_proximidad',
    )
    return bool(habilitado_legacy or (cliente and getattr(cliente, 'empleabilidad_exploracion_activa', False)))

def _haversine_metros(lat1, lon1, lat2, lon2):
    """Distancia Haversine en metros."""
    radio_tierra = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radio_tierra * c

def _activar_radar_empleabilidad_si_aplica(estudiante):
    from django.db.models import Q
    from core.empleabilidad_pausa import empleabilidad_en_pausa
    from ..models import AliadoEmpleabilidad

    # PAUSA PRODUCTO: no desbloquear radar Subachoque.
    if empleabilidad_en_pausa():
        return False

    if not _cliente_habilita_proximidad(estudiante.cliente):
        return False

    if estudiante.cliente_id:
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        ).exists()
    else:
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).exists()

    if not hay_aliados:
        return False

    ctx = estudiante.contexto_temporal or {}
    ctx['radar_empleabilidad_activo'] = True
    ctx['empleabilidad_habilitado_en'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])
    return True

def _radar_msg_si_aplica(estudiante):
    """Copy de radar solo si la pausa está off y hay aliados. No envía Subachoque en pausa."""
    from core.empleabilidad_pausa import mensaje_radar_desbloqueado

    if not _activar_radar_empleabilidad_si_aplica(estudiante):
        return ''
    return mensaje_radar_desbloqueado()

def _procesar_ubicacion_empleabilidad(estudiante, latitud, longitud):
    """
    Evalúa proximidad del estudiante a aliados activos y construye respuesta.
    Guarda aliado objetivo en contexto para validación de código secreto.
    """
    from django.db.models import Q
    from core.empleabilidad_pausa import empleabilidad_en_pausa
    from ..models import AliadoEmpleabilidad, MisionEmpleabilidad

    # PAUSA PRODUCTO: no crear misiones ni pedir código de aliado.
    if empleabilidad_en_pausa():
        return ''

    if not _cliente_habilita_proximidad(estudiante.cliente):
        return (
            "📍 El radar de empleabilidad por ubicación no está activo para tu organización en esta fecha. "
            "Si lo esperabas, escribe *ayuda* para que el equipo valide tu acceso."
        )

    if estudiante.cliente_id:
        aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        )
    else:
        aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True)

    aliados = list(aliados)
    if not aliados:
        return "📍 En este momento no hay vacantes activas de aliados en tu zona. Te avisaremos cuando se habiliten."

    cliente_cfg = estudiante.cliente
    radio_metros = int(getattr(cliente_cfg, 'empleabilidad_radio_metros', 800) or 800)
    max_misiones_dia = int(getattr(cliente_cfg, 'empleabilidad_max_misiones_dia', 3) or 3)
    hoy = timezone.localdate()
    misiones_hoy = MisionEmpleabilidad.objects.filter(
        estudiante=estudiante,
        fecha_descubierta__date=hoy,
    ).exclude(estado='cancelada').count()
    if misiones_hoy >= max_misiones_dia:
        return (
            f"📌 Ya completaste tu límite diario de exploración ({max_misiones_dia} misiones).\n"
            "Vuelve mañana para descubrir nuevas oportunidades."
        )

    mejor = None
    mejor_dist = None
    for aliado in aliados:
        dist = _haversine_metros(latitud, longitud, aliado.latitud, aliado.longitud)
        if mejor_dist is None or dist < mejor_dist:
            mejor_dist = dist
            mejor = aliado

    if not mejor:
        return "No pude procesar tu ubicación en este momento. Inténtalo nuevamente."

    if mejor_dist > radio_metros:
        return (
            "📍 Aún no hay oportunidades dentro de tu radio de exploración actual.\n\n"
            f"Distancia más cercana a {mejor.nombre_empresa}: *{int(round(mejor_dist))} m*.\n"
            f"Radio activo de tu organización: *{int(radio_metros)} m*."
        )

    mision = MisionEmpleabilidad.objects.create(
        cliente=estudiante.cliente,
        estudiante=estudiante,
        aliado=mejor,
        estado='descubierta',
        latitud=latitud,
        longitud=longitud,
        distancia_metros=round(mejor_dist, 1),
        metadata={'fuente': 'whatsapp_location'},
    )

    ctx = estudiante.contexto_temporal or {}
    ctx['radar_empleabilidad_activo'] = True
    ctx['aliado_empleabilidad_objetivo_id'] = mejor.id
    ctx['mision_empleabilidad_id'] = mision.id
    ctx['distancia_aliado_m'] = round(mejor_dist, 1)
    estudiante.contexto_temporal = ctx
    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

    if mejor_dist <= 100:
        return (
            f"🎯 *¡Estás a {int(round(mejor_dist))} metros de {mejor.nombre_empresa}!*\n\n"
            "Acércate a la entrada y envía el *código secreto* que verás en la puerta."
        )

    sector = mejor.indicacion_sector or "del parque principal"
    return (
        "📍 Aún estás lejos de nuestras empresas aliadas.\n\n"
        f"Vas por buen camino. Acércate al sector *{sector}* y vuelve a enviarme tu ubicación.\n"
        f"Distancia aproximada actual a {mejor.nombre_empresa}: *{int(round(mejor_dist))} m*."
    )
