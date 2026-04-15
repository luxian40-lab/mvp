"""
API REST para datos de progreso y tareas del estudiante.
Endpoints:
- GET /api/estudiante/{telefono}/ → datos del estudiante
- GET /api/estudiante/{telefono}/progreso/ → progreso detallado
- GET /api/estudiante/{telefono}/siguiente-tarea/ → siguiente tarea
"""
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
import json
import math
import hmac
from .models import (
    Estudiante,
    Campana,
    EnvioLog,
    AliadoEmpleabilidad,
    MisionEmpleabilidad,
    Curso,
    ProgresoEstudiante,
    ModuloCompletado,
    WhatsappLog,
)


def _haversine_metros(lat1, lon1, lat2, lon2):
    radio_tierra = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radio_tierra * c


def _score_oportunidad(distancia_metros, aliado):
    """Prioriza oportunidades con distancia, prioridad del aliado y cupos."""
    distancia = float(distancia_metros if distancia_metros is not None else 999999)
    prioridad = int(getattr(aliado, 'prioridad', 3) or 3)
    cupos = int(getattr(aliado, 'cupos_disponibles', 0) or 0)

    score_dist = max(0.0, 1000.0 - distancia)
    score_prioridad = prioridad * 120.0
    score_cupos = min(cupos, 50) * 5.0
    return round(score_dist + score_prioridad + score_cupos, 2)


@csrf_exempt
@require_http_methods(["GET"])
def api_estudiante(request, telefono):
    """
    GET /api/estudiante/{telefono}/
    Devuelve información del estudiante.
    """
    try:
        estudiante = Estudiante.objects.get(telefono=telefono)
        return JsonResponse({
            'success': True,
            'estudiante': {
                'id': estudiante.id,
                'nombre': estudiante.nombre,
                'telefono': estudiante.telefono,
                'activo': estudiante.activo,
            }
        })
    except Estudiante.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Estudiante con teléfono {telefono} no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_estudiante_progreso(request, telefono):
    """
    GET /api/estudiante/{telefono}/progreso/
    Devuelve progreso del estudiante en cursos/módulos.
    """
    try:
        estudiante = Estudiante.objects.get(telefono=telefono)
        
        # Contar envíos y determinar progreso
        total_envios = EnvioLog.objects.filter(estudiante=estudiante).count()
        exitosos = EnvioLog.objects.filter(estudiante=estudiante, estado='ENVIADO').count()
        fallidos = EnvioLog.objects.filter(estudiante=estudiante, estado='FALLIDO').count()
        
        # Calcular porcentaje de progreso
        progreso_porcentaje = int((exitosos / total_envios * 100) if total_envios > 0 else 0)
        
        # Módulo actual (simplificado: basado en campañas)
        ultimo_envio = EnvioLog.objects.filter(estudiante=estudiante).order_by('-fecha_envio').first()
        modulo_actual = ultimo_envio.campana.plantilla.nombre_interno if ultimo_envio else 'Introducción'
        
        return JsonResponse({
            'success': True,
            'estudiante': {
                'nombre': estudiante.nombre,
                'telefono': telefono
            },
            'progreso': {
                'porcentaje': progreso_porcentaje,
                'total_tareas': total_envios,
                'tareas_completadas': exitosos,
                'tareas_fallidas': fallidos,
                'modulo_actual': modulo_actual,
                'estado': 'En progreso' if progreso_porcentaje < 100 else 'Completado'
            }
        })
    except Estudiante.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Estudiante con teléfono {telefono} no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_estudiante_siguiente_tarea(request, telefono):
    """
    GET /api/estudiante/{telefono}/siguiente-tarea/
    Devuelve la siguiente tarea del estudiante.
    """
    try:
        estudiante = Estudiante.objects.get(telefono=telefono)
        
        # Buscar siguiente tarea (primera pendiente)
        siguiente = EnvioLog.objects.filter(
            estudiante=estudiante,
            estado='PENDIENTE'
        ).order_by('fecha_envio').first()
        
        if siguiente:
            return JsonResponse({
                'success': True,
                'estudiante': {
                    'nombre': estudiante.nombre,
                    'telefono': telefono
                },
                'siguiente_tarea': {
                    'id': siguiente.id,
                    'campana': siguiente.campana.nombre,
                    'plantilla': siguiente.campana.plantilla.nombre_interno,
                    'descripcion': siguiente.campana.plantilla.cuerpo_mensaje[:100],
                    'fecha_vence': siguiente.fecha_envio.isoformat() if siguiente.fecha_envio else None,
                    'estado': siguiente.estado
                }
            })
        else:
            # Si no hay tareas pendientes, devolver un mensaje
            return JsonResponse({
                'success': True,
                'estudiante': {
                    'nombre': estudiante.nombre,
                    'telefono': telefono
                },
                'siguiente_tarea': {
                    'id': None,
                    'campana': None,
                    'plantilla': None,
                    'descripcion': '¡Felicidades! No tienes tareas pendientes',
                    'fecha_vence': None,
                    'estado': 'COMPLETADO'
                }
            })
    except Estudiante.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Estudiante con teléfono {telefono} no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_empleabilidad_oportunidades(request):
    """GET /api/empleabilidad/oportunidades/?telefono=...&latitud=...&longitud=..."""
    telefono = (request.GET.get('telefono', '') or '').strip()
    latitud_raw = request.GET.get('latitud')
    longitud_raw = request.GET.get('longitud')

    if not telefono:
        return JsonResponse({'success': False, 'error': 'telefono es obligatorio'}, status=400)
    if latitud_raw is None or longitud_raw is None:
        return JsonResponse({'success': False, 'error': 'latitud y longitud son obligatorios'}, status=400)

    try:
        estudiante = Estudiante.objects.select_related('cliente').get(telefono=telefono)
        latitud = float(latitud_raw)
        longitud = float(longitud_raw)
    except Estudiante.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estudiante no encontrado'}, status=404)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Coordenadas inválidas'}, status=400)

    cliente = estudiante.cliente
    if cliente and not (getattr(cliente, 'habilitar_gamificacion_proximidad', False) or getattr(cliente, 'empleabilidad_exploracion_activa', False)):
        return JsonResponse({'success': True, 'activa': False, 'oportunidades': []})

    radio = int(getattr(cliente, 'empleabilidad_radio_metros', 800) if cliente else 800)
    hoy = timezone.localdate()
    aliados_qs = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
        Q(vigencia_desde__isnull=True) | Q(vigencia_desde__lte=hoy)
    ).filter(
        Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=hoy)
    )
    if cliente:
        aliados_qs = aliados_qs.filter(Q(cliente__isnull=True) | Q(cliente=cliente))

    oportunidades = []
    for aliado in aliados_qs:
        dist = _haversine_metros(latitud, longitud, aliado.latitud, aliado.longitud)
        if dist <= radio:
            score = _score_oportunidad(dist, aliado)
            oportunidades.append({
                'aliado_id': aliado.id,
                'nombre_empresa': aliado.nombre_empresa,
                'distancia_metros': round(dist, 1),
                'score_prioridad': score,
                'cupos_disponibles': int(getattr(aliado, 'cupos_disponibles', 0) or 0),
                'indicacion_sector': aliado.indicacion_sector or '',
            })

    oportunidades.sort(key=lambda x: (-x['score_prioridad'], x['distancia_metros']))
    return JsonResponse({
        'success': True,
        'activa': True,
        'radio_metros': radio,
        'oportunidades': oportunidades[:10],
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_empleabilidad_claim(request):
    """POST /api/empleabilidad/claim/ con {telefono, aliado_id, latitud, longitud}."""
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    telefono = (body.get('telefono', '') or '').strip()
    aliado_id = body.get('aliado_id')
    latitud = body.get('latitud')
    longitud = body.get('longitud')

    if not telefono or not aliado_id:
        return JsonResponse({'success': False, 'error': 'telefono y aliado_id son obligatorios'}, status=400)

    try:
        estudiante = Estudiante.objects.select_related('cliente').get(telefono=telefono)
        aliado = AliadoEmpleabilidad.objects.get(id=int(aliado_id), vacantes_activas=True)
        lat = float(latitud) if latitud is not None else None
        lon = float(longitud) if longitud is not None else None
    except Estudiante.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estudiante no encontrado'}, status=404)
    except AliadoEmpleabilidad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Aliado no encontrado o inactivo'}, status=404)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)

    distancia = None
    if lat is not None and lon is not None:
        distancia = _haversine_metros(lat, lon, aliado.latitud, aliado.longitud)
    score_prioridad = _score_oportunidad(distancia, aliado)

    mision = MisionEmpleabilidad.objects.create(
        cliente=estudiante.cliente,
        estudiante=estudiante,
        aliado=aliado,
        estado='reclamada',
        estado_flujo='interesado',
        latitud=lat,
        longitud=lon,
        distancia_metros=round(distancia, 1) if distancia is not None else None,
        puntaje_prioridad=score_prioridad,
        fecha_reclamada=timezone.now(),
        fecha_interes=timezone.now(),
        metadata={'fuente': 'api_claim'},
    )

    return JsonResponse({
        'success': True,
        'mision_id': mision.id,
        'estado': mision.estado,
        'estado_flujo': mision.estado_flujo,
        'score_prioridad': mision.puntaje_prioridad,
        'codigo_hint': 'Solicita el código secreto al aliado para completar.',
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_empleabilidad_completar(request):
    """POST /api/empleabilidad/completar/ con {telefono, mision_id, codigo}."""
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    telefono = (body.get('telefono', '') or '').strip()
    mision_id = body.get('mision_id')
    codigo = (body.get('codigo', '') or '').strip().lower()

    if not telefono or not mision_id or not codigo:
        return JsonResponse({'success': False, 'error': 'telefono, mision_id y codigo son obligatorios'}, status=400)

    try:
        estudiante = Estudiante.objects.select_related('cliente').get(telefono=telefono)
        mision = MisionEmpleabilidad.objects.select_related('aliado').get(id=int(mision_id), estudiante=estudiante)
    except Estudiante.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estudiante no encontrado'}, status=404)
    except MisionEmpleabilidad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Misión no encontrada'}, status=404)

    if codigo != str(mision.aliado.codigo_secreto).strip().lower():
        return JsonResponse({'success': False, 'error': 'Código inválido'}, status=400)

    puntos = int(getattr(estudiante.cliente, 'empleabilidad_puntos_validacion', 30) if estudiante.cliente else 30)
    if mision.estado != 'completada':
        mision.estado = 'completada'
        mision.codigo_validado = True
        mision.puntos_otorgados = puntos
        mision.estado_flujo = 'postulado'
        mision.fecha_completada = timezone.now()
        mision.fecha_postulacion = timezone.now()
        mision.save(update_fields=['estado', 'codigo_validado', 'puntos_otorgados', 'estado_flujo', 'fecha_completada', 'fecha_postulacion'])

    return JsonResponse({
        'success': True,
        'mision_id': mision.id,
        'estado': mision.estado,
        'estado_flujo': mision.estado_flujo,
        'puntos': mision.puntos_otorgados,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_empleabilidad_flujo(request):
    """POST /api/empleabilidad/flujo/ con {mision_id, estado_flujo}."""
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    mision_id = body.get('mision_id')
    estado_flujo = (body.get('estado_flujo', '') or '').strip().lower()
    estados_validos = {'descubierto', 'interesado', 'postulado', 'entrevista', 'vinculado', 'descartado'}

    if not mision_id or estado_flujo not in estados_validos:
        return JsonResponse({'success': False, 'error': 'mision_id y estado_flujo válido son obligatorios'}, status=400)

    try:
        mision = MisionEmpleabilidad.objects.get(id=int(mision_id))
    except MisionEmpleabilidad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Misión no encontrada'}, status=404)

    mision.estado_flujo = estado_flujo
    ahora = timezone.now()
    update_fields = ['estado_flujo']
    if estado_flujo == 'interesado' and not mision.fecha_interes:
        mision.fecha_interes = ahora
        update_fields.append('fecha_interes')
    elif estado_flujo == 'postulado' and not mision.fecha_postulacion:
        mision.fecha_postulacion = ahora
        update_fields.append('fecha_postulacion')
    elif estado_flujo == 'entrevista' and not mision.fecha_entrevista:
        mision.fecha_entrevista = ahora
        update_fields.append('fecha_entrevista')
    elif estado_flujo == 'vinculado' and not mision.fecha_vinculacion:
        mision.fecha_vinculacion = ahora
        update_fields.append('fecha_vinculacion')

    mision.save(update_fields=update_fields)
    return JsonResponse({'success': True, 'mision_id': mision.id, 'estado_flujo': mision.estado_flujo})


@csrf_exempt
@require_http_methods(["GET"])
def api_empleabilidad_resumen(request):
    """GET /api/empleabilidad/resumen/?cliente_id=..."""
    cliente_id = request.GET.get('cliente_id')
    qs = MisionEmpleabilidad.objects.all()
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)

    total = qs.count()
    por_estado = {k: v for k, v in qs.values_list('estado_flujo').annotate(c=Count('id'))}
    desc = por_estado.get('descubierto', 0)
    ints = por_estado.get('interesado', 0)
    post = por_estado.get('postulado', 0)
    entr = por_estado.get('entrevista', 0)
    vinc = por_estado.get('vinculado', 0)

    def tasa(a, b):
        return round((a / b * 100), 2) if b else 0

    return JsonResponse({
        'success': True,
        'total_misiones': total,
        'embudo': {
            'descubierto': desc,
            'interesado': ints,
            'postulado': post,
            'entrevista': entr,
            'vinculado': vinc,
        },
        'kpis': {
            'tasa_interes_vs_descubierto': tasa(ints, desc),
            'tasa_postulacion_vs_interes': tasa(post, ints),
            'tasa_entrevista_vs_postulado': tasa(entr, post),
            'tasa_vinculacion_vs_postulado': tasa(vinc, post),
            'tasa_vinculacion_vs_descubierto': tasa(vinc, desc),
        },
    })


def _integracion_apply_cors(request, resp):
    allowed_raw = str(getattr(settings, 'INTEGRACION_API_ALLOWED_ORIGINS', '*') or '*').strip()
    origin = (request.headers.get('Origin', '') or '').strip()

    allow_origin = '*'
    if allowed_raw != '*':
        allowed = [o.strip() for o in allowed_raw.split(',') if o.strip()]
        if origin and origin in allowed:
            allow_origin = origin
        elif allowed:
            allow_origin = allowed[0]

    resp['Access-Control-Allow-Origin'] = allow_origin
    resp['Vary'] = 'Origin'
    resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-API-Key'
    resp['Access-Control-Max-Age'] = '86400'
    return resp


def _integracion_auth_error(request):
    expected_key = str(getattr(settings, 'INTEGRACION_API_KEY', '') or '').strip()
    if not expected_key:
        return None

    auth_header = (request.headers.get('Authorization', '') or '').strip()
    provided = ''
    if auth_header.lower().startswith('bearer '):
        provided = auth_header.split(' ', 1)[1].strip()
    if not provided:
        provided = (request.headers.get('X-API-Key', '') or request.GET.get('api_key', '') or '').strip()

    if not provided or not hmac.compare_digest(provided, expected_key):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=401)
    return None


def _integracion_parse_filtros(request, permitir_curso=False):
    cliente_id_raw = (request.GET.get('cliente_id') or '').strip()
    curso_id_raw = (request.GET.get('curso_id') or '').strip()
    fecha_raw = (request.GET.get('fecha') or '').strip()
    desde_raw = (request.GET.get('desde') or '').strip()
    hasta_raw = (request.GET.get('hasta') or '').strip()

    cliente_id = None
    if cliente_id_raw:
        try:
            cliente_id = int(cliente_id_raw)
        except ValueError:
            return None, JsonResponse({'success': False, 'error': 'cliente_id debe ser numérico'}, status=400)

    curso_id = None
    if permitir_curso and curso_id_raw:
        try:
            curso_id = int(curso_id_raw)
        except ValueError:
            return None, JsonResponse({'success': False, 'error': 'curso_id debe ser numérico'}, status=400)

    def _parse_iso(value: str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except Exception:
            return None

    if desde_raw or hasta_raw:
        fecha_desde = _parse_iso(desde_raw)
        fecha_hasta = _parse_iso(hasta_raw)
        if not fecha_desde or not fecha_hasta:
            return None, JsonResponse({'success': False, 'error': 'desde y hasta deben usar formato YYYY-MM-DD'}, status=400)
    else:
        fecha_unica = _parse_iso(fecha_raw) if fecha_raw else timezone.localdate()
        if not fecha_unica:
            return None, JsonResponse({'success': False, 'error': 'fecha debe usar formato YYYY-MM-DD'}, status=400)
        fecha_desde = fecha_unica
        fecha_hasta = fecha_unica

    if fecha_hasta < fecha_desde:
        return None, JsonResponse({'success': False, 'error': 'hasta no puede ser menor que desde'}, status=400)

    max_dias = int(getattr(settings, 'INTEGRACION_API_MAX_DIAS', 31) or 31)
    rango_dias = (fecha_hasta - fecha_desde).days + 1
    if rango_dias > max_dias:
        return None, JsonResponse({
            'success': False,
            'error': f'Rango máximo permitido: {max_dias} días',
        }, status=400)

    return {
        'cliente_id': cliente_id,
        'curso_id': curso_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'rango_dias': rango_dias,
    }, None


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def api_integracion_educativa_metricas(request):
    """GET /api/integracion/educativa/metricas/?cliente_id=...&curso_id=...&fecha=YYYY-MM-DD"""
    if request.method == 'OPTIONS':
        return _integracion_apply_cors(request, HttpResponse(status=204))

    auth_error = _integracion_auth_error(request)
    if auth_error:
        return _integracion_apply_cors(request, auth_error)

    filtros, parse_error = _integracion_parse_filtros(request, permitir_curso=True)
    if parse_error:
        return _integracion_apply_cors(request, parse_error)

    cliente_id = filtros['cliente_id']
    curso_id = filtros['curso_id']
    fecha_desde = filtros['fecha_desde']
    fecha_hasta = filtros['fecha_hasta']
    rango_dias = filtros['rango_dias']

    estudiantes_base = Estudiante.objects.filter(activo=True)
    if cliente_id is not None:
        estudiantes_base = estudiantes_base.filter(cliente_id=cliente_id)
    if curso_id is not None:
        estudiantes_base = estudiantes_base.filter(progresos__curso_id=curso_id).distinct()

    progreso_base = ProgresoEstudiante.objects.filter(estudiante__in=estudiantes_base)
    if curso_id is not None:
        progreso_base = progreso_base.filter(curso_id=curso_id)

    estudiantes_registrados_q = estudiantes_base.filter(
        fecha_registro__date__gte=fecha_desde,
        fecha_registro__date__lte=fecha_hasta,
    )
    inscripciones_q = progreso_base.filter(
        fecha_inicio__date__gte=fecha_desde,
        fecha_inicio__date__lte=fecha_hasta,
    )
    cursos_completados_q = progreso_base.filter(
        completado=True,
        fecha_completado__date__gte=fecha_desde,
        fecha_completado__date__lte=fecha_hasta,
    )
    modulos_completados_q = ModuloCompletado.objects.filter(
        progreso__in=progreso_base,
        fecha_completado__date__gte=fecha_desde,
        fecha_completado__date__lte=fecha_hasta,
    )

    telefonos_scope = estudiantes_base.exclude(telefono='').values_list('telefono', flat=True)
    mensajes_q = WhatsappLog.objects.filter(
        fecha__date__gte=fecha_desde,
        fecha__date__lte=fecha_hasta,
    )
    if cliente_id is not None or curso_id is not None:
        mensajes_q = mensajes_q.filter(
            Q(estudiante__in=estudiantes_base) | Q(telefono__in=telefonos_scope)
        ).distinct()

    estudiantes_activos_total = estudiantes_base.count()
    estudiantes_registrados_total = estudiantes_registrados_q.count()
    inscripciones_total = inscripciones_q.count()
    cursos_completados_total = cursos_completados_q.count()
    modulos_completados_total = modulos_completados_q.count()
    mensajes_total = mensajes_q.count()
    mensajes_enviados_total = mensajes_q.filter(tipo='SENT').count()
    mensajes_recibidos_total = mensajes_q.filter(tipo='INCOMING').count()

    tasa_completacion = round((cursos_completados_total / inscripciones_total * 100), 2) if inscripciones_total else 0

    cursos_scope = Curso.objects.filter(progresoestudiante__in=progreso_base).distinct()
    if curso_id is not None:
        cursos_scope = cursos_scope.filter(id=curso_id)

    filtro_progreso_base = Q(progresoestudiante__id__in=progreso_base.values('id'))
    filtro_inscritos = (
        filtro_progreso_base
        & Q(progresoestudiante__fecha_inicio__date__gte=fecha_desde)
        & Q(progresoestudiante__fecha_inicio__date__lte=fecha_hasta)
    )
    filtro_completados = (
        filtro_progreso_base
        & Q(progresoestudiante__completado=True)
        & Q(progresoestudiante__fecha_completado__date__gte=fecha_desde)
        & Q(progresoestudiante__fecha_completado__date__lte=fecha_hasta)
    )

    cursos_resumen_raw = list(
        cursos_scope.annotate(
            inscritos=Count('progresoestudiante', filter=filtro_inscritos, distinct=True),
            completados=Count('progresoestudiante', filter=filtro_completados, distinct=True),
        )
        .values('id', 'nombre', 'inscritos', 'completados')
        .order_by('-inscritos', 'nombre')[:20]
    )
    cursos_resumen = []
    for item in cursos_resumen_raw:
        inscritos = int(item.get('inscritos') or 0)
        completados = int(item.get('completados') or 0)
        cursos_resumen.append({
            'curso_id': int(item.get('id')),
            'curso_nombre': item.get('nombre') or '',
            'inscritos': inscritos,
            'completados': completados,
            'tasa_completacion': round((completados / inscritos * 100), 2) if inscritos else 0,
        })

    registros_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in estudiantes_registrados_q.annotate(metric_day=TruncDate('fecha_registro'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    inscripciones_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in inscripciones_q.annotate(metric_day=TruncDate('fecha_inicio'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    completados_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in cursos_completados_q.annotate(metric_day=TruncDate('fecha_completado'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    modulos_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in modulos_completados_q.annotate(metric_day=TruncDate('fecha_completado'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    mensajes_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in mensajes_q.annotate(metric_day=TruncDate('fecha'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    enviados_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in mensajes_q.filter(tipo='SENT').annotate(metric_day=TruncDate('fecha'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }
    recibidos_por_dia = {
        str(row['metric_day']): int(row['c'])
        for row in mensajes_q.filter(tipo='INCOMING').annotate(metric_day=TruncDate('fecha'))
        .values('metric_day')
        .annotate(c=Count('id'))
    }

    metrics = []
    day_cursor = fecha_desde
    while day_cursor <= fecha_hasta:
        metric_date = day_cursor.isoformat()
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'estudiantes_registrados',
            'metric_value': int(registros_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'inscripciones_curso',
            'metric_value': int(inscripciones_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'cursos_completados',
            'metric_value': int(completados_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'modulos_completados',
            'metric_value': int(modulos_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'mensajes_whatsapp_total',
            'metric_value': int(mensajes_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'mensajes_whatsapp_sent',
            'metric_value': int(enviados_por_dia.get(metric_date, 0)),
        })
        metrics.append({
            'schema_version': 2,
            'metric_date': metric_date,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'metric_name': 'mensajes_whatsapp_incoming',
            'metric_value': int(recibidos_por_dia.get(metric_date, 0)),
        })
        day_cursor += timedelta(days=1)

    response = JsonResponse({
        'success': True,
        'meta': {
            'schema_version': 2,
            'tenant_id': cliente_id,
            'course_id': curso_id,
            'desde': fecha_desde.isoformat(),
            'hasta': fecha_hasta.isoformat(),
            'dias': rango_dias,
        },
        'resumen': {
            'estudiantes_activos_total': int(estudiantes_activos_total),
            'estudiantes_registrados_total': int(estudiantes_registrados_total),
            'inscripciones_total': int(inscripciones_total),
            'cursos_completados_total': int(cursos_completados_total),
            'modulos_completados_total': int(modulos_completados_total),
            'tasa_completacion_cursos': tasa_completacion,
            'mensajes_total': int(mensajes_total),
            'mensajes_enviados_total': int(mensajes_enviados_total),
            'mensajes_recibidos_total': int(mensajes_recibidos_total),
        },
        'cursos': cursos_resumen,
        'metrics': metrics,
    })
    return _integracion_apply_cors(request, response)


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def api_integracion_empleabilidad_metricas(request):
    """GET /api/integracion/empleabilidad/metricas/?cliente_id=...&fecha=YYYY-MM-DD"""
    if request.method == 'OPTIONS':
        return _integracion_apply_cors(request, HttpResponse(status=204))

    auth_error = _integracion_auth_error(request)
    if auth_error:
        return _integracion_apply_cors(request, auth_error)

    filtros, parse_error = _integracion_parse_filtros(request, permitir_curso=False)
    if parse_error:
        return _integracion_apply_cors(request, parse_error)

    cliente_id = filtros['cliente_id']
    fecha_desde = filtros['fecha_desde']
    fecha_hasta = filtros['fecha_hasta']
    rango_dias = filtros['rango_dias']

    qs = MisionEmpleabilidad.objects.filter(
        fecha_descubierta__date__gte=fecha_desde,
        fecha_descubierta__date__lte=fecha_hasta,
    )
    if cliente_id is not None:
        qs = qs.filter(cliente_id=cliente_id)

    agregados = list(
        qs.annotate(metric_day=TruncDate('fecha_descubierta'))
        .values('metric_day', 'estado_flujo')
        .annotate(c=Count('id'))
        .order_by('metric_day', 'estado_flujo')
    )

    metrics = []
    resumen_por_estado = {}
    resumen_por_dia = {}

    for row in agregados:
        day = row.get('metric_day')
        estado = row.get('estado_flujo') or 'sin_estado'
        count = int(row.get('c') or 0)
        day_txt = str(day or fecha_desde)

        resumen_por_estado[estado] = resumen_por_estado.get(estado, 0) + count
        resumen_por_dia[day_txt] = resumen_por_dia.get(day_txt, 0) + count

        metrics.append({
            'schema_version': 1,
            'metric_date': day_txt,
            'tenant_id': cliente_id,
            'metric_name': f'embudo_{estado}',
            'metric_value': count,
        })

    d = fecha_desde
    while d <= fecha_hasta:
        day_txt = d.isoformat()
        metrics.append({
            'schema_version': 1,
            'metric_date': day_txt,
            'tenant_id': cliente_id,
            'metric_name': 'misiones_total',
            'metric_value': int(resumen_por_dia.get(day_txt, 0)),
        })
        d += timedelta(days=1)

    response = JsonResponse({
        'success': True,
        'meta': {
            'schema_version': 1,
            'tenant_id': cliente_id,
            'desde': fecha_desde.isoformat(),
            'hasta': fecha_hasta.isoformat(),
            'dias': rango_dias,
        },
        'resumen': {
            'misiones_total': int(qs.count()),
            'por_estado': resumen_por_estado,
        },
        'metrics': metrics,
    })
    return _integracion_apply_cors(request, response)
