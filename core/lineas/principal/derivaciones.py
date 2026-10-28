"""Derivaciones de asesoría: se anotan para revisar si se acierta.

Una derivación queda corregida si justo después la persona cambió de asesor o
volvió al menú: dentro de 10 minutos y sin hacerle otra pregunta al asesor
elegido. Ir al segundo asesor que se le ofreció no cuenta como error.
Fuera del ciclo de imports.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import DatabaseError
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

VENTANA_MINUTOS = 10
DIAS_RESUMEN = 7


def _etiquetas_log(agente: str) -> list[str]:
    return [f'sandbox_{agente}', 'BOT_COMERCIAL'] if agente == 'nat' else [f'sandbox_{agente}']


def registrar(
    telefono: str, frase: str, agente: str, *, secundario: str = '', fuente: str = 'llm', con_contexto: bool = False,
) -> None:
    from core.conocimiento_agentes import _sin_datos_personales
    from core.locks import telefono_hash
    from core.models import DerivacionAsesoria

    try:
        DerivacionAsesoria.objects.create(
            telefono_hash=telefono_hash(telefono),
            frase=_sin_datos_personales(' '.join((frase or '').split()))[:300],
            agente=agente,
            agente_secundario=secundario or '',
            fuente=fuente,
            con_contexto=con_contexto,
        )
    except DatabaseError:
        logger.exception('derivacion_registro_fail agente=%s', agente)


def marcar_si_corrige(telefono: str, anterior: str, nuevo: str) -> bool:
    """True si el cambio de modo corrige la derivación recién hecha."""
    if not anterior or anterior == nuevo:
        return False
    from core.locks import telefono_hash
    from core.models import DerivacionAsesoria, WhatsappLog

    desde = timezone.now() - timedelta(minutes=VENTANA_MINUTOS)
    derivacion = (
        DerivacionAsesoria.objects.filter(
            telefono_hash=telefono_hash(telefono), creada_en__gte=desde, agente=anterior, corregida=False,
        )
        .order_by('-creada_en')
        .first()
    )
    if derivacion is None or nuevo == derivacion.agente_secundario:
        return False
    preguntas = WhatsappLog.objects.filter(
        telefono=telefono,
        tipo='INCOMING',
        agente_usado__in=_etiquetas_log(anterior),
        fecha__gte=derivacion.creada_en,
    ).count()
    if preguntas > 1:
        return False
    derivacion.corregida = True
    derivacion.corregida_a = (nuevo or '')[:20]
    derivacion.save(update_fields=['corregida', 'corregida_a'])
    return True


def resumen_semana() -> tuple[int, int]:
    """(derivaciones, corregidas) de los últimos 7 días."""
    from core.models import DerivacionAsesoria

    desde = timezone.now() - timedelta(days=DIAS_RESUMEN)
    datos = DerivacionAsesoria.objects.filter(creada_en__gte=desde).aggregate(
        total=Count('id'), corregidas=Count('id', filter=Q(corregida=True)),
    )
    return datos['total'] or 0, datos['corregidas'] or 0
