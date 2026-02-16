"""
API REST para datos de progreso y tareas del estudiante.
Endpoints:
- GET /api/estudiante/{telefono}/ → datos del estudiante
- GET /api/estudiante/{telefono}/progreso/ → progreso detallado
- GET /api/estudiante/{telefono}/siguiente-tarea/ → siguiente tarea
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Estudiante, Campana, EnvioLog


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
