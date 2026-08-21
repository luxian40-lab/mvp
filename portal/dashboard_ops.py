"""KPIs operativos y comparativa de períodos para el dashboard del portal."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.models import ProgresoEstudiante, SolicitudSoporte
from core.models_certificados import Certificado


def _mes_rango(offset_meses: int = 0):
    hoy = timezone.localdate()
    primer = hoy.replace(day=1)
    for _ in range(abs(offset_meses)):
        if offset_meses < 0:
            primer = (primer - timedelta(days=1)).replace(day=1)
        else:
            sig = primer.replace(day=28) + timedelta(days=4)
            primer = sig.replace(day=1)
    if offset_meses > 0:
        sig = primer.replace(day=28) + timedelta(days=4)
        ultimo = sig.replace(day=1) - timedelta(days=1)
    else:
        sig = primer.replace(day=28) + timedelta(days=4)
        ultimo = (sig.replace(day=1) - timedelta(days=1)) if offset_meses < 0 else hoy
    return primer, ultimo


def _delta_pct(actual: int, anterior: int) -> int | None:
    if anterior == 0:
        return None if actual == 0 else 100
    return round((actual - anterior) / anterior * 100)


def resumen_dashboard_rapido(org) -> dict:
    """
    KPIs mínimos del home del portal (solo aggregates SQL).

    No usa calcular_metricas_empresa: esa función sigue intacta para
    /portal/metricas/ y analytics. Aquí solo lo que pinta el dashboard.
    """
    progreso_q = ProgresoEstudiante.objects.filter(
        estudiante__cliente_id=org.pk,
    ).annotate(n_mods=Count('modulos_completados', distinct=True))
    total_inscritos = progreso_q.count()
    finalizados = progreso_q.filter(completado=True).count()
    en_curso = progreso_q.filter(completado=False, n_mods__gt=0).count()
    no_iniciados = progreso_q.filter(completado=False, n_mods=0).count()
    return {
        'total_inscritos': total_inscritos,
        'finalizados': finalizados,
        'en_curso': en_curso,
        'no_iniciados': no_iniciados,
    }


def comparativa_periodos(org) -> dict:
    """Mes actual vs mes anterior (certificados, PQRS nuevas, inscripciones completadas)."""
    ini_act, fin_act = _mes_rango(0)
    ini_ant, fin_ant = _mes_rango(-1)

    cert_act = Certificado.objects.filter(
        estudiante__cliente=org, emitido=True,
        fecha_emision__date__gte=ini_act, fecha_emision__date__lte=fin_act,
    ).count()
    cert_ant = Certificado.objects.filter(
        estudiante__cliente=org, emitido=True,
        fecha_emision__date__gte=ini_ant, fecha_emision__date__lte=fin_ant,
    ).count()

    pqrs_act = SolicitudSoporte.objects.filter(
        estudiante__cliente=org,
        fecha_solicitud__date__gte=ini_act, fecha_solicitud__date__lte=fin_act,
    ).count()
    pqrs_ant = SolicitudSoporte.objects.filter(
        estudiante__cliente=org,
        fecha_solicitud__date__gte=ini_ant, fecha_solicitud__date__lte=fin_ant,
    ).count()

    comp_act = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=True,
        fecha_completado__date__gte=ini_act, fecha_completado__date__lte=fin_act,
    ).count()
    comp_ant = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=True,
        fecha_completado__date__gte=ini_ant, fecha_completado__date__lte=fin_ant,
    ).count()

    return {
        'mes_actual': ini_act.strftime('%B %Y'),
        'mes_anterior': ini_ant.strftime('%B %Y'),
        'certificados': {'actual': cert_act, 'anterior': cert_ant, 'delta_pct': _delta_pct(cert_act, cert_ant)},
        'pqrs': {'actual': pqrs_act, 'anterior': pqrs_ant, 'delta_pct': _delta_pct(pqrs_act, pqrs_ant)},
        'completados': {'actual': comp_act, 'anterior': comp_ant, 'delta_pct': _delta_pct(comp_act, comp_ant)},
    }


# Tickets PQRS sin humano > este umbral = "urgente" (next best action coordinador).
PQRS_URGENTE_HORAS = 24


def operacion_del_dia(org, *, categorias_pqrs=None) -> dict:
    """Acciones pendientes del día (aggregates SQL, sin N+1 ni inbox WhatsApp)."""
    hoy = timezone.localdate()
    semana = hoy - timedelta(days=7)
    hace_30 = hoy - timedelta(days=30)
    umbral_urgente = timezone.now() - timedelta(hours=PQRS_URGENTE_HORAS)

    pqrs_q = SolicitudSoporte.objects.filter(estudiante__cliente=org, estado='pendiente')
    if categorias_pqrs is not None:
        pqrs_q = pqrs_q.filter(categoria__in=categorias_pqrs)

    # Equivalente a max_modulo_alcanzado(p) <= 0: sin módulos completados y sin módulo actual.
    # Quienes ya tienen avance (n_mods>0 o modulo_actual) y llevan 30+ días sin actividad.
    incompletos = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=False,
    ).annotate(n_mods=Count('modulos_completados', distinct=True))
    sin_avance = incompletos.filter(n_mods=0, modulo_actual__isnull=True).count()
    con_avance = incompletos.filter(Q(n_mods__gt=0) | Q(modulo_actual__isnull=False))
    inactivos_30 = con_avance.filter(
        Q(fecha_ultimo_avance__isnull=True) | Q(fecha_ultimo_avance__date__lt=hace_30),
    ).count()

    return {
        'pqrs_pendientes': pqrs_q.count(),
        'pqrs_urgentes': pqrs_q.filter(fecha_solicitud__lte=umbral_urgente).count(),
        'certificados_semana': Certificado.objects.filter(
            estudiante__cliente=org, emitido=True,
            fecha_emision__date__gte=semana,
        ).count(),
        'sin_avance': sin_avance,
        'inactivos_30_dias': inactivos_30,
    }


def narrativa_estado_programa(ops: dict | None, comparativa: dict | None, resumen: dict | None) -> dict:
    """
    Redacta el 'Estado del programa' con lenguaje de coordinador, a partir de
    cifras reales. Nunca usa frases genéricas vacías: si no hay movimiento, lo dice.
    """
    ops = ops or {}
    comparativa = comparativa or {}
    resumen = resumen or {}

    cert_mes = int((comparativa.get('certificados') or {}).get('actual') or 0)
    comp_mes = int((comparativa.get('completados') or {}).get('actual') or 0)
    comp_ant = int((comparativa.get('completados') or {}).get('anterior') or 0)
    sin_avance = int(ops.get('sin_avance') or 0)
    inactivos = int(ops.get('inactivos_30_dias') or 0)
    pqrs = int(ops.get('pqrs_pendientes') or 0)
    en_curso = int(resumen.get('en_curso') or 0)

    logros = []
    if comp_mes:
        if comp_mes == 1:
            logros.append('1 persona completó su curso este mes')
        else:
            logros.append(f'{comp_mes} personas completaron su curso este mes')
    if cert_mes:
        if cert_mes == 1:
            logros.append('se emitió 1 certificado')
        else:
            logros.append(f'se emitieron {cert_mes} certificados')

    pendientes = []
    if sin_avance:
        pendientes.append(f'{sin_avance} aún no inician')
    if inactivos:
        pendientes.append(f'{inactivos} llevan 30+ días sin actividad')
    pqrs_urg = int(ops.get('pqrs_urgentes') or 0)
    if pqrs_urg:
        pendientes.append(f'{pqrs_urg} PQRS urgentes (+{PQRS_URGENTE_HORAS}h sin respuesta)')
    elif pqrs:
        pendientes.append(f'{pqrs} PQRS por atender')

    # Titular honesto según el pulso real del programa.
    if comp_mes and comp_mes >= comp_ant:
        titulo = 'Buen ritmo de participación.'
    elif comp_mes or cert_mes:
        titulo = 'El programa sigue avanzando.'
    elif en_curso:
        titulo = 'Momento de reactivar.'
    else:
        titulo = 'Programa recién comienza.'

    if logros:
        cuerpo = _capitalizar(_unir(logros)) + '.'
        if pendientes:
            cuerpo += ' Requiere atención: ' + _unir(pendientes) + '.'
    elif pendientes:
        cuerpo = 'Sin finalizaciones nuevas este mes. Requiere atención: ' + _unir(pendientes) + '.'
    else:
        cuerpo = 'Todavía no hay actividad registrada este mes. Es buen momento para inscribir o reactivar participantes.'

    # Siguiente acción: la más relevante según los datos.
    if sin_avance:
        cta = {'label': 'Ver participantes sin avance', 'url': '/portal/estudiantes/'}
    elif pqrs:
        cta = {'label': 'Atender PQRS', 'url': '/portal/pqrs/?estado=pendiente'}
    elif inactivos:
        cta = {'label': 'Ver retención', 'url': '/portal/retencion/'}
    else:
        cta = {'label': 'Ver retención', 'url': '/portal/retencion/'}

    return {'titulo': titulo, 'cuerpo': cuerpo, 'cta': cta}


def _unir(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + ' y ' + items[-1]


def _capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto
