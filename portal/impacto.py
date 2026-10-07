"""Doce indicadores núcleo para Portal → Analítica → Impacto.

S1 y S2 salen del sistema (A). El resto se muestra pendiente hasta que exista
captura. No se inventa un porcentaje. Un corte con n < 10 no publica %.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from core.models import Estudiante, ProgresoEstudiante, WhatsappLog
from core.models_certificados import Certificado

MIN_PUBLICACION = 10
DIAS_PERIODO = 90
DIAS_RETENCION = 30

_PENDIENTES = (
    ('S3', 'Ganancia de aprendizaje', 'A', 'Mini-diagnóstico módulo 0 y final.'),
    ('S4', 'Acceso nuevo', 'B', 'Pregunta de onboarding: ¿había recibido capacitación formal?'),
    ('E1', 'Gestión financiera', 'B', 'Cierre del agente de finanzas: registro ≥1 mes.'),
    ('E2', 'Decisión comercial informada', 'B', 'Precio con costos, canal nuevo o primera venta (90 días).'),
    ('E3', 'Cambio en ingreso', 'B/C', 'Encuesta a 90 y 180 días. Solo contribución.'),
    ('A1', 'Prácticas mejoradas adoptadas', 'B/C', 'Lista por sector y cierre «¿lo aplicaste?».',),
    ('A2', 'Área o unidades bajo prácticas', 'B/C', 'A1 × área declarada. Solo contribución.'),
    ('A3', 'Decisiones con información climática', 'A/B', 'Nat + Open-Meteo y cierre a 7 días.'),
)


def corte_edad(edad) -> str:
    if edad is None:
        return ''
    try:
        n = int(edad)
    except (TypeError, ValueError):
        return ''
    if 14 <= n <= 28:
        return 'joven'
    if n >= 50:
        return 'mayor_50'
    if n >= 29:
        return 'adulto'
    return ''


def _pct(num: int, den: int):
    if den < MIN_PUBLICACION:
        return None
    if not den:
        return None
    return round(num * 100 / den, 1)


def _corte_fila(n: int, den: int) -> dict:
    pct = _pct(n, den)
    nota = ''
    if den < MIN_PUBLICACION:
        nota = f'n < {MIN_PUBLICACION}; no se publica el porcentaje'
    return {'n': n, 'denominador': den, 'pct': pct, 'nota': nota}


def _pendiente(codigo: str, nombre: str, evidencia: str, nota: str, *, rotulo: str = '') -> dict:
    return {
        'codigo': codigo,
        'nombre': nombre,
        'evidencia': evidencia,
        'estado': 'pendiente_captura',
        'numerador': None,
        'denominador': None,
        'pct': None,
        'rotulo': rotulo,
        'nota': nota,
    }


def impacto_nucleo(org, *, ahora=None) -> dict:
    ahora = ahora or timezone.now()
    inicio = ahora - timedelta(days=DIAS_PERIODO)
    estudiantes = list(
        Estudiante.objects.filter(cliente=org, activo=True).only(
            'id', 'telefono', 'genero', 'edad',
            'rural_disperso', 'pdet', 'consentimiento_impacto',
        )
    )
    ids = [e.id for e in estudiantes]
    tels = [e.telefono for e in estudiantes if e.telefono]

    qs_in = WhatsappLog.objects.filter(
        fecha__gte=inicio,
        fecha__lt=ahora,
        tipo='INCOMING',
    )
    alcance_ids = set(qs_in.filter(estudiante_id__in=ids).values_list('estudiante_id', flat=True))
    tel_a_id = {e.telefono: e.id for e in estudiantes if e.telefono}
    if tels:
        for tel, eid in qs_in.filter(telefono__in=tels).values_list('telefono', 'estudiante_id'):
            alcance_ids.add(eid or tel_a_id.get(tel))
    alcance_ids.discard(None)
    alcance_ids &= set(ids)

    por_id = {e.id: e for e in estudiantes}
    muestra = [por_id[i] for i in alcance_ids if i in por_id]
    den = len(muestra)
    n_muj = sum(1 for e in muestra if e.genero == 'F')
    n_jov = sum(1 for e in muestra if corte_edad(e.edad) == 'joven')
    n_50 = sum(1 for e in muestra if corte_edad(e.edad) == 'mayor_50')
    n_rural = sum(1 for e in muestra if e.rural_disperso is True)
    n_pdet = sum(1 for e in muestra if e.pdet is True)

    s1 = {
        'codigo': 'S1',
        'nombre': 'Alcance inclusivo',
        'evidencia': 'A',
        'estado': 'ok',
        'numerador': den,
        'denominador': den,
        'pct': 100.0 if den else None,
        'periodo_dias': DIAS_PERIODO,
        'nota': (
            f'Personas únicas con ≥1 mensaje entrante en {DIAS_PERIODO} días. '
            f'Fuente: WhatsappLog.'
        ),
        'rotulo': '',
        'cortes': {
            'mujeres': _corte_fila(n_muj, den),
            'jovenes': _corte_fila(n_jov, den),
            'mayor_50': _corte_fila(n_50, den),
            'rural_disperso': _corte_fila(n_rural, den),
            'pdet': _corte_fila(n_pdet, den),
        },
    }

    inscritos_ids = set(
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
        ).values_list('estudiante_id', flat=True)
    )
    n_inscritos = len(inscritos_ids)
    n_certs = (
        Certificado.objects.filter(
            estudiante_id__in=inscritos_ids,
            emitido=True,
        )
        .values('estudiante_id')
        .distinct()
        .count()
        if inscritos_ids
        else 0
    )
    corte_30 = ahora - timedelta(days=DIAS_RETENCION)
    cohortes = list(
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=inscritos_ids,
            fecha_inicio__lte=corte_30,
        ).values_list('estudiante_id', 'fecha_inicio')
    )
    vistos = set()
    ret_den = 0
    ret_num = 0
    for eid, fi in cohortes:
        if eid in vistos:
            continue
        vistos.add(eid)
        ret_den += 1
        umbral = fi + timedelta(days=DIAS_RETENCION)
        act = ProgresoEstudiante.objects.filter(
            estudiante_id=eid,
            fecha_ultimo_avance__gte=umbral,
        ).exists()
        if not act:
            act = WhatsappLog.objects.filter(
                estudiante_id=eid,
                tipo='INCOMING',
                fecha__gte=umbral,
            ).exists()
        if act:
            ret_num += 1

    s2 = {
        'codigo': 'S2',
        'nombre': 'Finalización y retención',
        'evidencia': 'A',
        'estado': 'ok',
        'certificados': n_certs,
        'inscritos': n_inscritos,
        'numerador': n_certs,
        'denominador': n_inscritos,
        'pct': _pct(n_certs, n_inscritos) if n_inscritos else None,
        'nota': 'Certificados emitidos / inscritos (filas de progreso, personas distintas).',
        'rotulo': '',
        'retencion_30': {
            'numerador': ret_num,
            'denominador': ret_den,
            'pct': _pct(ret_num, ret_den) if ret_den else None,
            'nota': (
                f'De quienes se inscribieron hace ≥{DIAS_RETENCION} días, '
                'quién tuvo avance o mensaje después del día 30.'
            ),
        },
    }

    n_g1 = sum(1 for e in estudiantes if e.consentimiento_impacto)
    g1 = {
        'codigo': 'G1',
        'nombre': 'Consentimiento específico',
        'evidencia': 'A',
        'estado': 'ok',
        'numerador': n_g1,
        'denominador': len(estudiantes),
        'pct': _pct(n_g1, len(estudiantes)) if estudiantes else None,
        'nota': (
            'Consentimiento para reportes de impacto, distinto del habeas operativo. '
            'Meta: 100 %. Menores: acudiente.'
        ),
        'rotulo': '',
    }

    por_codigo = {'S1': s1, 'S2': s2}
    for codigo, nombre, evidencia, nota in _PENDIENTES:
        rotulo = 'contribución' if codigo in ('E3', 'A2') else ''
        por_codigo[codigo] = _pendiente(codigo, nombre, evidencia, nota, rotulo=rotulo)

    por_codigo['G1'] = g1

    con_valor = [
        ind for ind in por_codigo.values()
        if ind.get('estado') == 'ok' and ind.get('denominador') is not None
    ]
    a_o_c = [
        ind for ind in con_valor
        if (ind.get('evidencia') or '')[:1] in ('A', 'C')
    ]
    g2 = {
        'codigo': 'G2',
        'nombre': 'Calidad de la evidencia',
        'evidencia': 'A',
        'estado': 'ok',
        'numerador': len(a_o_c),
        'denominador': len(con_valor),
        'pct': _pct(len(a_o_c), len(con_valor)) if con_valor else None,
        'nota': (
            'De los indicadores con valor en este tablero, cuántos son A o C. '
            'La tasa de respuesta a encuestas aparece cuando exista captura B.'
        ),
        'rotulo': '',
    }
    por_codigo['G2'] = g2

    grupos = {
        'Social': [por_codigo[c] for c in ('S1', 'S2', 'S3', 'S4')],
        'Económico': [por_codigo[c] for c in ('E1', 'E2', 'E3')],
        'Ambiental': [por_codigo[c] for c in ('A1', 'A2', 'A3')],
        'Gobernanza': [por_codigo[c] for c in ('G1', 'G2')],
    }
    return {
        'periodo_dias': DIAS_PERIODO,
        'min_publicacion': MIN_PUBLICACION,
        'por_codigo': por_codigo,
        'grupos': grupos,
    }
