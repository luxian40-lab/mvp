from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
import json

from core.models import Campana, EnvioLog, Estudiante, WhatsappLog


@staff_member_required
def dashboard_api_view(request):
    """API para actualizar datos del dashboard en tiempo real"""
    
    # Métricas básicas
    total_campanas = Campana.objects.count()
    total_envios = EnvioLog.objects.count()
    exitosos = EnvioLog.objects.filter(estado='ENVIADO').count()
    fallidos = EnvioLog.objects.filter(estado='FALLIDO').count()
    pendientes = EnvioLog.objects.filter(estado='PENDIENTE').count()
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()
    
    # WhatsApp stats
    whatsapp_total = WhatsappLog.objects.count()
    whatsapp_enviados = WhatsappLog.objects.filter(estado='SENT').count()
    whatsapp_entrantes = WhatsappLog.objects.filter(estado='INCOMING').count()
    
    # Últimos 10 logs de WhatsApp
    whatsapp_logs = WhatsappLog.objects.all().order_by('-fecha')[:10]
    whatsapp_logs_data = [{
        'telefono': log.telefono,
        'mensaje': log.mensaje[:50] + '...' if len(log.mensaje) > 50 else log.mensaje,
        'estado': log.estado,
        'fecha': log.fecha.strftime('%d/%m/%Y %H:%M')
    } for log in whatsapp_logs]
    
    # Datos para gráficos - Últimos 7 días
    hoy = datetime.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    
    mensajes_por_dia = WhatsappLog.objects.filter(
        fecha__gte=hace_7_dias
    ).annotate(
        dia=TruncDate('fecha')
    ).values('dia').annotate(
        total=Count('id')
    ).order_by('dia')
    
    # Preparar datos para Chart.js
    dias_labels = []
    dias_valores = []
    for i in range(7):
        dia = hoy - timedelta(days=6-i)
        dias_labels.append(dia.strftime('%d/%m'))
        count = next((m['total'] for m in mensajes_por_dia if m['dia'] == dia), 0)
        dias_valores.append(count)
    
    # Envíos por estado (últimos 30 días)
    hace_30_dias = hoy - timedelta(days=30)
    envios_exitosos_30d = EnvioLog.objects.filter(
        fecha_envio__gte=hace_30_dias,
        estado='ENVIADO'
    ).count()
    envios_fallidos_30d = EnvioLog.objects.filter(
        fecha_envio__gte=hace_30_dias,
        estado='FALLIDO'
    ).count()
    
    data = {
        'metricas': {
            'total_campanas': total_campanas,
            'total_envios': total_envios,
            'exitosos': exitosos,
            'fallidos': fallidos,
            'pendientes': pendientes,
            'estudiantes_activos': estudiantes_activos,
            'whatsapp_total': whatsapp_total,
            'whatsapp_enviados': whatsapp_enviados,
            'whatsapp_entrantes': whatsapp_entrantes,
        },
        'graficos': {
            'dias_labels': dias_labels,
            'dias_valores': dias_valores,
            'exitosos_30d': envios_exitosos_30d,
            'fallidos_30d': envios_fallidos_30d,
        },
        'whatsapp_logs': whatsapp_logs_data,
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    }
    
    return JsonResponse(data)
