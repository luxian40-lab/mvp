"""Métricas GEI para el portal B2B (misma lógica que el panel admin)."""
from __future__ import annotations

from datetime import date, timedelta

GEI_CAMPOS_LEGIBLES = (
    ('nombre_finca', 'Nombre de la finca'),
    ('area_ha', 'Área productiva (ha)'),
    ('num_plantas', 'Número de plantas'),
    ('fertilizante_kg', 'Fertilizante (kg)'),
    ('concentracion_n_pct', 'Concentración de N (%)'),
    ('produccion_kg', 'Producción anual (kg)'),
    ('energia_kwh', 'Energía (kWh)'),
)


def _es_dato_lleno(valor) -> bool:
    return valor is not None and valor != ''


def _ficha_estado(pct: int) -> tuple[str, str]:
    if pct >= 80:
        return ('Completa', 'ok')
    if pct >= 40:
        return ('Parcial', 'warn')
    return ('Pendiente', 'danger')


def parse_filtros_gei(request, org) -> dict:
    from core.models import Curso

    curso_id = request.GET.get('curso') or ''
    curso_id_int = int(curso_id) if str(curso_id).isdigit() else None
    if curso_id_int and not Curso.objects.filter(pk=curso_id_int, cliente_id=org.pk).exists():
        curso_id_int = None

    desde = request.GET.get('desde') or ''
    hasta = request.GET.get('hasta') or ''
    try:
        fecha_desde = date.fromisoformat(desde) if desde else None
    except ValueError:
        fecha_desde = None
    try:
        fecha_hasta = date.fromisoformat(hasta) if hasta else None
    except ValueError:
        fecha_hasta = None
    if not fecha_desde:
        fecha_desde = date.today() - timedelta(days=365)
    if not fecha_hasta:
        fecha_hasta = date.today()

    return {
        'curso_id': curso_id_int,
        'desde': fecha_desde,
        'hasta': fecha_hasta,
        'desde_str': fecha_desde.isoformat(),
        'hasta_str': fecha_hasta.isoformat(),
    }


def queryset_fichas_org(org, filtros: dict):
    from django.db.models import Q

    from formulario.models import FichaGEI

    # Incluye fichas con cliente denormalizado O estudiante de la org
    # (cubre huérfanas cliente=NULL creadas antes de fijar FK).
    qs = FichaGEI.objects.filter(
        Q(cliente_id=org.pk) | Q(estudiante__cliente_id=org.pk)
    ).select_related(
        'estudiante', 'curso', 'resultado',
    )
    # Autoreparar huérfanas visibles para esta org
    FichaGEI.objects.filter(
        cliente__isnull=True, estudiante__cliente_id=org.pk
    ).update(cliente_id=org.pk)

    if filtros.get('curso_id'):
        qs = qs.filter(curso_id=filtros['curso_id'])
    # Inventario operativo: excluye sandbox salvo que se pida explícito
    if filtros.get('incluir_sandbox'):
        pass
    elif filtros.get('solo_sandbox'):
        qs = qs.filter(es_sandbox=True)
    else:
        qs = qs.filter(es_sandbox=False)
    qs = qs.filter(
        fecha_inicio__date__gte=filtros['desde'],
        fecha_inicio__date__lte=filtros['hasta'],
    )
    return qs.order_by('-fecha_update')


def analitica_gei(org, filtros: dict, *, page: int = 1, page_size: int = 25) -> dict:
    try:
        from formulario.models import FichaGEI  # noqa: F401
    except ImportError:
        return {'gei_ok': False}

    qs = queryset_fichas_org(org, filtros)
    total_fichas = qs.count()
    fichas_list = list(qs[:2000])

    fichas_completas = fichas_parciales = fichas_pendientes = 0
    suma_pct = 0
    for f in fichas_list:
        pct = f.completitud_pct
        suma_pct += pct
        if pct >= 100:
            fichas_completas += 1
        elif pct > 0:
            fichas_parciales += 1
        else:
            fichas_pendientes += 1
    completitud_promedio = round(suma_pct / len(fichas_list), 1) if fichas_list else 0.0

    completitud_variables = []
    if fichas_list:
        for campo, label in GEI_CAMPOS_LEGIBLES:
            con_dato = sum(1 for f in fichas_list if _es_dato_lleno(getattr(f, campo, None)))
            pct = round((con_dato / len(fichas_list)) * 100, 1)
            completitud_variables.append({
                'campo': campo,
                'label': label,
                'pct': pct,
                'con_dato': con_dato,
                'total': len(fichas_list),
            })
        completitud_variables.sort(key=lambda x: x['pct'])

    distribucion = {'0%': 0, '1-25%': 0, '26-50%': 0, '51-75%': 0, '76-99%': 0, '100%': 0}
    for f in fichas_list:
        pct = f.completitud_pct
        if pct == 0:
            distribucion['0%'] += 1
        elif pct <= 25:
            distribucion['1-25%'] += 1
        elif pct <= 50:
            distribucion['26-50%'] += 1
        elif pct <= 75:
            distribucion['51-75%'] += 1
        elif pct < 100:
            distribucion['76-99%'] += 1
        else:
            distribucion['100%'] += 1
    max_dist = max(distribucion.values()) if distribucion.values() else 1
    distribucion_view = [
        {'rango': k, 'count': v, 'pct_bar': round((v / max_dist) * 100, 1) if max_dist else 0}
        for k, v in distribucion.items()
    ]

    page = max(1, page)
    inicio = (page - 1) * page_size
    productores = []
    for f in fichas_list[inicio:inicio + page_size]:
        pct = f.completitud_pct
        estado_label, estado_key = _ficha_estado(pct)
        productores.append({
            'ficha_id': f.id,
            'productor': getattr(f.estudiante, 'nombre', '—') if f.estudiante_id else '—',
            'telefono': getattr(f.estudiante, 'telefono', '—') if f.estudiante_id else '—',
            'finca': f.nombre_finca or '—',
            'curso': f.curso.nombre if f.curso_id else '—',
            'completitud_pct': pct,
            'estado_label': estado_label,
            'estado_key': estado_key,
            'balance_tco2e': (
                f.resultado.balance_neto_tco2e
                if getattr(f, 'resultado', None) and f.resultado.balance_neto_tco2e is not None
                else None
            ),
        })

    total_paginas = max(1, (len(fichas_list) + page_size - 1) // page_size)

    return {
        'gei_ok': True,
        'fichas_total': total_fichas,
        'fichas_completas': fichas_completas,
        'fichas_parciales': fichas_parciales,
        'fichas_pendientes': fichas_pendientes,
        'completitud_promedio': completitud_promedio,
        'pct_completas': round((fichas_completas / total_fichas) * 100, 1) if total_fichas else 0,
        'completitud_variables': completitud_variables,
        'distribucion_view': distribucion_view,
        'productores': productores,
        'page': page,
        'total_paginas': total_paginas,
        'page_anterior': page - 1 if page > 1 else None,
        'page_siguiente': page + 1 if page < total_paginas else None,
        'dist_chart_labels': list(distribucion.keys()),
        'dist_chart_values': list(distribucion.values()),
        'vars_chart_labels': [v['label'] for v in completitud_variables],
        'vars_chart_values': [v['pct'] for v in completitud_variables],
    }
