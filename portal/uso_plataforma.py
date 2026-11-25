"""Uso de plataforma del portal. Cada cifra tiene denominador real; si no hay base, queda en None."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import ProgresoEstudiante, WhatsappLog
from portal.analitica_universo import estudiantes_analitica, telefonos_excluidos_analitica

_MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def _pct(num: int, den: int):
    if not den:
        return None
    return round(num * 100 / den, 1)


def _rango_mes(anio: int, mes: int):
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime(anio, mes, 1), tz)
    if mes == 12:
        fin = timezone.make_aware(datetime(anio + 1, 1, 1), tz)
    else:
        fin = timezone.make_aware(datetime(anio, mes + 1, 1), tz)
    return inicio, fin


def _meses_atras(n: int = 6):
    ahora = timezone.localtime()
    anio, mes = ahora.year, ahora.month
    pares = []
    for _ in range(n):
        pares.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio -= 1
            mes = 12
    pares.reverse()
    return pares


def _barras(filas: list[tuple[str, int]]):
    maximo = max((valor for _, valor in filas), default=0)
    salida = []
    for etiqueta, valor in filas:
        if valor and maximo:
            altura = max(8, round(valor * 100 / maximo))
        else:
            altura = 0
        salida.append({'etiqueta': etiqueta, 'valor': valor, 'altura': altura})
    return salida


def _ids_con_avance(org, ids_universo: set[int]):
    if not ids_universo:
        return set()
    return set(
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=ids_universo,
            fecha_ultimo_avance__isnull=False,
        ).values_list('estudiante_id', flat=True)
    )


def _ids_actividad(org, inicio, fin, ids_universo: set[int]):
    if not ids_universo:
        return set()
    avance = set(
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=ids_universo,
            fecha_ultimo_avance__gte=inicio,
            fecha_ultimo_avance__lt=fin,
        ).values_list('estudiante_id', flat=True)
    )
    escritos = set(
        WhatsappLog.objects.filter(
            estudiante_id__in=ids_universo,
            tipo='INCOMING',
            fecha__gte=inicio,
            fecha__lt=fin,
        ).values_list('estudiante_id', flat=True)
    )
    escritos.discard(None)
    return avance | escritos


def _ids_en_curso(ids_universo: set[int], org) -> set[int]:
    if not ids_universo:
        return set()
    return set(
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=ids_universo,
            completado=False,
        )
        .filter(Q(curso__cliente=org) | Q(curso__catalogo_menu=True, curso__cliente__isnull=True))
        .filter(
            Q(fecha_ultimo_avance__isnull=False) | Q(modulos_completados__isnull=False),
        )
        .values_list('estudiante_id', flat=True)
        .distinct()
    )


def uso_plataforma(org) -> dict:
    """Cajas y series de los últimos seis meses, para una organización."""
    ahora = timezone.now()
    registrados_qs = estudiantes_analitica(org)
    ids_universo = set(registrados_qs.values_list('id', flat=True))
    registrados = len(ids_universo)
    con_avance = _ids_con_avance(org, ids_universo)
    sin_avance = registrados_qs.exclude(id__in=con_avance).count() if con_avance else registrados

    ids_en_curso = _ids_en_curso(ids_universo, org)
    en_curso = len(ids_en_curso)
    # Histórico: quienes alguna vez iniciaron de verdad (base de retorno).
    ids_en_curso_hist = set(con_avance)

    certificados = 0
    try:
        from core.certificados.models_certificados import Certificado

        certificados = (
            Certificado.objects.filter(
                estudiante_id__in=ids_universo,
                anulado=False,
            ).count()
            if ids_universo
            else 0
        )
    except Exception:
        certificados = 0

    meses = _meses_atras(6)
    inicio_mes, fin_mes = _rango_mes(*meses[-1])
    actividad_mes = _ids_actividad(org, inicio_mes, fin_mes, ids_universo)
    activos_mes = len(actividad_mes & ids_en_curso)

    hace_14 = ahora - timedelta(days=14)
    actividad_14 = _ids_actividad(org, hace_14, ahora + timedelta(seconds=1), ids_universo)
    abandono_2s_ids = ids_en_curso - actividad_14
    abandono_2s_n = len(abandono_2s_ids)
    abandono_2s_base = en_curso

    hace_30 = ahora - timedelta(days=30)
    # Retorno: de quienes ya tenían actividad hace >30 días y están en el histórico de curso,
    # cuántos volvieron en los últimos 30.
    cohorte = _ids_actividad(org, ahora - timedelta(days=3650), hace_30, ids_universo) & ids_en_curso_hist
    recientes = _ids_actividad(org, hace_30, ahora + timedelta(seconds=1), ids_universo)
    volvieron = len(cohorte & recientes)

    uso_personas = len(actividad_mes)

    serie_activos = []
    serie_abandonos = []
    serie_uso = []
    for anio, mes in meses:
        inicio, fin = _rango_mes(anio, mes)
        etiqueta = _MESES[mes - 1]
        actividad = _ids_actividad(org, inicio, fin, ids_universo)
        serie_activos.append((etiqueta, len(actividad)))
        abandonos = registrados_qs.filter(
            fecha_registro__gte=inicio,
            fecha_registro__lt=fin,
        ).exclude(id__in=con_avance).count()
        serie_abandonos.append((etiqueta, abandonos))
        escritos = (
            WhatsappLog.objects.filter(
                estudiante_id__in=ids_universo,
                tipo='INCOMING',
                fecha__gte=inicio,
                fecha__lt=fin,
            ).values('estudiante_id').distinct().count()
            if ids_universo
            else 0
        )
        serie_uso.append((etiqueta, escritos))

    return {
        'registrados': registrados,
        'en_curso': en_curso,
        'certificados': certificados,
        # Antes «abandono»; ahora es no inicio (registrados sin avance).
        'no_inicio_pct': _pct(sin_avance, registrados),
        'no_inicio_n': sin_avance,
        'abandono_2s_pct': _pct(abandono_2s_n, abandono_2s_base),
        'abandono_2s_n': abandono_2s_n,
        'abandono_2s_base': abandono_2s_base,
        # Alias de compatibilidad para tests viejos que aún lean abandono_*.
        'abandono_pct': _pct(sin_avance, registrados),
        'abandono_n': sin_avance,
        'activos_mes': activos_mes,
        'mes_label': _MESES[meses[-1][1] - 1],
        'retorno_pct': _pct(volvieron, len(cohorte)),
        'retorno_n': volvieron,
        'retorno_base': len(cohorte),
        'uso_pct': _pct(uso_personas, registrados),
        'uso_n': uso_personas,
        'serie_activos': _barras(serie_activos),
        'serie_abandonos': _barras(serie_abandonos),
        'serie_uso': _barras(serie_uso),
    }
