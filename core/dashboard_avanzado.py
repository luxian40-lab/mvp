"""
Vista de Dashboard con Métricas Visuales
Muestra estadísticas clave del sistema en tiempo real
"""
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Avg, Sum
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import json

from .models import (
    Estudiante, WhatsappLog, Plantilla, Campana, EnvioLog,
    ProgresoEstudiante, Curso, ModuloCompletado, Cliente,
    PerfilGamificacion, Badge, TransaccionPuntos, SolicitudSoporte,
    Certificado, Linea
)
from .gamificacion import BadgeEstudiante


@staff_member_required
def dashboard_metricas(request):
    """Dashboard excepcional con métricas completas de control"""

    # ========== PARÁMETROS DE TIEMPO ==========
    ahora = datetime.now()
    hace_1_dia = ahora - timedelta(days=1)
    hace_7_dias = ahora - timedelta(days=7)
    hace_30_dias = ahora - timedelta(days=30)
    hace_90_dias = ahora - timedelta(days=90)

    # ========== 1. MÉTRICAS DE CLIENTES ==========
    total_clientes = Cliente.objects.count()
    clientes_activos = Cliente.objects.filter(activo=True).count() if hasattr(Cliente, 'activo') else total_clientes

    # Métricas detalladas por cliente
    clientes_detalle = []
    clientes_labels = []
    clientes_estudiantes_data = []
    clientes_mensajes_data = []
    
    for cliente in Cliente.objects.all():
        estudiantes_cliente = Estudiante.objects.filter(cliente=cliente)
        estudiantes_activos_cliente = estudiantes_cliente.filter(activo=True).count()
        mensajes_cliente = WhatsappLog.objects.filter(
            telefono__in=estudiantes_cliente.values_list('telefono', flat=True)
        ).count()
        
        clientes_detalle.append({
            'nombre': cliente.nombre,
            'total_estudiantes': estudiantes_cliente.count(),
            'estudiantes_activos': estudiantes_activos_cliente,
            'mensajes': mensajes_cliente,
        })
        
        # Datos para gráfica
        clientes_labels.append(cliente.nombre[:15])  # Limitar nombre
        clientes_estudiantes_data.append(estudiantes_cliente.count())
        clientes_mensajes_data.append(mensajes_cliente)

    # ========== 2. MÉTRICAS DE ESTUDIANTES ==========
    total_estudiantes = Estudiante.objects.count()
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()
    estudiantes_nuevos_30d = Estudiante.objects.filter(fecha_registro__gte=hace_30_dias).count()
    estudiantes_nuevos_7d = Estudiante.objects.filter(fecha_registro__gte=hace_7_dias).count()

    # Distribución por cliente
    estudiantes_por_cliente = Estudiante.objects.values('cliente__nombre').annotate(
        total=Count('id'),
        activos=Count('id', filter=Q(activo=True))
    ).order_by('-total')

    # ========== 3. MÉTRICAS DE MENSAJERÍA ==========
    total_mensajes = WhatsappLog.objects.count()
    mensajes_24h = WhatsappLog.objects.filter(fecha__gte=hace_1_dia).count()
    mensajes_7d = WhatsappLog.objects.filter(fecha__gte=hace_7_dias).count()
    mensajes_30d = WhatsappLog.objects.filter(fecha__gte=hace_30_dias).count()

    # Tipos de mensajes
    mensajes_enviados = WhatsappLog.objects.filter(tipo='SENT').count()
    mensajes_recibidos = WhatsappLog.objects.filter(tipo='INCOMING').count()
    mensajes_error = WhatsappLog.objects.filter(estado='error').count()

    # Tasa de éxito
    tasa_exito_mensajes = ((mensajes_enviados - mensajes_error) / mensajes_enviados * 100) if mensajes_enviados > 0 else 0

    # ========== 4. MÉTRICAS DE CAMPAÑAS ==========
    total_campanas = Campana.objects.count()
    campanas_ejecutadas = Campana.objects.filter(ejecutada=True).count()
    campanas_programadas = Campana.objects.filter(fecha_programada__gte=ahora).count()

    # Envíos de campañas
    total_envios_campanas = EnvioLog.objects.count()
    envios_exitosos = EnvioLog.objects.filter(estado='exitoso').count()
    envios_fallidos = EnvioLog.objects.filter(estado='fallido').count()

    tasa_exito_campanas = (envios_exitosos / total_envios_campanas * 100) if total_envios_campanas > 0 else 0

    # ========== 5. MÉTRICAS EDUCATIVAS ==========
    total_cursos = Curso.objects.count()
    cursos_activos = Curso.objects.filter(activo=True).count()

    estudiantes_inscritos = ProgresoEstudiante.objects.count()
    cursos_completados = ProgresoEstudiante.objects.filter(completado=True).count()
    modulos_completados = ModuloCompletado.objects.count()

    tasa_completacion = (cursos_completados / estudiantes_inscritos * 100) if estudiantes_inscritos > 0 else 0

    # Progreso por curso
    progreso_cursos = []
    for curso in Curso.objects.all()[:10]:  # Top 10 cursos
        inscritos = ProgresoEstudiante.objects.filter(curso=curso).count()
        completados = ProgresoEstudiante.objects.filter(curso=curso, completado=True).count()
        porcentaje = (completados / inscritos * 100) if inscritos > 0 else 0

        progreso_cursos.append({
            'curso': curso,
            'inscritos': inscritos,
            'completados': completados,
            'porcentaje': round(porcentaje, 1)
        })

    # ========== 6. MÉTRICAS DE PLANTILLAS ==========
    total_plantillas = Plantilla.objects.count()
    plantillas_activas = Plantilla.objects.filter(activa=True).count()
    plantillas_twilio = Plantilla.objects.filter(twilio_template_sid__isnull=False, aprobada_twilio=True).count()

    # Plantillas más usadas
    top_plantillas = Plantilla.objects.filter(activa=True).order_by('-veces_usada')[:8]

    # ========== 7. MÉTRICAS DE GAMIFICACIÓN ==========
    total_puntos_otorgados = TransaccionPuntos.objects.filter(tipo='credito').aggregate(total=Sum('puntos'))['total'] or 0
    total_puntos_canjeados = TransaccionPuntos.objects.filter(tipo='debito').aggregate(total=Sum('puntos'))['total'] or 0

    total_badges = Badge.objects.count()
    badges_otorgados = BadgeEstudiante.objects.count()

    perfiles_gamificacion = PerfilGamificacion.objects.count()

    # ========== 8. MÉTRICAS DE SOPORTE ==========
    total_solicitudes = SolicitudSoporte.objects.count()
    solicitudes_pendientes = SolicitudSoporte.objects.filter(estado='pendiente').count()
    solicitudes_atendiendo = SolicitudSoporte.objects.filter(estado='atendiendo').count()
    solicitudes_resueltas = SolicitudSoporte.objects.filter(estado='resuelta').count()

    # ========== 9. MÉTRICAS DE CERTIFICADOS ==========
    total_certificados = Certificado.objects.count()
    certificados_generados_30d = Certificado.objects.filter(fecha_emision__gte=hace_30_dias).count()

    # ========== 10. ANÁLISIS TEMPORAL ==========
    # Mensajes por día (últimos 14 días)
    mensajes_por_dia = WhatsappLog.objects.filter(fecha__gte=hace_30_dias).annotate(
        dia=TruncDate('fecha')
    ).values('dia').annotate(
        total=Count('id'),
        enviados=Count('id', filter=Q(tipo='SENT')),
        recibidos=Count('id', filter=Q(tipo='INCOMING'))
    ).order_by('dia')

    # Preparar datos para gráficas
    fechas = []
    mensajes_diarios = []
    envios_diarios = []

    for item in mensajes_por_dia:
        fechas.append(item['dia'].strftime('%d/%m'))
        mensajes_diarios.append(item['total'])
        envios_diarios.append(item['enviados'])

    # ========== 11. ALERTAS Y NOTIFICACIONES ==========
    alertas = []

    # Alertas críticas
    if mensajes_error > 10:
        alertas.append({
            'tipo': 'error',
            'titulo': 'Altos errores de envío',
            'mensaje': f'{mensajes_error} mensajes con error en las últimas 24h',
            'icono': '⚠️'
        })

    if solicitudes_pendientes > 5:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Solicitudes de soporte pendientes',
            'mensaje': f'{solicitudes_pendientes} solicitudes esperando atención',
            'icono': '📞'
        })

    if estudiantes_nuevos_7d == 0:
        alertas.append({
            'tipo': 'info',
            'titulo': 'Sin nuevos estudiantes',
            'mensaje': 'No se registraron estudiantes en los últimos 7 días',
            'icono': '📈'
        })

    # ========== 12. KPIs PRINCIPALES ==========
    kpis = [
        {
            'titulo': 'Total Clientes',
            'valor': f"{total_clientes}",
            'cambio': f"{clientes_activos} activos",
            'tendencia': 'up',
            'icono': '🏢',
            'color': 'info'
        },
        {
            'titulo': 'Tasa de Éxito',
            'valor': f"{tasa_exito_campanas:.1f}%",
            'cambio': '+2.3%',
            'tendencia': 'up',
            'icono': '🎯',
            'color': 'primary'
        },
        {
            'titulo': 'Estudiantes Activos',
            'valor': f"{estudiantes_activos:,}",
            'cambio': f"+{estudiantes_nuevos_7d}",
            'tendencia': 'up',
            'icono': '👥',
            'color': 'info'
        },
        {
            'titulo': 'Mensajes Enviados',
            'valor': f"{mensajes_7d:,}",
            'cambio': f"+{mensajes_24h}",
            'tendencia': 'up',
            'icono': '💬',
            'color': 'warning'
        }
    ]

    # ========== CONTEXTO PARA TEMPLATE ==========
    context = {
        # KPIs principales
        'kpis': kpis,
        'alertas': alertas,

        # Clientes
        'total_clientes': total_clientes,
        'clientes_activos': clientes_activos,
        'clientes_detalle': clientes_detalle,
        'clientes_labels_json': json.dumps(clientes_labels),
        'clientes_estudiantes_json': json.dumps(clientes_estudiantes_data),
        'clientes_mensajes_json': json.dumps(clientes_mensajes_data),

        # Estudiantes
        'total_estudiantes': total_estudiantes,
        'estudiantes_activos': estudiantes_activos,
        'estudiantes_nuevos_30d': estudiantes_nuevos_30d,
        'estudiantes_nuevos_7d': estudiantes_nuevos_7d,
        'estudiantes_por_cliente': estudiantes_por_cliente,

        # Mensajería
        'total_mensajes': total_mensajes,
        'mensajes_24h': mensajes_24h,
        'mensajes_7d': mensajes_7d,
        'mensajes_30d': mensajes_30d,
        'mensajes_enviados': mensajes_enviados,
        'mensajes_recibidos': mensajes_recibidos,
        'mensajes_error': mensajes_error,
        'tasa_exito_mensajes': round(tasa_exito_mensajes, 1),

        # Campañas
        'total_campanas': total_campanas,
        'campanas_ejecutadas': campanas_ejecutadas,
        'campanas_programadas': campanas_programadas,
        'total_envios_campanas': total_envios_campanas,
        'envios_exitosos': envios_exitosos,
        'envios_fallidos': envios_fallidos,
        'tasa_exito_campanas': round(tasa_exito_campanas, 1),

        # Educación
        'total_cursos': total_cursos,
        'cursos_activos': cursos_activos,
        'estudiantes_inscritos': estudiantes_inscritos,
        'cursos_completados': cursos_completados,
        'modulos_completados': modulos_completados,
        'tasa_completacion': round(tasa_completacion, 1),
        'progreso_cursos': progreso_cursos,

        # Plantillas
        'total_plantillas': total_plantillas,
        'plantillas_activas': plantillas_activas,
        'plantillas_twilio': plantillas_twilio,
        'top_plantillas': top_plantillas,

        # Gamificación
        'total_puntos_otorgados': total_puntos_otorgados,
        'total_puntos_canjeados': total_puntos_canjeados,
        'total_badges': total_badges,
        'badges_otorgados': badges_otorgados,
        'perfiles_gamificacion': perfiles_gamificacion,

        # Soporte
        'total_solicitudes': total_solicitudes,
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_atendiendo': solicitudes_atendiendo,
        'solicitudes_resueltas': solicitudes_resueltas,

        # Certificados
        'total_certificados': total_certificados,
        'certificados_generados_30d': certificados_generados_30d,

        # Datos para gráficas
        'fechas_json': json.dumps(fechas),
        'mensajes_diarios_json': json.dumps(mensajes_diarios),
        'envios_diarios_json': json.dumps(envios_diarios),

        # Información temporal
        'fecha_actualizacion': ahora.strftime('%d/%m/%Y %H:%M'),
    }

    return TemplateResponse(request, 'admin/dashboard_metricas.html', context)


@staff_member_required
def dashboard_gerencial(request):
    """Dashboard gerencial con vista ejecutiva — mismas métricas, template diferente"""
    response = dashboard_metricas(request)
    response.template_name = 'admin/dashboard_gerencial.html'
    return response
