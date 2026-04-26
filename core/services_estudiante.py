"""
Servicios de aplicación para endpoints del estudiante.
"""

from core.models import EnvioLog, Estudiante


def get_estudiante_payload(telefono):
    estudiante = Estudiante.objects.get(telefono=telefono)
    return {
        'id': estudiante.id,
        'nombre': estudiante.nombre,
        'telefono': estudiante.telefono,
        'activo': estudiante.activo,
    }


def get_estudiante_progreso_payload(telefono):
    estudiante = Estudiante.objects.get(telefono=telefono)

    total_envios = EnvioLog.objects.filter(estudiante=estudiante).count()
    exitosos = EnvioLog.objects.filter(estudiante=estudiante, estado='ENVIADO').count()
    fallidos = EnvioLog.objects.filter(estudiante=estudiante, estado='FALLIDO').count()
    progreso_porcentaje = int((exitosos / total_envios * 100) if total_envios > 0 else 0)

    ultimo_envio = EnvioLog.objects.filter(estudiante=estudiante).order_by('-fecha_envio').first()
    modulo_actual = ultimo_envio.campana.plantilla.nombre_interno if ultimo_envio else 'Introducción'

    return {
        'estudiante': {
            'nombre': estudiante.nombre,
            'telefono': telefono,
        },
        'progreso': {
            'porcentaje': progreso_porcentaje,
            'total_tareas': total_envios,
            'tareas_completadas': exitosos,
            'tareas_fallidas': fallidos,
            'modulo_actual': modulo_actual,
            'estado': 'En progreso' if progreso_porcentaje < 100 else 'Completado',
        },
    }


def get_estudiante_siguiente_tarea_payload(telefono):
    estudiante = Estudiante.objects.get(telefono=telefono)
    siguiente = EnvioLog.objects.filter(
        estudiante=estudiante,
        estado='PENDIENTE',
    ).order_by('fecha_envio').first()

    base_estudiante = {
        'nombre': estudiante.nombre,
        'telefono': telefono,
    }

    if siguiente:
        return {
            'estudiante': base_estudiante,
            'siguiente_tarea': {
                'id': siguiente.id,
                'campana': siguiente.campana.nombre,
                'plantilla': siguiente.campana.plantilla.nombre_interno,
                'descripcion': siguiente.campana.plantilla.cuerpo_mensaje[:100],
                'fecha_vence': siguiente.fecha_envio.isoformat() if siguiente.fecha_envio else None,
                'estado': siguiente.estado,
            },
        }

    return {
        'estudiante': base_estudiante,
        'siguiente_tarea': {
            'id': None,
            'campana': None,
            'plantilla': None,
            'descripcion': '¡Felicidades! No tienes tareas pendientes',
            'fecha_vence': None,
            'estado': 'COMPLETADO',
        },
    }
