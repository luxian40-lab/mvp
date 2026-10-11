"""Datos del inicio del admin. Un dict, consultas agregadas, cache 60 s por usuario.

Meta (estado y calidad de la línea) no entra aquí: lo pide un endpoint aparte.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_TTL = 60
META_LINEA_TTL = 600
META_LINEA_TTL_FALLO = 60

_TOOLTIP_FALLOS = (
    'Envíos fallidos de WhatsApp en 24 h, más eventos de webhook Meta con error. '
    'Las tareas Celery fallidas no entran: no hay historial consultable (Sin dato).'
)

_DIAS = (
    'lunes',
    'martes',
    'miércoles',
    'jueves',
    'viernes',
    'sábado',
    'domingo',
)
_MESES = (
    '',
    'enero',
    'febrero',
    'marzo',
    'abril',
    'mayo',
    'junio',
    'julio',
    'agosto',
    'septiembre',
    'octubre',
    'noviembre',
    'diciembre',
)


def home_para(user, *, force: bool = False) -> dict:
    """Dict del inicio. Cache 60 s por usuario. force=True lo vuelve a calcular."""
    key = _cache_key(user)
    if not force and key:
        try:
            hit = cache.get(key)
        except Exception:
            hit = None
        if isinstance(hit, dict):
            return hit
    data = construir_inicio(user)
    if key:
        try:
            cache.set(key, data, CACHE_TTL)
        except Exception:
            logger.info('cache inicio no disponible', exc_info=True)
    return data


def invalidar_home(user) -> None:
    key = _cache_key(user)
    if not key:
        return
    try:
        cache.delete(key)
    except Exception:
        logger.info('no se pudo invalidar el cache del inicio', exc_info=True)


def badge_nav(user, clave: str) -> str:
    """Conteo para el menú. Vacío si es 0, para que Unfold no pinte el badge."""
    data = home_para(user)
    try:
        n = int((data.get('badges') or {}).get(clave) or 0)
    except (TypeError, ValueError):
        n = 0
    return str(n) if n else ''


def estado_lineas() -> list[dict]:
    """Estado y calidad en Meta. Nunca lanza. Cache 10 min por línea."""
    try:
        from core.plantilla_meta_editor import lineas_disponibles
    except Exception:
        logger.info('lineas de whatsapp no disponibles', exc_info=True)
        return []
    salida = []
    for phone_id, nombre in lineas_disponibles():
        salida.append(estado_una_linea(str(phone_id), str(nombre)))
    return salida


def estado_una_linea(phone_id: str, nombre: str) -> dict:
    phone_id = (phone_id or '').strip()
    base = {
        'id': phone_id,
        'nombre': nombre or 'Línea',
        'estado': 'Sin dato',
        'numero': 'Sin dato',
        'calidad': 'Sin dato',
    }
    if not phone_id:
        return base
    key = f'eki-meta-linea-v1-{phone_id}'
    try:
        hit = cache.get(key)
    except Exception:
        hit = None
    if isinstance(hit, dict) and hit.get('id') == phone_id:
        return hit
    try:
        dato = _graph_linea(phone_id)
    except Exception:
        logger.info('meta linea sin dato phone=%s', phone_id, exc_info=True)
        try:
            cache.set(key, base, META_LINEA_TTL_FALLO)
        except Exception:
            pass
        return base
    dato['id'] = phone_id
    dato['nombre'] = nombre or 'Línea'
    try:
        cache.set(key, dato, META_LINEA_TTL)
    except Exception:
        pass
    return dato


def construir_inicio(user) -> dict:
    ahora = timezone.localtime()
    saludo = _saludo(user, ahora.hour)
    fecha = (
        f'{_DIAS[ahora.weekday()]} {ahora.day} de {_MESES[ahora.month]}'
        f' · actualizado {ahora:%H:%M}'
    )
    vacio = _vacio(saludo, fecha, ahora)
    if user is None or not getattr(user, 'is_authenticated', False):
        return vacio
    try:
        return _armar(user, ahora, saludo, fecha)
    except Exception:
        logger.exception('inicio admin no se pudo armar')
        return vacio


def _armar(user, ahora, saludo: str, fecha: str) -> dict:
    from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante, WhatsappLog
    from core.models_meta_webhook import MetaWebhookEvento

    puede_est = _puede(user, 'core.view_estudiante')
    puede_cert = _puede(user, 'core.view_certificado')
    puede_wh = _puede(user, 'core.view_metawebhookevento')
    puede_plantilla = _puede(user, 'core.view_plantillameta')
    puede_modulo = _puede(user, 'core.view_modulo')
    puede_log = _puede(user, 'core.view_whatsapplog')

    hace_24 = ahora - timedelta(hours=24)
    hace_5 = ahora - timedelta(minutes=5)
    inicio_mes = timezone.make_aware(
        datetime.combine(ahora.date().replace(day=1), time.min),
        ahora.tzinfo,
    )

    activas = 0
    sin_progreso = 0
    completaron = 0
    avance = 0
    if puede_est:
        activas = Estudiante.objects.filter(activo=True).count()
        sin_progreso = (
            Estudiante.objects.filter(activo=True)
            .annotate(np=Count('progresos'))
            .filter(np=0)
            .count()
        )
        completaron = (
            ProgresoEstudiante.objects.filter(
                completado=True,
                fecha_completado__gte=inicio_mes,
            )
            .values('estudiante_id')
            .distinct()
            .count()
        )
        avance = _avance_promedio()

    envios_fallidos = 0
    if puede_log:
        envios_fallidos = (
            WhatsappLog.objects.filter(tipo='SENT', fecha__gte=hace_24)
            .filter(
                Q(estado__iexact='failed')
                | Q(estado__iexact='undelivered')
                | Q(estado__iexact='error')
                | (Q(error_codigo__isnull=False) & ~Q(error_codigo=''))
            )
            .count()
        )

    errores_24 = 0
    sin_respuesta = 0
    sin_respuesta_24 = 0
    errores = []
    if puede_wh:
        agg = MetaWebhookEvento.objects.aggregate(
            errores_24=Count(
                'id',
                filter=Q(resultado='error', recibido_en__gte=hace_24),
            ),
            sin_respuesta=Count(
                'id',
                filter=Q(resultado='recibido', recibido_en__lte=hace_5),
            ),
            sin_respuesta_24=Count(
                'id',
                filter=Q(
                    resultado='recibido',
                    recibido_en__lte=hace_5,
                    recibido_en__gte=hace_24,
                ),
            ),
        )
        errores_24 = int(agg['errores_24'] or 0)
        sin_respuesta = int(agg['sin_respuesta'] or 0)
        sin_respuesta_24 = int(agg['sin_respuesta_24'] or 0)
        errores = _errores_recientes()

    certs = 0
    if puede_cert:
        from core.models_certificados import Certificado

        certs = Certificado.objects.filter(
            emitido=True,
            enviado_whatsapp=False,
        ).count()

    plantillas = 0
    if puede_plantilla:
        from core.models_campana_meta import PlantillaMeta

        plantillas = PlantillaMeta.objects.filter(estado='PENDING').count()

    borradores = 0
    if puede_modulo:
        borradores = (
            Modulo.objects.filter(publicado_wa=False, curso__activo=True)
            .exclude(curso__modo_aula=Curso.MODO_AULA_CLASES)
            .count()
        )

    mensajes = _mensajes_14_dias() if puede_log else _serie_vacia(ahora)
    lineas = _lineas_locales(
        mensajes_hoy=mensajes['hoy'] if puede_log else None,
        sin_respuesta_24=sin_respuesta_24 if puede_wh else None,
        puede_log=puede_log,
        puede_wh=puede_wh,
    )

    acciones = []
    if puede_cert and certs:
        acciones.append({
            'clave': 'certs',
            'tono': 'ambar',
            'titulo': 'Certificados por enviar por WhatsApp',
            'conteo': certs,
            'contexto': 'Emitidos y todavía no salen por WhatsApp.',
            'url': '/admin/envio-certificados/',
        })
    if puede_est and sin_progreso:
        acciones.append({
            'clave': 'sin_progreso',
            'tono': 'ambar',
            'titulo': 'Sin progreso',
            'conteo': sin_progreso,
            'contexto': 'Personas activas sin ningún curso empezado.',
            'url': '/admin/core/estudiante/?eki_progreso=sin',
        })
    if puede_wh and sin_respuesta:
        acciones.append({
            'clave': 'sin_respuesta',
            'tono': 'ambar',
            'titulo': 'Mensajes recibidos sin respuesta',
            'conteo': sin_respuesta,
            'contexto': 'Llegaron hace más de 5 minutos y siguen en recibido.',
            'url': '/admin/core/metawebhookevento/?resultado__exact=recibido',
        })
    if puede_plantilla and plantillas:
        acciones.append({
            'clave': 'plantillas',
            'tono': 'azul',
            'titulo': 'Plantillas pendientes en Meta',
            'conteo': plantillas,
            'contexto': 'Estado Pendiente. Meta aún no las aprueba.',
            'url': '/admin/core/plantillameta/?estado__exact=PENDING',
        })
    if puede_modulo and borradores:
        acciones.append({
            'clave': 'borradores',
            'tono': 'gris',
            'titulo': 'Módulos en borrador',
            'conteo': borradores,
            'contexto': 'Cursos activos. El campo no los recibe hasta publicarlos.',
            'url': '/admin/core/modulo/?publicado_wa__exact=0',
        })

    return {
        'saludo': saludo,
        'fecha_linea': fecha,
        'actualizado': ahora.strftime('%H:%M'),
        'twilio_mes': _twilio_mes(),
        'cifras': [
            {'clave': 'activas', 'label': 'Personas activas', 'valor': str(activas)},
            {'clave': 'avance', 'label': 'Avance promedio', 'valor': f'{avance}%'},
            {
                'clave': 'completaron',
                'label': 'Completaron este mes',
                'valor': str(completaron),
            },
            {
                'clave': 'fallos',
                'label': 'Fallos en 24 h',
                'valor': str(envios_fallidos + errores_24),
                'tooltip': _TOOLTIP_FALLOS,
            },
        ],
        'acciones': acciones[:6],
        'lineas': lineas,
        'chart_data': mensajes['chart_data'],
        'chart_options': mensajes['chart_options'],
        'mensajes_nota': mensajes['nota'],
        'errores': errores,
        'errores_tabla': {
            'headers': ['Hora', 'Qué pasó', 'Teléfono', 'Línea'],
            'rows': [
                {'cols': [e['hora'], e['que'], e['sufijo'], e['linea']]}
                for e in errores
            ],
        },
        'errores_url': '/admin/core/metawebhookevento/?resultado__exact=error',
        'badges': {
            'plantillas': plantillas if puede_plantilla else 0,
            'modulos': borradores if puede_modulo else 0,
        },
    }


def _lineas_locales(*, mensajes_hoy, sin_respuesta_24, puede_log: bool, puede_wh: bool) -> list[dict]:
    try:
        from core.plantilla_meta_editor import lineas_disponibles

        configuradas = list(lineas_disponibles())
    except Exception:
        logger.info('no se leyeron las lineas configuradas', exc_info=True)
        configuradas = []
    una = len(configuradas) == 1
    filas = []
    for phone_id, nombre in configuradas:
        filas.append({
            'id': phone_id,
            'nombre': nombre,
            'mensajes_hoy': mensajes_hoy if una and puede_log else None,
            'sin_respuesta_24h': sin_respuesta_24 if una and puede_wh else None,
            'aproximado': not una,
        })
    return filas


def _mensajes_14_dias() -> dict:
    from django.db.models.functions import TruncDate

    from core.models import WhatsappLog

    ahora = timezone.localtime()
    hoy = ahora.date()
    desde = hoy - timedelta(days=13)
    inicio = timezone.make_aware(datetime.combine(desde, time.min), ahora.tzinfo)
    filas = (
        WhatsappLog.objects.filter(canal='meta', fecha__gte=inicio)
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(n=Count('id'))
    )
    por_dia = {}
    for fila in filas:
        dia = fila['dia']
        if hasattr(dia, 'date'):
            dia = dia.date()
        por_dia[dia] = int(fila['n'] or 0)
    labels = []
    data = []
    for i in range(13, -1, -1):
        dia = hoy - timedelta(days=i)
        labels.append(dia.strftime('%d/%m'))
        data.append(por_dia.get(dia, 0))
    import json

    chart_data = json.dumps({
        'labels': labels,
        'datasets': [{
            'label': 'Meta',
            'data': data,
            'backgroundColor': 'var(--color-primary-500)',
            'borderColor': 'var(--color-primary-600)',
            'borderWidth': 0,
        }],
    })
    chart_options = json.dumps({
        'scales': {
            'x': {'stacked': True},
            'y': {'stacked': True, 'beginAtZero': True},
        },
        'plugins': {'legend': {'display': True}},
    })
    return {
        'hoy': por_dia.get(hoy, 0),
        'chart_data': chart_data,
        'chart_options': chart_options,
        'nota': (
            'Una serie Meta. El historial no guarda la línea, '
            'así que principal y línea 2 no se separan.'
        ),
    }


def _serie_vacia(ahora) -> dict:
    import json

    hoy = ahora.date()
    labels = [(hoy - timedelta(days=i)).strftime('%d/%m') for i in range(13, -1, -1)]
    return {
        'hoy': None,
        'chart_data': json.dumps({
            'labels': labels,
            'datasets': [{
                'label': 'Meta',
                'data': [0] * 14,
                'backgroundColor': 'var(--color-primary-500)',
            }],
        }),
        'chart_options': '{}',
        'nota': '',
    }


def _errores_recientes() -> list[dict]:
    from core.models_meta_webhook import MetaWebhookEvento

    filas = []
    for ev in MetaWebhookEvento.objects.filter(resultado='error').order_by('-recibido_en')[:5]:
        cuando = timezone.localtime(ev.recibido_en) if ev.recibido_en else None
        telefono = ev.telefono or ''
        sufijo = telefono[-4:] if telefono else '—'
        que = (ev.error or ev.tipo or 'Error de webhook').strip()
        filas.append({
            'hora': cuando.strftime('%H:%M') if cuando else '—',
            'que': que[:80],
            'sufijo': sufijo,
            'linea': 'Sin dato',
        })
    return filas


def _avance_promedio() -> int:
    """Porcentaje medio. Denominador = módulos publicados en WhatsApp (o todos, si el curso es de clases)."""
    from core.models import ProgresoEstudiante

    filas = list(
        ProgresoEstudiante.objects.annotate(
            total=Count(
                'curso__modulos',
                filter=Q(curso__modo_aula='clases') | Q(curso__modulos__publicado_wa=True),
                distinct=True,
            ),
            hechos=Count(
                'modulos_completados',
                filter=(
                    Q(curso__modo_aula='clases')
                    | Q(modulos_completados__modulo__publicado_wa=True)
                ),
                distinct=True,
            ),
        )
        .filter(total__gt=0)
        .values_list('hechos', 'total')
    )
    if not filas:
        agg = ProgresoEstudiante.objects.aggregate(
            total=Count('id'),
            done=Count('id', filter=Q(completado=True)),
        )
        total = int(agg['total'] or 0)
        if not total:
            return 0
        return int(round(int(agg['done'] or 0) / total * 100))
    ratios = [hechos / total for hechos, total in filas if total]
    if not ratios:
        return 0
    return int(round(sum(ratios) / len(ratios) * 100))


def _graph_linea(phone_id: str) -> dict:
    import requests

    from core.meta_waba import _headers, _version

    headers = _headers()
    if not headers:
        raise RuntimeError('sin token de Meta')
    url = f'https://graph.facebook.com/{_version()}/{phone_id}'
    resp = requests.get(
        url,
        params={'fields': 'display_phone_number,quality_rating,status'},
        headers=headers,
        timeout=3,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict) or payload.get('error'):
        raise RuntimeError('graph sin dato')
    status = str(payload.get('status') or '').strip().upper()
    if status == 'CONNECTED':
        estado = 'Conectada'
    elif status:
        estado = 'Con problema'
    else:
        estado = 'Sin dato'
    numero = _ocultar_ultimos(str(payload.get('display_phone_number') or ''))
    return {
        'estado': estado,
        'numero': numero or 'Sin dato',
        'calidad': _calidad(payload.get('quality_rating')),
    }


def _calidad(raw) -> str:
    return {
        'GREEN': 'Alta',
        'YELLOW': 'Media',
        'RED': 'Baja',
    }.get(str(raw or '').strip().upper(), 'Sin dato')


def _ocultar_ultimos(numero: str) -> str:
    numero = (numero or '').strip()
    if not numero:
        return ''
    chars = list(numero)
    vistos = 0
    for i in range(len(chars) - 1, -1, -1):
        if chars[i].isdigit():
            chars[i] = '·'
            vistos += 1
            if vistos == 4:
                break
    return ''.join(chars)


def _twilio_mes() -> str:
    try:
        from core.twilio_balance import twilio_balance_badge

        texto, _tono = twilio_balance_badge()
    except Exception:
        return 'Sin dato'
    match = re.search(r'(\$[0-9]+(?:[.,][0-9]+)?)\s+este mes', texto or '')
    if not match:
        return 'Sin dato'
    return match.group(1)


def _saludo(user, hour: int) -> str:
    from core.templatetags.eki_admin import saludo_por_hora

    nombre = 'equipo'
    if user is not None and getattr(user, 'is_authenticated', False):
        nombre = (
            (getattr(user, 'first_name', '') or '').strip()
            or (user.get_username() or '').strip()
            or 'equipo'
        )
    return saludo_por_hora(nombre, hour)


def _puede(user, perm: str) -> bool:
    if getattr(user, 'is_superuser', False):
        return True
    try:
        return bool(user.has_perm(perm))
    except Exception:
        return False


def _cache_key(user) -> str:
    pk = getattr(user, 'pk', None)
    if not pk:
        return ''
    return f'eki-admin-home-v1-{pk}'


def _vacio(saludo: str, fecha: str, ahora) -> dict:
    serie = _serie_vacia(ahora)
    return {
        'saludo': saludo,
        'fecha_linea': fecha,
        'actualizado': ahora.strftime('%H:%M'),
        'twilio_mes': 'Sin dato',
        'cifras': [
            {'clave': 'activas', 'label': 'Personas activas', 'valor': '0'},
            {'clave': 'avance', 'label': 'Avance promedio', 'valor': '0%'},
            {'clave': 'completaron', 'label': 'Completaron este mes', 'valor': '0'},
            {
                'clave': 'fallos',
                'label': 'Fallos en 24 h',
                'valor': '0',
                'tooltip': _TOOLTIP_FALLOS,
            },
        ],
        'acciones': [],
        'lineas': [],
        'chart_data': serie['chart_data'],
        'chart_options': serie['chart_options'],
        'mensajes_nota': '',
        'errores': [],
        'errores_tabla': {'headers': ['Hora', 'Qué pasó', 'Teléfono', 'Línea'], 'rows': []},
        'errores_url': '/admin/core/metawebhookevento/?resultado__exact=error',
        'badges': {'plantillas': 0, 'modulos': 0},
    }
