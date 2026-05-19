"""
Views del Dashboard de Analíticas
Panel de métricas educativas con filtros geográficos y temporales
"""

import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
import csv


# Imports seguros de modelos
try:
    from .models import (
        Estudiante, Curso, Modulo,
        ProgresoEstudiante, ModuloCompletado,
        WhatsappLog, Cliente,
        InteraccionLog, RespuestaEjercicio
    )
except ImportError:
    Estudiante = Curso = Modulo = ProgresoEstudiante = ModuloCompletado = WhatsappLog = Cliente = None
    InteraccionLog = RespuestaEjercicio = None

try:
    from formulario.models import FichaGEI, SesionFormulario
except ImportError:
    FichaGEI = None
    SesionFormulario = None

import logging
logger = logging.getLogger(__name__)



@staff_member_required
def dashboard_analytics(request):
    """Vista principal del dashboard de analíticas - versión robusta"""
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        cliente_id = request.GET.get('cliente')
        curso_id = request.GET.get('curso')

        estudiantes = Estudiante.objects.filter(activo=True) if Estudiante else []
        progresos = ProgresoEstudiante.objects.all() if ProgresoEstudiante else []

        # Validación robusta de fechas
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                progresos = progresos.filter(fecha_inicio__gte=fecha_inicio_dt)
            except (ValueError, TypeError):
                fecha_inicio = None
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
                progresos = progresos.filter(fecha_inicio__lte=fecha_fin_dt)
            except (ValueError, TypeError):
                fecha_fin = None
        if curso_id:
            progresos = progresos.filter(curso_id=curso_id)
        if cliente_id:
            progresos = progresos.filter(curso__cliente_id=cliente_id)

        total_estudiantes = estudiantes.count() if hasattr(estudiantes, 'count') else 0
        total_estudiantes_activos = estudiantes.filter(
            id__in=progresos.filter(completado=False).values_list('estudiante_id', flat=True)
        ).count() if hasattr(estudiantes, 'filter') else 0

        total_cursos = Curso.objects.filter(activo=True).count() if Curso else 0
        total_modulos = Modulo.objects.count() if Modulo else 0

        cursos_completados = progresos.filter(completado=True).count() if hasattr(progresos, 'filter') else 0
        cursos_en_progreso = progresos.filter(completado=False).count() if hasattr(progresos, 'filter') else 0

        tasa_finalizacion = 0
        try:
            if hasattr(progresos, 'exists') and progresos.exists():
                tasa_finalizacion = (cursos_completados / progresos.count() * 100)
        except Exception as e:
            logger.warning(f"Error calculando tasa_finalizacion: {e}")

        cursos_populares = progresos.values(
            'curso__nombre', 'curso__emoji'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:5] if hasattr(progresos, 'values') else []

        actividad_cliente = progresos.values(
            'curso__cliente__nombre'
        ).annotate(
            total=Count('id')
        ).order_by('-total') if hasattr(progresos, 'values') else []

        # --- MÉTRICAS DE ERROR/ENVÍO DE MEDIA ---
        total_envios_media = WhatsappLog.objects.filter(tipo='SENT').count() if WhatsappLog else 0
        total_fallos_media = WhatsappLog.objects.filter(tipo='SENT', estado='ERROR').count() if WhatsappLog else 0
        total_exitos_media = WhatsappLog.objects.filter(tipo='SENT', estado='SENT').count() if WhatsappLog else 0
        tasa_fallo_media = round((total_fallos_media / total_envios_media * 100), 1) if total_envios_media > 0 else 0
        ultimos_errores_media = WhatsappLog.objects.filter(tipo='SENT', estado='ERROR').order_by('-fecha')[:5] if WhatsappLog else []
        top_usuarios_fallos = (
            WhatsappLog.objects.filter(tipo='SENT', estado='ERROR')
            .values('telefono')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        ) if WhatsappLog else []

        # --- MÉTRICAS EDUCATIVAS ---
        clientes = Cliente.objects.filter(activo=True).order_by('nombre') if Cliente else []
        cursos = Curso.objects.filter(activo=True).order_by('nombre') if Curso else []

        # Cálculo de estudiantes por curso
        estudiantes_por_curso = []
        if Curso and ProgresoEstudiante:
            for curso in cursos:
                total = ProgresoEstudiante.objects.filter(curso_id=curso.id).count()
                completados = ProgresoEstudiante.objects.filter(curso_id=curso.id, completado=True).count()
                porcentaje = round((completados / total * 100) if total > 0 else 0, 1)
                estudiantes_por_curso.append({
                    'nombre': curso.nombre,
                    'total': total,
                    'completados': completados,
                    'porcentaje': porcentaje
                })

        context = {
            'total_estudiantes': total_estudiantes,
            'total_estudiantes_activos': total_estudiantes_activos,
            'total_cursos': total_cursos,
            'total_modulos': total_modulos,
            'cursos_completados': cursos_completados,
            'cursos_en_progreso': cursos_en_progreso,
            'tasa_finalizacion': round(tasa_finalizacion, 1),
            'cursos_populares': list(cursos_populares),
            'actividad_cliente': list(actividad_cliente),
            # Solo métricas educativas, no logs individuales
            'tasa_fallo_media': tasa_fallo_media,
            'total_envios_media': total_envios_media,
            'total_fallos_media': total_fallos_media,
            'total_exitos_media': total_exitos_media,
            'ultimos_errores_media': ultimos_errores_media,
            'top_usuarios_fallos': list(top_usuarios_fallos),
            'clientes': clientes,
            'cursos': cursos,
            'filtro_fecha_inicio': fecha_inicio,
            'filtro_fecha_fin': fecha_fin,
            'filtro_cliente': cliente_id,
            'filtro_curso': curso_id,
            'estudiantes_por_curso': estudiantes_por_curso,
        }
        # Usar template existente y fallback si no existe
        try:
            return render(request, 'admin/dashboard_metricas.html', context)
        except Exception as e:
            # logger.error(f"Error renderizando dashboard_metricas.html: {e}")
            return render(request, 'admin/dashboard_reportes_avanzados.html', context)
    except Exception as e:
        # logger.error(f"Error en dashboard_analytics: {e}", exc_info=True)
        return render(request, 'admin/error_page.html', {
            'error_message': 'Ocurrió un error al cargar el dashboard de analíticas.',
            'error_detail': str(e) if hasattr(request, 'user') and getattr(request.user, 'is_superuser', False) else None
        }, status=500)


@staff_member_required
def exportar_metricas_csv(request):
    """Exporta métricas a CSV"""
    
    # Aplicar mismos filtros que dashboard
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    municipio = request.GET.get('municipio')
    curso_id = request.GET.get('curso')
    modalidad = request.GET.get('modalidad')
    
    interacciones = InteraccionLog.objects.all()
    
    if fecha_inicio:
        interacciones = interacciones.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        interacciones = interacciones.filter(fecha__lte=fecha_fin)
    if municipio:
        interacciones = interacciones.filter(municipio=municipio)
    if curso_id:
        interacciones = interacciones.filter(curso_id=curso_id)
    if modalidad:
        interacciones = interacciones.filter(modalidad=modalidad)
    
    # Crear respuesta CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="metricas_eki_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Estudiante', 'Municipio',
        'Curso', 'Módulo', 'Tipo', 'Modalidad',
        'Puntaje', 'Correcto', 'Duración (seg)'
    ])
    
    for i in interacciones.select_related('estudiante', 'curso', 'modulo')[:1000]:  # Límite 1000
        writer.writerow([
            i.fecha.strftime('%Y-%m-%d %H:%M'),
            i.estudiante.nombre if i.estudiante else 'N/A',
            i.municipio or 'N/A',
            # Eliminado departamento
            i.curso.titulo if i.curso else 'N/A',
            i.modulo.titulo if i.modulo else 'N/A',
            i.get_tipo_display(),
            i.get_modalidad_display(),
            i.puntaje or 'N/A',
            'Sí' if i.es_correcto else 'No',
            i.duracion_segundos or 'N/A'
        ])
    
    return response


@staff_member_required
def api_metricas_json(request):
    """API JSON para gráficos dinámicos"""
    from core.domains.dashboard import API_TIPO_ALIASES

    tipo_metrica = request.GET.get('tipo', 'modalidad')
    if tipo_metrica in API_TIPO_ALIASES:
        tipo_metrica = API_TIPO_ALIASES[tipo_metrica]
    
    if tipo_metrica == 'modalidad':
        # Comparación audio vs texto
        data = InteraccionLog.objects.exclude(
            puntaje__isnull=True
        ).values('modalidad').annotate(
            total=Count('id'),
            correctas=Count('id', filter=Q(es_correcto=True)),
            puntaje_avg=Avg('puntaje')
        )
        
        return JsonResponse({
            'labels': [item['modalidad'] for item in data],
            'datasets': [
                {
                    'label': 'Total Interacciones',
                    'data': [item['total'] for item in data]
                },
                {
                    'label': 'Puntaje Promedio',
                    'data': [round(item['puntaje_avg'] or 0, 1) for item in data]
                }
            ]
        })
    
    elif tipo_metrica == 'municipios':
        # Top 10 municipios
        data = InteraccionLog.objects.values('municipio').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        return JsonResponse({
            'labels': [item['municipio'] or 'Sin municipio' for item in data],
            'data': [item['total'] for item in data]
        })
    
    elif tipo_metrica == 'temporal':
        # Últimos 30 días
        hace_30 = datetime.now() - timedelta(days=30)
        data = InteraccionLog.objects.filter(
            fecha__gte=hace_30
        ).annotate(
            dia=TruncDate('fecha')
        ).values('dia').annotate(
            total=Count('id')
        ).order_by('dia')
        
        return JsonResponse({
            'labels': [item['dia'].strftime('%d/%m') for item in data],
            'data': [item['total'] for item in data]
        })
    
    elif tipo_metrica == 'formulario_gei':
        # Métricas agregadas de Ficha GEI / sesiones (para dashboard admin; staff autenticado)
        if not (FichaGEI and SesionFormulario):
            return JsonResponse({'error': 'app formulario no disponible'}, status=400)
        from django.utils import timezone as tz_util
        try:
            from formulario.models import CAMPOS_GEI_7
        except Exception:
            CAMPOS_GEI_7 = ()
        hace_30 = tz_util.now() - timedelta(days=30)
        cliente_id = request.GET.get("cliente_id")
        f_q = FichaGEI.objects.all()
        s_q = SesionFormulario.objects.all()
        if cliente_id and str(cliente_id).isdigit():
            cid = int(cliente_id)
            f_q = f_q.filter(cliente_id=cid)
            s_q = s_q.filter(estudiante__cliente_id=cid)

        muestra = list(f_q.order_by("-fecha_update")[:300])
        n = len(muestra)
        suma_pct = 0
        fichas_completas = 0
        fichas_parciales = 0
        fichas_pendientes = 0
        nulos_por_campo = {c: 0 for c in CAMPOS_GEI_7}
        for ficha in muestra:
            pct = int(ficha.completitud_pct or 0)
            suma_pct += pct
            if pct == 100:
                fichas_completas += 1
            elif pct == 0:
                fichas_pendientes += 1
            else:
                fichas_parciales += 1
            for c in CAMPOS_GEI_7:
                v = getattr(ficha, c, None)
                if v is None or v == "":
                    nulos_por_campo[c] += 1
        prom = round(suma_pct / n, 1) if n else 0.0

        campo_menor = None
        if n and nulos_por_campo:
            cm = max(nulos_por_campo.items(), key=lambda kv: kv[1])
            if cm[1] > 0:
                campo_menor = {
                    "campo": cm[0],
                    "fichas_sin_dato": cm[1],
                    "porcentaje_sin_dato": round(cm[1] * 100 / n, 1),
                }

        completadas_30d = list(
            s_q.filter(completado=True, fecha_update__gte=hace_30)[:300]
        )
        tiempo_promedio_min = None
        if completadas_30d:
            total_seg = 0
            cnt = 0
            for s in completadas_30d:
                if s.fecha_inicio and s.fecha_update:
                    total_seg += (s.fecha_update - s.fecha_inicio).total_seconds()
                    cnt += 1
            if cnt:
                tiempo_promedio_min = round((total_seg / cnt) / 60, 1)

        return JsonResponse({
            "schema": "formulario_gei_v2",
            "fichas_total": f_q.count(),
            "fichas_ultimos_30d": f_q.filter(fecha_inicio__gte=hace_30).count(),
            "fichas_completas": fichas_completas,
            "fichas_parciales": fichas_parciales,
            "fichas_pendientes": fichas_pendientes,
            "completitud_promedio_pct": prom,
            "completitud_muestra": n,
            "campo_con_menor_completitud": campo_menor,
            "sesiones_activas": s_q.filter(completado=False).count(),
            "sesiones_completadas_30d": len(completadas_30d),
            "tiempo_promedio_completar_min": tiempo_promedio_min,
        })
    
    elif tipo_metrica == 'metricas_empresa':
        from core.metricas_empresa import calcular_metricas_empresa

        cliente_id = request.GET.get('cliente_id') or request.GET.get('cliente')
        curso_id = request.GET.get('curso_id') or request.GET.get('curso')
        desde = request.GET.get('desde') or request.GET.get('fecha_inicio')
        hasta = request.GET.get('hasta') or request.GET.get('fecha_fin')

        cid = int(cliente_id) if cliente_id and str(cliente_id).isdigit() else None
        cu_id = int(curso_id) if curso_id and str(curso_id).isdigit() else None

        payload = calcular_metricas_empresa(
            cliente_id=cid,
            curso_id=cu_id,
            desde=desde,
            hasta=hasta,
        )
        payload['schema'] = 'metricas_empresa_v1'
        return JsonResponse(payload)

    elif tipo_metrica == 'metricas_nati':
        from core.metricas_empresa import calcular_metricas_nati

        cliente_id = request.GET.get('cliente_id') or request.GET.get('cliente')
        desde = request.GET.get('desde') or request.GET.get('fecha_inicio')
        hasta = request.GET.get('hasta') or request.GET.get('fecha_fin')
        cid = int(cliente_id) if cliente_id and str(cliente_id).isdigit() else None

        payload = calcular_metricas_nati(cliente_id=cid, desde=desde, hasta=hasta)
        payload['schema'] = 'metricas_nati_v1'
        return JsonResponse(payload)

    return JsonResponse({'error': 'Tipo de métrica no válido'}, status=400)


@staff_member_required
def detalle_estudiante(request, estudiante_id):
    """Vista detallada de métricas de un estudiante"""
    
    estudiante = Estudiante.objects.get(id=estudiante_id)
    
    # Interacciones del estudiante
    interacciones = InteraccionLog.objects.filter(
        estudiante=estudiante
    ).order_by('-fecha')[:50]
    
    # Estadísticas generales
    stats = InteraccionLog.objects.filter(estudiante=estudiante).aggregate(
        total=Count('id'),
        correctas=Count('id', filter=Q(es_correcto=True)),
        puntaje_avg=Avg('puntaje'),
        tiempo_total=Count('duracion_segundos')
    )
    
    # Respuestas a ejercicios
    respuestas = RespuestaEjercicio.objects.filter(
        estudiante=estudiante
    ).select_related('ejercicio', 'ejercicio__modulo').order_by('-fecha_respuesta')[:20]
    
    # Progreso por curso
    progreso_cursos = InteraccionLog.objects.filter(
        estudiante=estudiante
    ).values(
        'curso__titulo'
    ).annotate(
        total=Count('id'),
        puntaje_avg=Avg('puntaje')
    ).order_by('-total')
    
    context = {
        'estudiante': estudiante,
        'interacciones': interacciones,
        'stats': stats,
        'respuestas': respuestas,
        'progreso_cursos': progreso_cursos,
    }
    
    try:
        return render(request, 'analytics/detalle_estudiante.html', context)
    except Exception as e:
        # logger.error(f"Error renderizando detalle_estudiante: {e}")
        return render(request, 'admin/error_page.html', {
            'error_message': 'Ocurrió un error al cargar el detalle del estudiante.',
            'error_detail': str(e) if hasattr(request, 'user') and getattr(request.user, 'is_superuser', False) else None
        }, status=500)


# ============================================================
# 🌱 Panel GEI independiente — /admin/gei/panel/
# ============================================================

GEI_CAMPOS_LEGIBLES = (
    ("nombre_finca", "🌾 Nombre de la finca"),
    ("area_ha", "📐 Área productiva (ha)"),
    ("num_plantas", "🌱 Número de plantas"),
    ("fertilizante_kg", "🧪 Fertilizante (kg)"),
    ("concentracion_n_pct", "⚗️ Concentración de N (%)"),
    ("produccion_kg", "☕ Producción anual (kg)"),
    ("energia_kwh", "💡 Energía (kWh)"),
)


def _es_dato_lleno(valor) -> bool:
    return valor is not None and valor != ""


def _ficha_estado(pct: int) -> tuple[str, str]:
    """Devuelve (etiqueta, color) según el % de completitud."""
    if pct >= 80:
        return ("Completa", "#2f9e44")
    if pct >= 40:
        return ("Parcial", "#f08c00")
    return ("Pendiente", "#c92a2a")


@staff_member_required
def gei_panel_view(request):
    """Panel dedicado de métricas de recolección GEI.

    Soporta filtro `?cliente_id=X` y paginación `?page=N`.
    Requiere staff. Si FichaGEI no está disponible (app no instalada o migraciones
    pendientes), renderiza un placeholder.
    """
    if FichaGEI is None:
        return render(request, 'admin/gei_panel.html', {
            'gei_disponible': False,
            'titulo': 'Panel GEI',
        })

    cliente_id_param = request.GET.get('cliente_id') or request.GET.get('cliente') or ''
    cliente_id = None
    if cliente_id_param:
        try:
            cliente_id = int(cliente_id_param)
        except (TypeError, ValueError):
            cliente_id = None

    fichas_qs = FichaGEI.objects.all().select_related('estudiante', 'cliente', 'curso')
    if cliente_id:
        fichas_qs = fichas_qs.filter(cliente_id=cliente_id)

    fichas_list = list(fichas_qs.order_by('-fecha_update')[:1000])
    total_fichas = fichas_qs.count()

    # SECCIÓN 1 — Resumen ejecutivo
    fichas_completas = 0
    fichas_parciales = 0
    fichas_pendientes = 0
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

    # Tiempo promedio para completar (sesiones cerradas últimos 30 días)
    tiempo_promedio_min = None
    if SesionFormulario is not None:
        from django.utils import timezone
        hace_30 = timezone.now() - timedelta(days=30)
        ses_qs = SesionFormulario.objects.filter(
            completado=True,
            fecha_update__gte=hace_30,
        )
        if cliente_id:
            ses_qs = ses_qs.filter(estudiante__cliente_id=cliente_id)
        total_seg = 0
        cnt = 0
        for s in ses_qs:
            try:
                delta = (s.fecha_update - s.fecha_inicio).total_seconds()
                if delta > 0:
                    total_seg += delta
                    cnt += 1
            except Exception:
                continue
        if cnt:
            tiempo_promedio_min = round((total_seg / cnt) / 60, 1)

    # SECCIÓN 2 — Completitud por variable
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
                'sin_dato': len(fichas_list) - con_dato,
            })
        completitud_variables.sort(key=lambda x: x['pct'])

    # SECCIÓN 4 — Distribución de completitud
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
        {
            'rango': k,
            'count': v,
            'pct_bar': round((v / max_dist) * 100, 1) if max_dist else 0,
        }
        for k, v in distribucion.items()
    ]

    # SECCIÓN 3 — Tabla de productores (paginada, 20 por página)
    page_size = 20
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    inicio = (page - 1) * page_size
    fin = inicio + page_size

    productores = []
    for f in fichas_list[inicio:fin]:
        pct = f.completitud_pct
        estado_label, estado_color = _ficha_estado(pct)
        productores.append({
            'ficha_id': f.id,
            'estudiante': f.estudiante,
            'estudiante_nombre': getattr(f.estudiante, 'nombre', '—'),
            'estudiante_telefono': getattr(f.estudiante, 'telefono', '—'),
            'cliente_nombre': f.cliente.nombre if f.cliente_id else '—',
            'nombre_finca': f.nombre_finca or '—',
            'fertilizante': f.fertilizante_kg if f.fertilizante_kg is not None else '—',
            'n_pct': f.concentracion_n_pct if f.concentracion_n_pct is not None else '—',
            'combustible': f.combustible_gal if f.combustible_gal is not None else '—',
            'energia': f.energia_kwh if f.energia_kwh is not None else '—',
            'residuos': f.residuos_ton if f.residuos_ton is not None else '—',
            'produccion': f.produccion_kg if f.produccion_kg is not None else '—',
            'bosque': f.area_bosque_ha if f.area_bosque_ha is not None else '—',
            'completitud_pct': pct,
            'estado_label': estado_label,
            'estado_color': estado_color,
        })

    total_paginas = max(1, (len(fichas_list) + page_size - 1) // page_size)

    # Lista de clientes para el filtro
    clientes_disponibles = []
    if Cliente is not None:
        clientes_disponibles = list(
            Cliente.objects.filter(activo=True).order_by('nombre').values('id', 'nombre')
        )

    context = {
        'gei_disponible': True,
        'titulo': '🌱 Panel GEI — Recolección de datos',
        'cliente_id_actual': cliente_id,
        'clientes_disponibles': clientes_disponibles,
        # Resumen
        'fichas_total': total_fichas,
        'fichas_completas': fichas_completas,
        'fichas_parciales': fichas_parciales,
        'fichas_pendientes': fichas_pendientes,
        'completitud_promedio': completitud_promedio,
        'tiempo_promedio_min': tiempo_promedio_min,
        'pct_completas': round((fichas_completas / total_fichas) * 100, 1) if total_fichas else 0,
        # Variables
        'completitud_variables': completitud_variables,
        # Distribución
        'distribucion_view': distribucion_view,
        # Productores
        'productores': productores,
        'page': page,
        'total_paginas': total_paginas,
        'page_anterior': page - 1 if page > 1 else None,
        'page_siguiente': page + 1 if page < total_paginas else None,
        # Export URL
        'export_url': '/api/integracion/gei/exportar/',
    }
    return render(request, 'admin/gei_panel.html', context)
