"""
Sistema de Seguimiento Proactivo - Estilo Huaku
Detecta estudiantes inactivos y envía mensajes de motivación
"""

from django.utils import timezone
from datetime import timedelta
from .models import Estudiante, ProgresoEstudiante, WhatsappLog
from .agentes_ia import AgenteMotivador
from .utils import enviar_whatsapp_twilio
import logging

logger = logging.getLogger(__name__)


def detectar_estudiantes_inactivos(dias_inactividad=3):
    """
    Detecta estudiantes que no han interactuado en X días
    
    Args:
        dias_inactividad: Número de días sin actividad
    
    Returns:
        QuerySet de estudiantes inactivos
    """
    fecha_limite = timezone.now() - timedelta(days=dias_inactividad)
    
    # Obtener últimos mensajes de cada estudiante
    estudiantes_activos = WhatsappLog.objects.filter(
        fecha__gte=fecha_limite,
        tipo='INCOMING'
    ).values_list('telefono', flat=True).distinct()
    
    # Estudiantes con progreso pero inactivos
    estudiantes_inactivos = Estudiante.objects.filter(
        activo=True
    ).exclude(
        telefono__in=estudiantes_activos
    ).filter(
        progreso_estudiante__completado=False  # Tienen curso en progreso
    ).distinct()
    
    return estudiantes_inactivos


def enviar_mensaje_motivacional(estudiante: Estudiante, razon: str = "inactividad"):
    """
    Envía mensaje motivacional personalizado
    
    Args:
        estudiante: Objeto Estudiante
        razon: Razón del mensaje ("inactividad", "progreso_lento", etc.)
    """
    try:
        # Generar mensaje con agente motivador
        agente = AgenteMotivador(estudiante)
        
        contexto_map = {
            "inactividad": f"El estudiante lleva varios días sin estudiar.",
            "progreso_lento": f"El estudiante avanza lento en su curso.",
            "modulo_abandonado": f"El estudiante dejó un módulo a la mitad."
        }
        
        mensaje = agente.generar_mensaje_motivacional(
            contexto_especifico=contexto_map.get(razon, "")
        )
        
        # Agregar llamado a la acción
        mensaje += "\n\n📚 Escribe 'continuar' para retomar tu curso."
        
        # Enviar mensaje
        resultado = enviar_whatsapp_twilio(
            telefono=estudiante.telefono,
            texto=mensaje
        )
        
        logger.info(f"✅ Mensaje motivacional enviado a {estudiante.nombre} ({razon})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando motivación a {estudiante.nombre}: {e}")
        return False


def ejecutar_seguimiento_proactivo():
    """
    Función principal para ejecutar seguimiento automático
    Se puede llamar desde un CRON job o tarea programada
    """
    logger.info("🔄 Iniciando seguimiento proactivo...")
    
    # Detectar inactivos de 3 días
    inactivos_3d = detectar_estudiantes_inactivos(dias_inactividad=3)
    logger.info(f"📊 Estudiantes inactivos (3 días): {inactivos_3d.count()}")
    
    mensajes_enviados = 0
    
    for estudiante in inactivos_3d[:10]:  # Limitar a 10 por ejecución
        if enviar_mensaje_motivacional(estudiante, razon="inactividad"):
            mensajes_enviados += 1
    
    logger.info(f"✅ Seguimiento completado. Mensajes enviados: {mensajes_enviados}")
    return mensajes_enviados


def analizar_progreso_estudiante(estudiante: Estudiante):
    """
    Analiza el progreso del estudiante y devuelve insights
    
    Returns:
        dict con {
            'estado': 'activo'|'inactivo'|'lento',
            'porcentaje': int,
            'dias_sin_avanzar': int,
            'necesita_motivacion': bool
        }
    """
    progreso = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False
    ).first()
    
    if not progreso:
        return {
            'estado': 'sin_curso',
            'porcentaje': 0,
            'dias_sin_avanzar': 0,
            'necesita_motivacion': False
        }
    
    # Calcular días desde último mensaje
    ultimo_mensaje = WhatsappLog.objects.filter(
        telefono=estudiante.telefono,
        tipo='INCOMING'
    ).order_by('-fecha').first()
    
    dias_sin_avanzar = 0
    if ultimo_mensaje:
        dias_sin_avanzar = (timezone.now() - ultimo_mensaje.fecha).days
    
    porcentaje = progreso.porcentaje_avance()
    
    # Determinar estado
    if dias_sin_avanzar >= 5:
        estado = 'inactivo'
        necesita_motivacion = True
    elif dias_sin_avanzar >= 3:
        estado = 'lento'
        necesita_motivacion = True
    else:
        estado = 'activo'
        necesita_motivacion = False
    
    return {
        'estado': estado,
        'porcentaje': porcentaje,
        'dias_sin_avanzar': dias_sin_avanzar,
        'necesita_motivacion': necesita_motivacion
    }
