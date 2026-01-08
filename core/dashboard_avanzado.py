"""
Vista de Dashboard con Métricas Visuales
Muestra estadísticas clave del sistema en tiempo real
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Avg
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
from collections import Counter
import json

from .models import (
    Estudiante, WhatsappLog, Plantilla, Campana,
    ProgresoEstudiante, Curso, ModuloCompletado
)


@staff_member_required
def dashboard_metricas(request):
    """Dashboard principal con métricas visuales"""
    
    # Periodo de análisis
    hace_30_dias = datetime.now() - timedelta(days=30)
    hace_7_dias = datetime.now() - timedelta(days=7)
    
    # ========== MÉTRICAS GENERALES ==========
    total_estudiantes = Estudiante.objects.count()
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()
    total_plantillas = Plantilla.objects.count()
    plantillas_activas = Plantilla.objects.filter(activa=True).count()
    
    # ========== MENSAJERÍA ==========
    total_mensajes = WhatsappLog.objects.count()
    mensajes_enviados = WhatsappLog.objects.filter(tipo='SENT').count()
    mensajes_recibidos = WhatsappLog.objects.filter(tipo='INCOMING').count()
    mensajes_ultima_semana = WhatsappLog.objects.filter(
        fecha__gte=hace_7_dias
    ).count()
    
    # ========== PROGRESO EDUCATIVO ==========
    total_cursos = Curso.objects.count()
    estudiantes_inscritos = ProgresoEstudiante.objects.count()
    cursos_completados = ProgresoEstudiante.objects.filter(completado=True).count()
    modulos_completados = ModuloCompletado.objects.count()
    
    # Tasa de completación
    tasa_completacion = (cursos_completados / estudiantes_inscritos * 100) if estudiantes_inscritos > 0 else 0
    
    # ========== TOP PLANTILLAS MÁS USADAS ==========
    top_plantillas = Plantilla.objects.filter(
        activa=True
    ).order_by('-veces_usada')[:5]
    
    # ========== MENSAJES POR DÍA (ÚLTIMOS 14 DÍAS) ==========
    hace_14_dias = datetime.now() - timedelta(days=14)
    mensajes_por_dia = WhatsappLog.objects.filter(
        fecha__gte=hace_14_dias
    ).annotate(
        dia=TruncDate('fecha')
    ).values('dia').annotate(
        total=Count('id'),
        enviados=Count('id', filter=Q(tipo='SENT')),
        recibidos=Count('id', filter=Q(tipo='INCOMING'))
    ).order_by('dia')
    
    # Preparar datos para gráfica
    fechas = []
    enviados_data = []
    recibidos_data = []
    
    for item in mensajes_por_dia:
        fechas.append(item['dia'].strftime('%d/%m'))
        enviados_data.append(item['enviados'])
        recibidos_data.append(item['recibidos'])
    
    # ========== DISTRIBUCIÓN DE PLANTILLAS POR CATEGORÍA ==========
    plantillas_por_categoria = Plantilla.objects.values('categoria').annotate(
        total=Count('id')
    ).order_by('-total')
    
    categorias = []
    cantidades_categorias = []
    
    for item in plantillas_por_categoria:
        cat_display = dict(Plantilla.CATEGORIA_CHOICES).get(item['categoria'], item['categoria'])
        categorias.append(cat_display)
        cantidades_categorias.append(item['total'])
    
    # ========== PROGRESO POR CURSO ==========
    progreso_por_curso = []
    for curso in Curso.objects.all():
        inscritos = ProgresoEstudiante.objects.filter(curso=curso).count()
        completados = ProgresoEstudiante.objects.filter(
            curso=curso, 
            completado=True
        ).count()
        
        if inscritos > 0:
            porcentaje = (completados / inscritos) * 100
            progreso_por_curso.append({
                'nombre': curso.nombre,
                'emoji': curso.emoji,
                'inscritos': inscritos,
                'completados': completados,
                'porcentaje': round(porcentaje, 1)
            })
    
    # ========== ESTUDIANTES ACTIVOS VS INACTIVOS ==========
    activos_count = Estudiante.objects.filter(activo=True).count()
    inactivos_count = Estudiante.objects.filter(activo=False).count()
    
    # ========== ACTIVIDAD RECIENTE ==========
    actividad_reciente = WhatsappLog.objects.order_by('-fecha')[:10]
    
    # ========== ESTUDIANTES QUE NECESITAN SEGUIMIENTO ==========
    # Estudiantes sin mensajes en últimos 3 días
    hace_3_dias = datetime.now() - timedelta(days=3)
    estudiantes_inactivos = []
    
    for estudiante in Estudiante.objects.filter(activo=True):
        ultimo_mensaje = WhatsappLog.objects.filter(
            telefono=estudiante.telefono
        ).order_by('-fecha').first()
        
        if not ultimo_mensaje or ultimo_mensaje.fecha < hace_3_dias:
            dias_inactivo = (datetime.now() - ultimo_mensaje.fecha).days if ultimo_mensaje else 999
            estudiantes_inactivos.append({
                'estudiante': estudiante,
                'dias_inactivo': dias_inactivo
            })
    
    # Ordenar por días de inactividad
    estudiantes_inactivos = sorted(
        estudiantes_inactivos, 
        key=lambda x: x['dias_inactivo'], 
        reverse=True
    )[:10]
    
    # ========== CONTEXTO PARA TEMPLATE ==========
    context = {
        # Métricas generales
        'total_estudiantes': total_estudiantes,
        'estudiantes_activos': estudiantes_activos,
        'total_plantillas': total_plantillas,
        'plantillas_activas': plantillas_activas,
        'total_mensajes': total_mensajes,
        'mensajes_enviados': mensajes_enviados,
        'mensajes_recibidos': mensajes_recibidos,
        'mensajes_ultima_semana': mensajes_ultima_semana,
        'total_cursos': total_cursos,
        'estudiantes_inscritos': estudiantes_inscritos,
        'cursos_completados': cursos_completados,
        'modulos_completados': modulos_completados,
        'tasa_completacion': round(tasa_completacion, 1),
        
        # Porcentajes
        'porcentaje_activos': round((estudiantes_activos / total_estudiantes * 100) if total_estudiantes > 0 else 0, 1),
        'porcentaje_plantillas_activas': round((plantillas_activas / total_plantillas * 100) if total_plantillas > 0 else 0, 1),
        
        # Datos para gráficas
        'fechas_json': json.dumps(fechas),
        'enviados_data_json': json.dumps(enviados_data),
        'recibidos_data_json': json.dumps(recibidos_data),
        'categorias_json': json.dumps(categorias),
        'cantidades_categorias_json': json.dumps(cantidades_categorias),
        
        # Listas
        'top_plantillas': top_plantillas,
        'progreso_por_curso': progreso_por_curso,
        'actividad_reciente': actividad_reciente,
        'estudiantes_inactivos': estudiantes_inactivos,
        'activos_count': activos_count,
        'inactivos_count': inactivos_count,
    }
    
    return render(request, 'admin/dashboard_avanzado.html', context)
