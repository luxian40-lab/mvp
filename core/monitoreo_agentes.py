"""
Sistema de Monitoreo y Análisis de Agentes IA
Tracking detallado de qué agente responde cada mensaje
"""

from django.utils import timezone
from .models import WhatsappLog
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Archivo de estadísticas
STATS_FILE = Path(__file__).parent.parent / 'logs' / 'agentes_stats.json'


def registrar_uso_agente(telefono: str, mensaje: str, agente_usado: str, 
                        respuesta: str, tiempo_respuesta: float = 0):
    """
    Registra cada vez que un agente es usado
    
    Args:
        telefono: Número del estudiante
        mensaje: Mensaje original
        agente_usado: Nombre del agente (AgenteTutor, AgenteMotivador, etc.)
        respuesta: Respuesta generada
        tiempo_respuesta: Tiempo en segundos
    """
    try:
        # Cargar estadísticas existentes
        stats = cargar_estadisticas()
        
        # Incrementar contador del agente
        if agente_usado not in stats['uso_agentes']:
            stats['uso_agentes'][agente_usado] = 0
        stats['uso_agentes'][agente_usado] += 1
        
        # Agregar al historial reciente
        stats['historial_reciente'].append({
            'fecha': timezone.now().isoformat(),
            'telefono': telefono[-4:],  # Solo últimos 4 dígitos por privacidad
            'agente': agente_usado,
            'mensaje_preview': mensaje[:30] + '...' if len(mensaje) > 30 else mensaje,
            'respuesta_preview': respuesta[:50] + '...' if len(respuesta) > 50 else respuesta,
            'tiempo_respuesta': round(tiempo_respuesta, 2)
        })
        
        # Mantener solo últimos 50 registros
        stats['historial_reciente'] = stats['historial_reciente'][-50:]
        
        # Actualizar última ejecución
        stats['ultima_actualizacion'] = timezone.now().isoformat()
        
        # Guardar
        guardar_estadisticas(stats)
        
        logger.info(f"📊 Registrado uso de {agente_usado} para {telefono[-4:]}")
        
    except Exception as e:
        logger.error(f"❌ Error registrando uso de agente: {e}")


def cargar_estadisticas():
    """Carga estadísticas desde archivo JSON"""
    try:
        if STATS_FILE.exists():
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                'uso_agentes': {},
                'historial_reciente': [],
                'ultima_actualizacion': None
            }
    except Exception as e:
        logger.error(f"❌ Error cargando estadísticas: {e}")
        return {
            'uso_agentes': {},
            'historial_reciente': [],
            'ultima_actualizacion': None
        }


def guardar_estadisticas(stats):
    """Guarda estadísticas en archivo JSON"""
    try:
        # Crear directorio si no existe
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error guardando estadísticas: {e}")


def generar_reporte_agentes():
    """
    Genera reporte de uso de agentes
    
    Returns:
        str: Reporte formateado
    """
    stats = cargar_estadisticas()
    
    reporte = "=" * 60 + "\n"
    reporte += "📊 REPORTE DE USO DE AGENTES IA (Estilo Huaku)\n"
    reporte += "=" * 60 + "\n\n"
    
    # Uso por agente
    reporte += "🤖 USO POR AGENTE:\n"
    reporte += "-" * 40 + "\n"
    
    total_usos = sum(stats['uso_agentes'].values())
    
    if total_usos > 0:
        for agente, count in sorted(stats['uso_agentes'].items(), 
                                     key=lambda x: x[1], reverse=True):
            porcentaje = (count / total_usos) * 100
            barra = "█" * int(porcentaje / 5)
            reporte += f"{agente:20} │ {count:4d} usos │ {porcentaje:5.1f}% │ {barra}\n"
    else:
        reporte += "   (Sin datos aún)\n"
    
    reporte += f"\n   TOTAL: {total_usos} interacciones\n"
    
    # Historial reciente
    reporte += "\n📝 ÚLTIMAS INTERACCIONES:\n"
    reporte += "-" * 40 + "\n"
    
    for entry in stats['historial_reciente'][-10:]:  # Últimas 10
        fecha = entry['fecha'][:19].replace('T', ' ')
        reporte += f"\n[{fecha}] Usuario *{entry['telefono']}\n"
        reporte += f"   Agente: {entry['agente']}\n"
        reporte += f"   Mensaje: {entry['mensaje_preview']}\n"
        reporte += f"   Respuesta: {entry['respuesta_preview']}\n"
        reporte += f"   Tiempo: {entry['tiempo_respuesta']}s\n"
    
    # Última actualización
    if stats['ultima_actualizacion']:
        reporte += f"\n📅 Última actualización: {stats['ultima_actualizacion'][:19].replace('T', ' ')}\n"
    
    reporte += "\n" + "=" * 60 + "\n"
    
    return reporte


def analizar_efectividad_agentes():
    """
    Analiza la efectividad de cada agente
    
    Returns:
        dict con métricas por agente
    """
    stats = cargar_estadisticas()
    
    analisis = {}
    
    for agente, count in stats['uso_agentes'].items():
        # Calcular métricas básicas
        historial_agente = [h for h in stats['historial_reciente'] 
                           if h['agente'] == agente]
        
        tiempo_promedio = 0
        if historial_agente:
            tiempo_promedio = sum(h['tiempo_respuesta'] for h in historial_agente) / len(historial_agente)
        
        analisis[agente] = {
            'total_usos': count,
            'tiempo_promedio_respuesta': round(tiempo_promedio, 2),
            'ultimos_5_usos': historial_agente[-5:]
        }
    
    return analisis
