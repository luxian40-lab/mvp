"""
Personalización del dashboard del admin
"""
from django.contrib import admin
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)

def setup_custom_admin_dashboard():
    """Configura un dashboard personalizado en el admin"""
    # Cambiar los atributos del sitio default de Django
    admin.site.site_header = "🌾 EKI - Administración"
    admin.site.site_title = "EKI Admin"
    admin.site.index_title = "Panel de Control"

    # Guardar el método original
    _original_index = admin.site.index

    def eki_custom_index(request, extra_context=None):
        """Dashboard con estadísticas de estado"""
        import os
        from django.conf import settings
        from core.models import (
            Estudiante, Curso, ProgresoEstudiante,
            Certificado, WhatsappLog, Cliente
        )
        
        try:
            # Contar totales
            total_estudiantes = Estudiante.objects.count()
            estudiantes_activos = Estudiante.objects.filter(activo=True).count()
            total_cursos = Curso.objects.count()
            progreso_completado = ProgresoEstudiante.objects.filter(completado=True).count()
            certificados_emitidos = Certificado.objects.filter(emitido=True).count()
            mensajes_recientes = WhatsappLog.objects.filter(estado='SENT').count()
            mensajes_error = WhatsappLog.objects.filter(estado='ERROR').count()
            
            # Verificar estado del sistema
            vosk_disponible = os.path.exists(os.path.join(settings.BASE_DIR, 'models/vosk-model-small-es-0.42'))
            twilio_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_conectado = bool(twilio_token and len(twilio_token) > 10)
            media_path = os.path.join(settings.MEDIA_ROOT, 'certificados')
            media_disponible = os.path.exists(media_path) and os.access(media_path, os.W_OK)
            
            # Estadísticas de certificados por curso
            certificados_por_curso = list(Certificado.objects.filter(emitido=True).values('curso__nombre').annotate(count=Count('id')).order_by('-count'))
            
            # Estadísticas por cliente
            clientes_stats = []
            for cliente in Cliente.objects.all():
                cursos_cliente = Curso.objects.filter(cliente=cliente)
                estudiantes_cliente = Estudiante.objects.filter(cliente=cliente)
                progreso_cliente = ProgresoEstudiante.objects.filter(estudiante__cliente=cliente)
                mensajes_cliente = WhatsappLog.objects.filter(telefono__in=estudiantes_cliente.values_list('telefono', flat=True)).count()
                certificados_cliente = Certificado.objects.filter(estudiante__cliente=cliente, emitido=True).count()
                
                # Calcular progreso promedio por curso
                progreso_por_curso = []
                for curso in cursos_cliente:
                    progresos_curso = progreso_cliente.filter(curso=curso)
                    if progresos_curso.exists():
                        avg_progreso = sum([p.porcentaje_avance() for p in progresos_curso]) / progresos_curso.count()
                        completados = progresos_curso.filter(completado=True).count()
                        progreso_por_curso.append({
                            'curso': curso,
                            'avg_progreso': avg_progreso,
                            'completados': completados,
                            'total': progresos_curso.count()
                        })
                
                clientes_stats.append({
                    'cliente': cliente,
                    'total_estudiantes': estudiantes_cliente.count(),
                    'total_cursos': cursos_cliente.count(),
                    'total_mensajes': mensajes_cliente,
                    'total_certificados': certificados_cliente,
                    'progreso_por_curso': progreso_por_curso,
                })
            
            # Obtener logs recientes (últimos 10)
            logs_recientes = list(WhatsappLog.objects.all().order_by('-fecha')[:10].values(
                'fecha', 'tipo', 'estado', 'telefono'
            ))
            
            # Certificados generados recientemente
            certs_recientes = list(Certificado.objects.filter(emitido=True).order_by('-fecha_emision')[:5].values(
                'codigo_verificacion', 'estudiante__nombre', 'curso__nombre', 'fecha_emision'
            ))
            
            extra_context = extra_context or {}
            extra_context.update({
                'estadisticas': {
                    'total_estudiantes': total_estudiantes,
                    'estudiantes_activos': estudiantes_activos,
                    'total_cursos': total_cursos,
                    'progreso_completado': progreso_completado,
                    'certificados_emitidos': certificados_emitidos,
                    'mensajes_recientes': mensajes_recientes,
                    'mensajes_error': mensajes_error,
                },
                'estado_sistema': {
                    'vosk': {
                        'disponible': vosk_disponible,
                        'emoji': '✅' if vosk_disponible else '❌',
                        'texto': 'Modelo VOSK disponible' if vosk_disponible else 'Modelo VOSK NO encontrado',
                    },
                    'twilio': {
                        'disponible': twilio_conectado,
                        'emoji': '✅' if twilio_conectado else '❌',
                        'texto': 'Twilio conectado' if twilio_conectado else 'Twilio NO configurado',
                    },
                    'media': {
                        'disponible': media_disponible,
                        'emoji': '✅' if media_disponible else '❌',
                        'texto': 'Directorio de media accesible' if media_disponible else 'Directorio de media NO accesible',
                    },
                },
                'certificados_por_curso': certificados_por_curso,
                'clientes_stats': clientes_stats,
                'logs_recientes': logs_recientes,
                'certs_recientes': certs_recientes,
                'dashboard_control_url': '/admin/dashboard/',  # Enlace al dashboard excepcional
            })
        except Exception as e:
            logger.error(f"Error cargando estadísticas del dashboard: {str(e)}")
            extra_context = extra_context or {}
        
        # Llamar al método original
        return _original_index(request, extra_context=extra_context)

    # Reemplazar el método del sitio admin
    admin.site.index = eki_custom_index
