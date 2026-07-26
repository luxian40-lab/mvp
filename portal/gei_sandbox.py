"""Sandbox GEI: cupos de prueba editables en el portal B2B."""
from __future__ import annotations

from typing import Any

GEI_SANDBOX_CUPOS_DEFAULT = 10

# Campos editables desde el formulario sandbox del portal.
CAMPOS_SANDBOX_EDITABLES = (
    'nombre_finca',
    'area_ha',
    'num_plantas',
    'tipo_fertilizante',
    'fertilizante_kg',
    'concentracion_n_pct',
    'tipo_cultivo',
    'alta_mecanizacion',
    'usa_enmiendas_cal',
    'anio_datos_energia',
    'tipo_combustible',
    'combustible_gal',
    'energia_kwh',
    'residuos_ton',
    'manejo_residuos',
    'produccion_kg',
    'tiene_bosque',
    'area_bosque_ha',
    'referencia_balance_tco2e',
)


def margen_error_pct(calculado: float | None, referencia: float | None) -> float | None:
    """|calc - ref| / |ref| * 100. None si no se puede comparar."""
    if calculado is None or referencia is None:
        return None
    try:
        calc = float(calculado)
        ref = float(referencia)
    except (TypeError, ValueError):
        return None
    if ref == 0:
        return 0.0 if calc == 0 else 100.0
    return round(abs(calc - ref) / abs(ref) * 100.0, 2)


def queryset_sandbox_org(org):
    from django.db.models import Q

    from formulario.models import FichaGEI

    return (
        FichaGEI.objects.filter(es_sandbox=True)
        .filter(Q(cliente_id=org.pk) | Q(estudiante__cliente_id=org.pk))
        .select_related('estudiante', 'curso', 'resultado')
        .order_by('estudiante__nombre', 'id')
    )


def asegurar_cupos_sandbox(org, *, cupos: int = GEI_SANDBOX_CUPOS_DEFAULT, curso=None):
    """Crea hasta N productores + fichas sandbox para la organización."""
    from core.models import Curso, Estudiante
    from formulario.models import FichaGEI

    cupos = max(1, min(int(cupos or GEI_SANDBOX_CUPOS_DEFAULT), 20))
    if curso is None:
        curso = (
            Curso.objects.filter(cliente_id=org.pk, tiene_formulario_gei=True, activo=True)
            .order_by('id')
            .first()
        ) or Curso.objects.filter(cliente_id=org.pk, activo=True).order_by('id').first()

    existentes = list(queryset_sandbox_org(org))
    for i in range(1, cupos + 1):
        slot = f'{i:02d}'
        # Cedula/telefono sin guiones: Estudiante.save() elimina [-.\s]
        cedula = f'SBGEI{org.pk:05d}{i:02d}'
        telefono = f'5799{org.pk:05d}{i:02d}'
        est = Estudiante.objects.filter(cedula=cedula).first()
        if not est:
            est = Estudiante.objects.create(
                cliente=org,
                cedula=cedula,
                nombre=f'Sandbox GEI {slot}',
                telefono=telefono,
                activo=True,
            )
        else:
            updates = []
            if est.cliente_id != org.pk:
                est.cliente = org
                updates.append('cliente')
            if not (est.nombre or '').startswith('Sandbox'):
                est.nombre = f'Sandbox GEI {slot}'
                updates.append('nombre')
            if not est.activo:
                est.activo = True
                updates.append('activo')
            if updates:
                est.save(update_fields=updates)

        ficha = (
            FichaGEI.objects.filter(estudiante=est, es_sandbox=True)
            .order_by('id')
            .first()
        )
        if not ficha:
            FichaGEI.objects.create(
                estudiante=est,
                cliente=org,
                curso=curso,
                es_sandbox=True,
                nombre_finca=f'Finca ensayo {slot}',
            )
        else:
            updates = []
            if ficha.cliente_id != org.pk:
                ficha.cliente = org
                updates.append('cliente')
            if curso and ficha.curso_id != curso.pk:
                ficha.curso = curso
                updates.append('curso')
            if updates:
                ficha.save(update_fields=updates)

    return list(queryset_sandbox_org(org)[:cupos])


def _parse_bool(raw: str | None):
    if raw is None or raw == '':
        return None
    v = str(raw).strip().lower()
    if v in ('1', 'true', 'si', 'sí', 'yes', 'on'):
        return True
    if v in ('0', 'false', 'no', 'off'):
        return False
    return None


def _parse_float(raw: str | None):
    if raw is None or str(raw).strip() == '':
        return None
    try:
        return float(str(raw).replace(',', '.').strip())
    except ValueError:
        return None


def _parse_int(raw: str | None):
    if raw is None or str(raw).strip() == '':
        return None
    try:
        return int(float(str(raw).replace(',', '.').strip()))
    except ValueError:
        return None


def aplicar_post_sandbox(ficha, post) -> list[str]:
    """Aplica POST al ficha sandbox. Retorna lista de errores."""
    errores: list[str] = []
    bool_fields = {'alta_mecanizacion', 'usa_enmiendas_cal', 'tiene_bosque'}
    int_fields = {'num_plantas', 'anio_datos_energia'}
    float_fields = {
        'area_ha', 'fertilizante_kg', 'concentracion_n_pct', 'combustible_gal',
        'energia_kwh', 'residuos_ton', 'produccion_kg', 'area_bosque_ha',
        'referencia_balance_tco2e',
    }
    choice_fields = {
        'tipo_fertilizante', 'tipo_cultivo', 'tipo_combustible', 'manejo_residuos',
    }

    for campo in CAMPOS_SANDBOX_EDITABLES:
        raw = post.get(campo)
        if campo == 'nombre_finca':
            setattr(ficha, campo, (raw or '').strip()[:200])
            continue
        if campo in bool_fields:
            setattr(ficha, campo, _parse_bool(raw))
            continue
        if campo in int_fields:
            val = _parse_int(raw)
            if raw not in (None, '') and val is None:
                errores.append(f'{campo}: número inválido')
            else:
                setattr(ficha, campo, val)
            continue
        if campo in float_fields:
            val = _parse_float(raw)
            if raw not in (None, '') and val is None:
                errores.append(f'{campo}: número inválido')
            else:
                setattr(ficha, campo, val)
            continue
        if campo in choice_fields:
            setattr(ficha, campo, (raw or '').strip())
            continue

    if errores:
        return errores

    ficha.es_sandbox = True
    ficha.save()
    return []


def resumen_slot(ficha) -> dict[str, Any]:
    res = getattr(ficha, 'resultado', None)
    calc = res.balance_neto_tco2e if res else None
    ref = ficha.referencia_balance_tco2e
    return {
        'ficha': ficha,
        'completitud': ficha.completitud_pct,
        'balance': calc,
        'referencia': ref,
        'margen_error_pct': margen_error_pct(calc, ref),
        'evaluacion': res.get_evaluacion_display() if res and res.evaluacion else '—',
    }
