"""
Telemetría de aprendizaje para el Centro de Éxito.

Escribir siempre por registrar_evento(); nunca fallar el flujo pedagógico.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


def registrar_evento(
    *,
    tipo: str,
    estudiante,
    curso=None,
    modulo=None,
    paso=None,
    seccion=None,
    canal: str = 'whatsapp',
    metadata: dict | None = None,
    cliente=None,
) -> Any:
    """Persiste un EstudianteEventoAprendizaje. Devuelve la instancia o None si falla."""
    try:
        from core.models import EstudianteEventoAprendizaje

        if estudiante is None:
            return None

        cli = cliente
        if cli is None:
            cli = getattr(estudiante, 'cliente', None) or getattr(estudiante, 'cliente_id', None)
            if isinstance(cli, int):
                from core.models import Cliente

                cli = Cliente.objects.filter(pk=cli).first()

        if curso is None and hasattr(estudiante, '_progreso_telemetria_curso'):
            curso = estudiante._progreso_telemetria_curso

        meta = dict(metadata or {})
        ev = EstudianteEventoAprendizaje.objects.create(
            estudiante=estudiante,
            cliente=cli,
            curso=curso,
            modulo=modulo,
            paso=paso,
            seccion=seccion or (getattr(paso, 'seccion', None) if paso is not None else None),
            tipo=tipo,
            canal=canal or 'whatsapp',
            metadata=meta,
        )
        return ev
    except Exception as exc:
        logger.warning('telemetria: no se pudo registrar %s: %s', tipo, exc)
        return None


def marcar_recordatorio_respondido(estudiante, *, ventana_horas: int = 72) -> None:
    """Si hay recordatorio_enviado reciente sin respuesta, emite recordatorio_respondido."""
    try:
        from core.models import EstudianteEventoAprendizaje

        desde = timezone.now() - timedelta(hours=max(1, ventana_horas))
        ultimo = (
            EstudianteEventoAprendizaje.objects.filter(
                estudiante=estudiante,
                tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
                created_at__gte=desde,
            )
            .order_by('-created_at')
            .first()
        )
        if not ultimo:
            return
        ya = EstudianteEventoAprendizaje.objects.filter(
            estudiante=estudiante,
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_RESPONDIDO,
            created_at__gte=ultimo.created_at,
        ).exists()
        if ya:
            return
        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_RESPONDIDO,
            estudiante=estudiante,
            curso=ultimo.curso,
            modulo=ultimo.modulo,
            metadata={
                'recordatorio_evento_id': ultimo.pk,
                'horas_desde_envio': round(
                    (timezone.now() - ultimo.created_at).total_seconds() / 3600, 2
                ),
            },
        )
    except Exception as exc:
        logger.warning('telemetria: marcar_recordatorio_respondido: %s', exc)


def mapa_abandono_por_paso(progreso_qs, curso) -> list[dict]:
    """
    Pasos donde se envió contenido y no llegó listo/evaluación posterior
    (requiere telemetría; si no hay eventos, lista vacía).
    """
    from core.models import EstudianteEventoAprendizaje, PasoModulo

    if not curso:
        return []

    progreso_ids = list(progreso_qs.values_list('pk', flat=True))
    if not progreso_ids:
        return []

    est_ids = list(
        progreso_qs.values_list('estudiante_id', flat=True).distinct()
    )
    if not est_ids:
        return []

    enviados = (
        EstudianteEventoAprendizaje.objects.filter(
            estudiante_id__in=est_ids,
            curso=curso,
            tipo=EstudianteEventoAprendizaje.TIPO_CONTENIDO_ENVIADO,
            paso_id__isnull=False,
        )
        .values('paso_id')
        .annotate(n=Count('estudiante_id', distinct=True))
    )
    enviados_map = {r['paso_id']: r['n'] for r in enviados}
    if not enviados_map:
        return []

    avances = (
        EstudianteEventoAprendizaje.objects.filter(
            estudiante_id__in=est_ids,
            curso=curso,
            tipo__in=[
                EstudianteEventoAprendizaje.TIPO_LISTO_RECIBIDO,
                EstudianteEventoAprendizaje.TIPO_EVALUACION_RESPONDIDA,
            ],
            paso_id__isnull=False,
        )
        .values('paso_id')
        .annotate(n=Count('estudiante_id', distinct=True))
    )
    avance_map = {r['paso_id']: r['n'] for r in avances}

    pasos = list(
        PasoModulo.objects.filter(pk__in=enviados_map.keys(), modulo__curso=curso)
        .select_related('modulo', 'seccion')
        .order_by('modulo__numero', 'orden', 'id')
    )
    out = []
    max_caidas = 1
    for p in pasos:
        env = enviados_map.get(p.pk, 0)
        av = avance_map.get(p.pk, 0)
        # Aprox: quienes recibieron este paso y no tienen avance asociado al mismo paso.
        # Mejor métrica: desertaron = enviados - quienes hicieron listo en paso siguiente.
        caidas = max(0, env - av)
        max_caidas = max(max_caidas, caidas or 1)
        media = bool((p.media_url or '').strip())
        out.append({
            'paso_id': p.pk,
            'paso_orden': p.orden,
            'modulo_numero': p.modulo.numero if p.modulo_id else None,
            'titulo': (p.titulo or p.contenido or f'Paso {p.orden}')[:72],
            'tiene_media': media,
            'enviados': env,
            'avanzaron': av,
            'caidas': caidas,
            'tasa_pct': round(100.0 * caidas / env, 1) if env else 0.0,
        })
    for row in out:
        row['barra_pct'] = round(100.0 * row['caidas'] / max_caidas, 1) if max_caidas else 0
    # Solo mostrar pasos con alguna caída o media (diseñador instruccional).
    return [r for r in out if r['caidas'] > 0 or r['tiene_media']][:40]


def recordatorios_ignorados_estudiante(estudiante_id: int, *, dias: int = 30) -> int:
    """Cuenta recordatorios enviados sin recordatorio_respondido posterior (ventana 72h)."""
    from core.models import EstudianteEventoAprendizaje

    desde = timezone.now() - timedelta(days=dias)
    enviados = list(
        EstudianteEventoAprendizaje.objects.filter(
            estudiante_id=estudiante_id,
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
            created_at__gte=desde,
        ).values_list('id', 'created_at')
    )
    if not enviados:
        return 0
    ignorados = 0
    for eid, ts in enviados:
        limite = ts + timedelta(hours=72)
        respondio = EstudianteEventoAprendizaje.objects.filter(
            estudiante_id=estudiante_id,
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_RESPONDIDO,
            created_at__gte=ts,
            created_at__lte=limite,
        ).exists()
        if not respondio and timezone.now() > limite:
            ignorados += 1
    return ignorados
