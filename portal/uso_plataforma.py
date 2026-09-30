"""Uso de plataforma del portal. Cada cifra tiene denominador real; si no hay base, queda en None."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import Estudiante, ProgresoEstudiante, WhatsappLog

_MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def _pct(num: int, den: int):
    if not den:
        return None
    return round(num * 100 / den, 1)


def _fmt_duracion(segundos):
    if segundos is None:
        return None
    segundos = int(round(segundos))
    if segundos < 60:
        return f'{segundos} s'
    if segundos < 3600:
        return f'{segundos // 60} min'
    horas = segundos / 3600
    return f'{horas:.1f} h'


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


def _ids_con_avance(org):
    return set(
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            fecha_ultimo_avance__isnull=False,
        ).values_list('estudiante_id', flat=True)
    )


def _ids_actividad(org, inicio, fin):
    avance = set(
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            fecha_ultimo_avance__gte=inicio,
            fecha_ultimo_avance__lt=fin,
        ).values_list('estudiante_id', flat=True)
    )
    escritos = set(
        WhatsappLog.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            tipo='INCOMING',
            fecha__gte=inicio,
            fecha__lt=fin,
        ).values_list('estudiante_id', flat=True)
    )
    escritos.discard(None)
    return avance | escritos


def _tiempo_respuesta_segundos(org, ahora):
    desde = ahora - timedelta(days=30)
    filas = (
        WhatsappLog.objects.filter(estudiante__cliente=org, fecha__gte=desde)
        .order_by('fecha', 'id')
        .values_list('telefono', 'tipo', 'fecha')[:800]
    )
    pendiente = {}
    deltas = []
    for telefono, tipo, fecha in filas:
        tel = (telefono or '').strip()
        if not tel or fecha is None:
            continue
        if tipo == 'INCOMING':
            pendiente[tel] = fecha
        elif tipo == 'SENT' and tel in pendiente:
            delta = (fecha - pendiente.pop(tel)).total_seconds()
            if 0 <= delta <= 24 * 3600:
                deltas.append(delta)
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def uso_plataforma(org) -> dict:
    """Nueve cajas y tres series de los últimos seis meses, para una organización."""
    ahora = timezone.now()
    registrados_qs = Estudiante.objects.filter(cliente=org, activo=True)
    registrados = registrados_qs.count()
    con_avance = _ids_con_avance(org)
    sin_avance = registrados_qs.exclude(id__in=con_avance).count() if con_avance else registrados

    en_curso = (
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            completado=False,
        )
        .filter(Q(curso__cliente=org) | Q(curso__catalogo_menu=True, curso__cliente__isnull=True))
        .values('estudiante_id')
        .distinct()
        .count()
    )
    finalizaron = (
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            completado=True,
        )
        .values('estudiante_id')
        .distinct()
        .count()
    )

    certificados = 0
    try:
        from core.models_certificados import Certificado

        certificados = Certificado.objects.filter(
            estudiante__cliente=org,
            anulado=False,
        ).count()
    except Exception:
        certificados = 0

    meses = _meses_atras(6)
    inicio_mes, fin_mes = _rango_mes(*meses[-1])
    activos_mes = len(_ids_actividad(org, inicio_mes, fin_mes))

    hace_30 = ahora - timedelta(days=30)
    cohorte = _ids_actividad(org, ahora - timedelta(days=3650), hace_30)
    recientes = _ids_actividad(org, hace_30, ahora + timedelta(seconds=1))
    volvieron = len(cohorte & recientes)

    respuesta = _tiempo_respuesta_segundos(org, ahora)
    uso_personas = activos_mes

    serie_activos = []
    serie_abandonos = []
    serie_uso = []
    for anio, mes in meses:
        inicio, fin = _rango_mes(anio, mes)
        etiqueta = _MESES[mes - 1]
        actividad = _ids_actividad(org, inicio, fin)
        serie_activos.append((etiqueta, len(actividad)))
        abandonos = registrados_qs.filter(
            fecha_registro__gte=inicio,
            fecha_registro__lt=fin,
        ).exclude(id__in=con_avance).count()
        serie_abandonos.append((etiqueta, abandonos))
        escritos = WhatsappLog.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
            tipo='INCOMING',
            fecha__gte=inicio,
            fecha__lt=fin,
        ).values('estudiante_id').distinct().count()
        serie_uso.append((etiqueta, escritos))

    return {
        'registrados': registrados,
        'en_curso': en_curso,
        'certificados': certificados,
        'abandono_pct': _pct(sin_avance, registrados),
        'abandono_n': sin_avance,
        'finalizacion_pct': _pct(finalizaron, registrados),
        'finalizacion_n': finalizaron,
        'activos_mes': activos_mes,
        'mes_label': _MESES[meses[-1][1] - 1],
        'respuesta': _fmt_duracion(respuesta),
        'retorno_pct': _pct(volvieron, len(cohorte)),
        'retorno_n': volvieron,
        'retorno_base': len(cohorte),
        'uso_pct': _pct(uso_personas, registrados),
        'uso_n': uso_personas,
        'serie_activos': _barras(serie_activos),
        'serie_abandonos': _barras(serie_abandonos),
        'serie_uso': _barras(serie_uso),
    }
