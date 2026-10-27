"""Uso de IA por persona: preguntas a los asesores del menú y a Nat.

Cada pregunta queda como WhatsappLog INCOMING con agente_usado = sandbox_<agente>
o BOT_COMERCIAL (Nat). Se cruza por estudiante o por teléfono, como en Impacto.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import Estudiante, WhatsappLog

DIAS_PERIODO = 90
ETIQUETA_NAT = 'BOT_COMERCIAL'


def _nombre_agente(etiqueta: str) -> str:
    if etiqueta == ETIQUETA_NAT:
        return 'Agrónomo (Nat)'
    clave = etiqueta.removeprefix('sandbox_')
    try:
        from core.sandbox_agentes import nombre_agente

        return nombre_agente(clave)
    except KeyError:
        return clave


def uso_ia_por_persona(org, *, ahora=None) -> dict:
    ahora = ahora or timezone.now()
    estudiantes = list(
        Estudiante.objects.filter(cliente=org, activo=True).values_list('id', 'nombre', 'telefono')
    )
    nombres = {eid: nombre for eid, nombre, _ in estudiantes}
    por_telefono = {tel: eid for eid, _, tel in estudiantes if tel}

    filas = (
        WhatsappLog.objects.filter(
            tipo='INCOMING',
            fecha__gte=ahora - timedelta(days=DIAS_PERIODO),
        )
        .filter(Q(agente_usado__startswith='sandbox_') | Q(agente_usado=ETIQUETA_NAT))
        .filter(Q(estudiante_id__in=list(nombres)) | Q(telefono__in=list(por_telefono)))
        .values_list('estudiante_id', 'telefono', 'agente_usado', 'fecha')
    )
    conteo: dict[int, dict[str, int]] = {}
    ultima: dict[int, object] = {}
    totales_agente: dict[str, int] = {}
    for eid, telefono, etiqueta, fecha in filas:
        eid = eid if eid in nombres else por_telefono.get(telefono)
        if eid is None:
            continue
        agente = _nombre_agente(etiqueta)
        persona = conteo.setdefault(eid, {})
        persona[agente] = persona.get(agente, 0) + 1
        totales_agente[agente] = totales_agente.get(agente, 0) + 1
        if eid not in ultima or fecha > ultima[eid]:
            ultima[eid] = fecha

    agentes = sorted(totales_agente, key=lambda a: (-totales_agente[a], a))
    personas = sorted(
        (
            {
                'nombre': nombres[eid],
                'total': sum(por_agente.values()),
                'por_agente': [por_agente.get(a, 0) for a in agentes],
                'ultima': ultima[eid],
            }
            for eid, por_agente in conteo.items()
        ),
        key=lambda p: (-p['total'], p['nombre']),
    )
    registrados = len(estudiantes)
    return {
        'periodo_dias': DIAS_PERIODO,
        'agentes': agentes,
        'totales_agente': [totales_agente[a] for a in agentes],
        'total': sum(totales_agente.values()),
        'personas': personas,
        'usan': len(personas),
        'registrados': registrados,
        'usan_pct': round(len(personas) * 100 / registrados, 1) if registrados else None,
    }
