"""Ops Fase C: snapshot municipio×ventana×conteo + transiciones de alerta (interno eki)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone

from core.models import AlertaTerritorial, SenalTerritorial

# Runbook interno — no publica a cliente ni WA.
RUNBOOK_PASOS: list[dict[str, str]] = [
    {
        'paso': '1. Detectar',
        'quien': 'Sistema (Celery density_v0)',
        'hacer': 'Revisa conteo ≥ min_k en la ventana. No contactar aún.',
    },
    {
        'paso': '2. Validar',
        'quien': 'Ops / Data eki',
        'hacer': (
            'Confirma que las señales son tipificadas (plaga/empleo), '
            'mismo territorio y no son probe/ruido. Marca Validada.'
        ),
    },
    {
        'paso': '3. Comunicar (interno)',
        'quien': 'Ops eki → dueño de cuenta / Growth',
        'hacer': (
            'Solo canal interno (Slack/Notion/mail eki). '
            'No avisar al cliente ni publicar en portal en Fase C.'
        ),
    },
    {
        'paso': '4. Accionar / cerrar',
        'quien': 'Ops eki',
        'hacer': (
            'Si hay acción de producto (contenido Nat, campaña), anótalo. '
            'Cierra la alerta cuando el pico pasó o era falso positivo.'
        ),
    },
]

ESTADOS_ABIERTOS = (
    AlertaTerritorial.ESTADO_DETECTADA,
    AlertaTerritorial.ESTADO_VALIDADA,
    AlertaTerritorial.ESTADO_COMUNICADA,
    AlertaTerritorial.ESTADO_ACCIONADA,
)

_TRANSICIONES: dict[str, set[str]] = {
    AlertaTerritorial.ESTADO_DETECTADA: {
        AlertaTerritorial.ESTADO_VALIDADA,
        AlertaTerritorial.ESTADO_CERRADA,
    },
    AlertaTerritorial.ESTADO_VALIDADA: {
        AlertaTerritorial.ESTADO_COMUNICADA,
        AlertaTerritorial.ESTADO_ACCIONADA,
        AlertaTerritorial.ESTADO_CERRADA,
    },
    AlertaTerritorial.ESTADO_COMUNICADA: {
        AlertaTerritorial.ESTADO_ACCIONADA,
        AlertaTerritorial.ESTADO_CERRADA,
    },
    AlertaTerritorial.ESTADO_ACCIONADA: {
        AlertaTerritorial.ESTADO_CERRADA,
    },
}


def ventana_horas_default() -> int:
    try:
        return int(getattr(settings, 'ALERTA_TERRITORIAL_VENTANA_HORAS', 72) or 72)
    except (TypeError, ValueError):
        return 72


def min_k_default() -> int:
    try:
        return int(getattr(settings, 'ALERTA_TERRITORIAL_MIN_K', 3) or 3)
    except (TypeError, ValueError):
        return 3


def etiqueta_territory_id(territory_id: str) -> str:
    """Municipio / depto legible desde catálogo DIVIPOLA; si no, el código."""
    tid = (territory_id or '').strip()
    if not tid:
        return '—'
    try:
        from portal.geo_catalogo import _divipola_por_clave

        for clave, row in _divipola_por_clave().items():
            code = str((row or {}).get('codigo') or '').strip()
            if code.isdigit():
                code = code.zfill(5)
            if code == tid:
                partes = clave.split('|', 1)
                mun = partes[0].title() if partes else tid
                dep = partes[1].title() if len(partes) > 1 else ''
                return f'{mun} ({dep})' if dep else mun
    except Exception:
        pass
    return tid


def _familia_de_tipo(tipo: str) -> str:
    partes = (tipo or '').split('.')
    if len(partes) >= 2:
        return '.'.join(partes[:2])
    return tipo or ''


def build_territorio_alertas_snapshot(
    *,
    ventana_horas: int | None = None,
    tipo_prefijo: str = '',
) -> dict[str, Any]:
    """Municipio × ventana × conteo + alertas abiertas (solo ops interno)."""
    ventana = int(ventana_horas if ventana_horas is not None else ventana_horas_default())
    min_k = min_k_default()
    since = timezone.now() - timedelta(hours=ventana)

    qs = SenalTerritorial.objects.filter(occurred_at__gte=since)
    if tipo_prefijo:
        qs = qs.filter(tipo__startswith=tipo_prefijo)

    agg = list(
        qs.values('territory_id', 'tipo')
        .annotate(n=Count('id'), conf=Avg('confianza'))
        .order_by('-n', 'territory_id')[:80]
    )
    filas = []
    for row in agg:
        tid = row['territory_id'] or ''
        tipo = row['tipo'] or ''
        n = int(row['n'] or 0)
        filas.append({
            'territory_id': tid,
            'municipio': etiqueta_territory_id(tid),
            'tipo': tipo,
            'familia': _familia_de_tipo(tipo),
            'n': n,
            'confianza_media': round(float(row['conf'] or 0), 2),
            'sobre_umbral': n >= min_k,
        })

    alertas_qs = AlertaTerritorial.objects.filter(estado__in=ESTADOS_ABIERTOS)
    pref = (tipo_prefijo or '').strip().lower()
    if pref:
        fam = _familia_de_tipo(pref) if '.' in pref else pref
        alertas_qs = alertas_qs.filter(familia__startswith=fam)

    alertas = []
    for a in alertas_qs.order_by('-score', '-actualizado_en')[:40]:
        alertas.append({
            'id': a.pk,
            'familia': a.familia,
            'subtipo': a.subtipo,
            'territory_id': a.territory_id,
            'municipio': etiqueta_territory_id(a.territory_id),
            'conteo': a.conteo,
            'score': a.score,
            'estado': a.estado,
            'ventana_horas': a.ventana_horas,
            'explicacion': a.explicacion,
            'actualizado_en': a.actualizado_en,
        })

    return {
        'ventana_horas': ventana,
        'min_k': min_k,
        'tipo_prefijo': (tipo_prefijo or '').strip(),
        'filas': filas,
        'alertas_abiertas': alertas,
        'kpis': {
            'senales_ventana': qs.count(),
            'filas_tabla': len(filas),
            'sobre_umbral': sum(1 for f in filas if f['sobre_umbral']),
            'alertas_abiertas': len(alertas),
            'alertas_detectadas': AlertaTerritorial.objects.filter(
                estado=AlertaTerritorial.ESTADO_DETECTADA
            ).count(),
        },
        'runbook': RUNBOOK_PASOS,
        'generado_en': timezone.now(),
    }


def transicionar_alerta(
    alerta: AlertaTerritorial,
    *,
    nuevo_estado: str,
    usuario=None,
    nota: str = '',
) -> AlertaTerritorial:
    """Cambia estado si la transición es válida; anota historial en metadata."""
    actual = (alerta.estado or '').strip()
    destino = (nuevo_estado or '').strip()
    permitidos = _TRANSICIONES.get(actual, set())
    if destino not in permitidos:
        raise ValueError(f'Transición no permitida: {actual} → {destino}')

    meta = dict(alerta.metadata or {})
    hist = list(meta.get('historial') or [])
    hist.append({
        'at': timezone.now().isoformat(),
        'user': getattr(usuario, 'username', '') or str(getattr(usuario, 'pk', '') or ''),
        'de': actual,
        'a': destino,
        'nota': (nota or '')[:400],
    })
    meta['historial'] = hist[-30:]
    alerta.estado = destino
    alerta.metadata = meta
    alerta.save(update_fields=['estado', 'metadata', 'actualizado_en'])
    return alerta
