import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

def _cliente_en_ventana(cliente, campo_habilitar, campo_inicio, campo_fin):
    """Evalúa si una funcionalidad está habilitada para un cliente según ventana de fechas."""
    if not cliente:
        return True
    if not getattr(cliente, campo_habilitar, False):
        return False

    hoy = timezone.localdate()
    inicio = getattr(cliente, campo_inicio, None)
    fin = getattr(cliente, campo_fin, None)

    if inicio and hoy < inicio:
        return False
    if fin and hoy > fin:
        return False
    return True

def _cliente_habilita_pregunta_abierta_final(cliente):
    return _cliente_en_ventana(
        cliente,
        'habilitar_pregunta_abierta_final',
        'fecha_inicio_pregunta_abierta_final',
        'fecha_fin_pregunta_abierta_final',
    )

def _mensaje_bloqueo_drip_view(fecha_desbloqueo):
    from ..response_templates import _mensaje_bloqueo_drip
    return _mensaje_bloqueo_drip(fecha_desbloqueo)

def _pregunta_abierta_final_pendiente(estudiante, progreso):
    from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal

    preguntas_qs = PreguntaAbiertaFinalCurso.objects.filter(
        curso=progreso.curso,
        activa=True
    ).order_by('orden', 'id')

    if not preguntas_qs.exists():
        return None

    cliente_habilita = _cliente_habilita_pregunta_abierta_final(estudiante.cliente)
    curso_habilita = bool(getattr(progreso.curso, 'habilitar_pregunta_abierta_final', False))
    if not (cliente_habilita and curso_habilita):
        logger.info(
            "⚠️ Fallback pregunta abierta final por configuración | estudiante_id=%s | curso_id=%s | cliente_habilita=%s | curso_habilita=%s",
            estudiante.id,
            progreso.curso.id,
            cliente_habilita,
            curso_habilita,
        )

    preguntas = list(preguntas_qs[:3])

    for pregunta in preguntas:
        existe = RespuestaAbiertaFinal.objects.filter(
            pregunta=pregunta,
            estudiante=estudiante
        ).exists()
        if not existe:
            return pregunta

    return None
