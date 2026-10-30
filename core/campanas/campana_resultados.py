"""Resumen operativo de campaña: audiencia limpia + resultados de EnvioLog."""
from __future__ import annotations

import csv
from collections import Counter
from io import StringIO
from typing import Any

from django.db.models import QuerySet

from core.utils_telefono import explicar_error_envio_whatsapp, validar_telefono_whatsapp


def _qs_destinatarios(campana) -> QuerySet:
    if getattr(campana, 'tipo_audiencia', None) == 'grupo' and campana.grupo_id:
        return campana.grupo.estudiantes.filter(activo=True)
    return campana.destinatarios.filter(activo=True)


def revisar_audiencia_campana(campana) -> dict[str, Any]:
    """Clasifica teléfonos de la audiencia antes/después del envío."""
    ok, warn, error = [], [], []
    for est in _qs_destinatarios(campana).only('id', 'nombre', 'telefono'):
        v = validar_telefono_whatsapp(est.telefono or '')
        row = {
            'id': est.id,
            'nombre': est.nombre or '',
            'telefono': est.telefono or '',
            'mensaje': v['mensaje'],
        }
        if v['severity'] == 'error' or not v['ok']:
            error.append(row)
        elif v['severity'] == 'warn':
            warn.append(row)
        else:
            ok.append(row)
    return {
        'total': len(ok) + len(warn) + len(error),
        'ok': ok,
        'warn': warn,
        'error': error,
        'n_ok': len(ok),
        'n_warn': len(warn),
        'n_error': len(error),
    }


def resumen_envios_campana(campana, *, max_filas: int = 40) -> dict[str, Any]:
    """Agrega EnvioLog de la campaña en lenguaje simple."""
    from core.models import EnvioLog

    logs = (
        EnvioLog.objects.filter(campana=campana)
        .select_related('estudiante')
        .order_by('-fecha_envio')
    )
    by_estado = Counter()
    ok_rows = []
    fail_rows = []
    for log in logs:
        st = (log.estado or '').upper()
        by_estado[st] += 1
        motivo = explicar_error_envio_whatsapp(log.respuesta_api, log.estado)
        row = {
            'nombre': getattr(log.estudiante, 'nombre', '') or '',
            'telefono': getattr(log.estudiante, 'telefono', '') or '',
            'estado': st,
            'motivo': motivo,
            'fecha': log.fecha_envio,
        }
        if st in ('ENVIADO', 'EXITOSO', 'OK', 'DELIVERED', 'READ'):
            ok_rows.append(row)
        elif st in ('FALLIDO', 'ERROR', 'FAILED'):
            fail_rows.append(row)
        else:
            # PENDIENTE u otros → mostrar en fallidos suaves
            if st:
                fail_rows.append(row)

    n_ok = sum(by_estado[k] for k in by_estado if k in ('ENVIADO', 'EXITOSO', 'OK', 'DELIVERED', 'READ'))
    n_fail = sum(by_estado[k] for k in by_estado if k in ('FALLIDO', 'ERROR', 'FAILED'))
    n_other = sum(by_estado.values()) - n_ok - n_fail
    return {
        'total_logs': sum(by_estado.values()),
        'by_estado': dict(by_estado),
        'n_ok': n_ok,
        'n_fail': n_fail,
        'n_other': n_other,
        'ok_sample': ok_rows[:max_filas],
        'fail_sample': fail_rows[:max_filas],
        'fail_all': fail_rows,
    }


def csv_fallidos_campana(campana) -> str:
    """CSV Nombre,Teléfono,Estado,Motivo para reenviar / corregir."""
    data = resumen_envios_campana(campana, max_filas=10_000)
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(['nombre', 'telefono', 'estado', 'motivo'])
    for row in data['fail_all']:
        w.writerow([row['nombre'], row['telefono'], row['estado'], row['motivo']])
    # Si no hay EnvioLog fallidos, exportar audiencia con teléfono inválido
    if not data['fail_all']:
        aud = revisar_audiencia_campana(campana)
        for row in aud['error']:
            w.writerow([row['nombre'], row['telefono'], 'TELEFONO', row['mensaje']])
    return buf.getvalue()
