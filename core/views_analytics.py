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
    
    tipo_metrica = request.GET.get('tipo', 'modalidad')
    
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
