"""
Vista para logs del sistema con fechas de ejecución
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .models import WhatsappLog, EnvioLog, Campana, EnvioProgramado
import json

@staff_member_required
def logs_dashboard(request):
    """
    Dashboard principal de logs con fechas de ejecución
    """
    # Filtros de fecha
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo_log = request.GET.get('tipo', 'todos')
    
    # Fechas por defecto (últimos 7 días)
    if not fecha_desde:
        fecha_desde = (timezone.now() - timedelta(days=7)).date()
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    
    if not fecha_hasta:
        fecha_hasta = timezone.now().date()
    else:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Convertir a datetime para filtros
    fecha_desde_dt = datetime.combine(fecha_desde, datetime.min.time())
    fecha_hasta_dt = datetime.combine(fecha_hasta, datetime.max.time())
    
    # Logs de WhatsApp
    whatsapp_logs = WhatsappLog.objects.filter(
        fecha__range=[fecha_desde_dt, fecha_hasta_dt]
    ).select_related('estudiante').order_by('-fecha')
    
    # Logs de campañas/envíos
    envio_logs = EnvioLog.objects.filter(
        fecha_envio__range=[fecha_desde_dt, fecha_hasta_dt]
    ).select_related('estudiante', 'campana').order_by('-fecha_envio')
    
    # Campañas programadas (pendientes y futuras)
    campanas_programadas = Campana.objects.filter(
        fecha_programada__isnull=False,
        ejecutada=False
    ).order_by('fecha_programada')
    
    # Envíos programados
    envios_programados = EnvioProgramado.objects.filter(
        estado__in=['pendiente', 'programado']
    ).order_by('fecha_programada')
    
    # Estadísticas del período
    stats = {
        'total_whatsapp': whatsapp_logs.count(),
        'whatsapp_enviados': whatsapp_logs.filter(tipo='SENT').count(),
        'whatsapp_recibidos': whatsapp_logs.filter(tipo='INCOMING').count(),
        'total_campanas': envio_logs.count(),
        'campanas_exitosas': envio_logs.filter(estado='ENVIADO').count(),
        'campanas_fallidas': envio_logs.filter(estado='FALLIDO').count(),
        'programadas_pendientes': campanas_programadas.count(),
        'envios_pendientes': envios_programados.count(),
    }
    
    # Filtrar por tipo si se especifica
    if tipo_log == 'whatsapp':
        envio_logs = EnvioLog.objects.none()
    elif tipo_log == 'campanas':
        whatsapp_logs = WhatsappLog.objects.none()
    
    # Actividad por día (últimos 7 días)
    actividad_diaria = []
    for i in range(7):
        fecha = timezone.now().date() - timedelta(days=6-i)
        whatsapp_dia = WhatsappLog.objects.filter(
            fecha__date=fecha
        ).count()
        envios_dia = EnvioLog.objects.filter(
            fecha_envio__date=fecha
        ).count()
        
        actividad_diaria.append({
            'fecha': fecha.strftime('%d/%m'),
            'whatsapp': whatsapp_dia,
            'envios': envios_dia,
            'total': whatsapp_dia + envios_dia
        })
    
    context = {
        'whatsapp_logs': whatsapp_logs[:100],  # Limitar para performance
        'envio_logs': envio_logs[:100],
        'campanas_programadas': campanas_programadas,
        'envios_programados': envios_programados,
        'stats': stats,
        'actividad_diaria': actividad_diaria,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipo_log': tipo_log,
        'total_registros': whatsapp_logs.count() + envio_logs.count(),
    }
    
    return render(request, 'admin/logs_dashboard.html', context)


@staff_member_required
def actividad_timeline(request):
    """
    API para timeline de actividad (AJAX)
    """
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        return JsonResponse({'error': 'Fechas requeridas'})
    
    try:
        fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
        fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido'})
    
    # Actividad por hora
    timeline = []
    current_time = fecha_desde_dt
    
    while current_time <= fecha_hasta_dt:
        next_time = current_time + timedelta(hours=1)
        
        whatsapp_count = WhatsappLog.objects.filter(
            fecha__range=[current_time, next_time]
        ).count()
        
        envios_count = EnvioLog.objects.filter(
            fecha_envio__range=[current_time, next_time]
        ).count()
        
        if whatsapp_count > 0 or envios_count > 0:
            timeline.append({
                'hora': current_time.strftime('%H:%M'),
                'fecha': current_time.strftime('%d/%m/%Y'),
                'timestamp': current_time.isoformat(),
                'whatsapp': whatsapp_count,
                'envios': envios_count,
                'total': whatsapp_count + envios_count
            })
        
        current_time = next_time
    
    return JsonResponse({
        'timeline': timeline,
        'total_eventos': len(timeline)
    })


@staff_member_required
def calendario_programados(request):
    """
    Vista de calendario con fechas programadas
    """
    # Próximas 30 días
    hoy = timezone.now()
    fecha_limite = hoy + timedelta(days=30)
    
    # Campañas programadas
    campanas = Campana.objects.filter(
        fecha_programada__isnull=False,
        fecha_programada__range=[hoy, fecha_limite],
        ejecutada=False
    ).order_by('fecha_programada')
    
    # Envíos programados
    envios = EnvioProgramado.objects.filter(
        estado__in=['pendiente'],
        fecha_programada__range=[hoy, fecha_limite]
    ).order_by('fecha_programada')
    
    # Agrupar por día
    eventos_por_dia = {}
    
    for campana in campanas:
        fecha_key = campana.fecha_programada.strftime('%Y-%m-%d')
        if fecha_key not in eventos_por_dia:
            eventos_por_dia[fecha_key] = {
                'fecha': campana.fecha_programada.date(),
                'campanas': [],
                'envios': []
            }
        eventos_por_dia[fecha_key]['campanas'].append(campana)
    
    for envio in envios:
        fecha_key = envio.fecha_programada.strftime('%Y-%m-%d')
        if fecha_key not in eventos_por_dia:
            eventos_por_dia[fecha_key] = {
                'fecha': envio.fecha_programada.date(),
                'campanas': [],
                'envios': []
            }
        eventos_por_dia[fecha_key]['envios'].append(envio)
    
    # Ordenar por fecha
    eventos_ordenados = sorted(
        eventos_por_dia.values(), 
        key=lambda x: x['fecha']
    )
    
    # Calcular estadísticas
    total_campanas_programadas = campanas.count()
    total_envios_programados = envios.count()
    campanas_hoy = campanas.filter(
        fecha_programada__date=hoy.date()
    ).count()
    
    context = {
        'eventos_por_dia': eventos_ordenados,
        'total_campanas_programadas': total_campanas_programadas,
        'total_envios_programados': total_envios_programados,
        'campanas_hoy': campanas_hoy,
        'fecha_actual': hoy,
    }
    
    return render(request, 'admin/calendario_programados.html', context)


@staff_member_required
def detalle_log(request, log_tipo, log_id):
    """
    Vista detallada de un log específico
    """
    if log_tipo == 'whatsapp':
        try:
            log = WhatsappLog.objects.select_related('estudiante').get(id=log_id)
            template = 'admin/detalle_whatsapp_log.html'
        except WhatsappLog.DoesNotExist:
            return JsonResponse({'error': 'Log no encontrado'})
    
    elif log_tipo == 'envio':
        try:
            log = EnvioLog.objects.select_related(
                'estudiante', 'campana'
            ).get(id=log_id)
            template = 'admin/detalle_envio_log.html'
        except EnvioLog.DoesNotExist:
            return JsonResponse({'error': 'Log no encontrado'})
    
    else:
        return JsonResponse({'error': 'Tipo de log inválido'})
    
    context = {
        'log': log,
        'log_tipo': log_tipo
    }
    
    return render(request, template, context)


@staff_member_required
def exportar_logs(request):
    """
    Exportar logs en formato CSV
    """
    import csv
    from django.http import HttpResponse
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo', 'todos')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="logs_eki_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    writer = csv.writer(response)
    
    if tipo in ['todos', 'whatsapp']:
        writer.writerow(['LOGS WHATSAPP'])
        writer.writerow(['Fecha', 'Teléfono', 'Tipo', 'Estado', 'Mensaje', 'Estudiante'])
        
        logs = WhatsappLog.objects.select_related('estudiante')
        if fecha_desde and fecha_hasta:
            fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
            fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            logs = logs.filter(fecha__range=[fecha_desde_dt, fecha_hasta_dt])
        
        for log in logs.order_by('-fecha')[:1000]:  # Máximo 1000 registros
            estudiante = log.estudiante.nombre if log.estudiante else 'N/A'
            writer.writerow([
                log.fecha.strftime('%d/%m/%Y %H:%M'),
                log.telefono,
                log.get_tipo_display(),
                log.estado,
                log.mensaje[:100] if log.mensaje else '',
                estudiante
            ])
        
        writer.writerow([])  # Línea vacía
    
    if tipo in ['todos', 'campanas']:
        writer.writerow(['LOGS CAMPAÑAS'])
        writer.writerow(['Fecha', 'Estudiante', 'Campaña', 'Estado', 'Respuesta API'])
        
        logs = EnvioLog.objects.select_related('estudiante', 'campana')
        if fecha_desde and fecha_hasta:
            fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
            fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            logs = logs.filter(fecha_envio__range=[fecha_desde_dt, fecha_hasta_dt])
        
        for log in logs.order_by('-fecha_envio')[:1000]:
            writer.writerow([
                log.fecha_envio.strftime('%d/%m/%Y %H:%M'),
                log.estudiante.nombre,
                log.campana.nombre,
                log.estado,
                log.respuesta_api[:100] if log.respuesta_api else ''
            ])
    
    return response