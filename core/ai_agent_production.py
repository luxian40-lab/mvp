"""
🚀 AGENTE IA CON FUNCTION CALLING - VERSIÓN PRODUCCIÓN

Este es el agente mejorado que reemplazará ai_assistant.py
Incluye:
- ✅ Function Calling (consulta datos automáticamente)
- ✅ Caché para mejor performance
- ✅ Optimizado para miles de usuarios
- ✅ Fallback robusto
- ✅ Logging detallado
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from functools import lru_cache

from openai import OpenAI
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q

from .models import Estudiante, WhatsappLog, EnvioLog, Campana

# Configurar logging
logger = logging.getLogger(__name__)


# ============================================================================
# FUNCIONES QUE LA IA PUEDE LLAMAR
# ============================================================================

@lru_cache(maxsize=1000)  # Caché en memoria para consultas frecuentes
def get_student_progress(student_phone: str) -> Dict[str, Any]:
    """
    Obtiene el progreso académico del estudiante con caché.
    
    Args:
        student_phone: Teléfono del estudiante
        
    Returns:
        Dict con progreso completo
    """
    cache_key = f"student_progress_{student_phone}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        # Optimizado con select_related y prefetch_related
        estudiante = Estudiante.objects.prefetch_related('etiquetas').get(
            telefono=student_phone
        )
        
        # Usar aggregation para mejor performance
        stats = EnvioLog.objects.filter(estudiante=estudiante).aggregate(
            total=Count('id'),
            completados=Count('id', filter=Q(estado='ENVIADO')),
            pendientes=Count('id', filter=Q(estado='PENDIENTE'))
        )
        
        total = stats['total'] or 1
        completados = stats['completados'] or 0
        progreso_porcentaje = int((completados / total) * 100)
        
        result = {
            "success": True,
            "nombre": estudiante.nombre,
            "progreso_porcentaje": progreso_porcentaje,
            "tareas_completadas": completados,
            "tareas_totales": total,
            "tareas_pendientes": stats['pendientes'],
            "cursos_activos": [e.nombre for e in estudiante.etiquetas.all()],
            "activo": estudiante.activo,
            "fecha_registro": estudiante.fecha_registro.strftime("%Y-%m-%d")
        }
        
        # Guardar en caché por 5 minutos
        cache.set(cache_key, result, 300)
        return result
        
    except Estudiante.DoesNotExist:
        return {"success": False, "error": "Estudiante no encontrado"}
    except Exception as e:
        logger.error(f"Error en get_student_progress: {str(e)}")
        return {"success": False, "error": str(e)}


def get_pending_tasks(student_phone: str, limit: int = 5) -> Dict[str, Any]:
    """Obtiene tareas pendientes optimizado"""
    try:
        estudiante = Estudiante.objects.only('id').get(telefono=student_phone)
        
        # Optimizado con select_related
        pendientes = EnvioLog.objects.filter(
            estudiante=estudiante,
            estado='PENDIENTE'
        ).select_related('campana').only(
            'fecha_envio', 'campana__nombre'
        ).order_by('fecha_envio')[:limit]
        
        tareas_list = []
        hoy = datetime.now().date()
        
        for envio in pendientes:
            dias_restantes = (envio.fecha_envio - hoy).days
            tareas_list.append({
                "nombre": envio.campana.nombre,
                "fecha_envio": envio.fecha_envio.strftime("%Y-%m-%d"),
                "dias_restantes": dias_restantes,
                "urgente": dias_restantes <= 2
            })
        
        return {
            "success": True,
            "total_pendientes": len(tareas_list),
            "tareas": tareas_list
        }
        
    except Estudiante.DoesNotExist:
        return {"success": False, "error": "Estudiante no encontrado"}
    except Exception as e:
        logger.error(f"Error en get_pending_tasks: {str(e)}")
        return {"success": False, "error": str(e)}


def get_next_class(student_phone: str) -> Dict[str, Any]:
    """Obtiene próxima clase optimizado"""
    try:
        estudiante = Estudiante.objects.only('id').get(telefono=student_phone)
        
        proxima = EnvioLog.objects.filter(
            estudiante=estudiante,
            estado='PENDIENTE'
        ).select_related('campana').only(
            'fecha_envio', 'campana__nombre'
        ).order_by('fecha_envio').first()
        
        if proxima:
            dias = (proxima.fecha_envio - datetime.now().date()).days
            return {
                "success": True,
                "tiene_proxima_clase": True,
                "nombre": proxima.campana.nombre,
                "fecha": proxima.fecha_envio.strftime("%Y-%m-%d"),
                "dias_restantes": dias
            }
        else:
            return {
                "success": True,
                "tiene_proxima_clase": False,
                "mensaje": "No hay clases programadas"
            }
        
    except Estudiante.DoesNotExist:
        return {"success": False, "error": "Estudiante no encontrado"}
    except Exception as e:
        logger.error(f"Error en get_next_class: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# AGENTE IA CON FUNCTION CALLING
# ============================================================================

class EkiAIAgent:
    """
    Agente IA de producción con Function Calling.
    Optimizado para miles de usuarios concurrentes.
    """
    
    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        
        # System prompt optimizado para WhatsApp
        self.system_prompt = """Eres Eki, asistente educativo de estudiantes.

PERSONALIDAD:
- Amigable pero profesional
- Conciso (máximo 3 párrafos para WhatsApp)
- Motivador y positivo
- Usa emojis con moderación

CAPACIDADES:
Tienes acceso a funciones para consultar:
1. get_student_progress: Progreso académico completo
2. get_pending_tasks: Próximas 5 tareas
3. get_next_class: Siguiente clase programada

REGLAS:
- Respuestas de máximo 300 caracteres cuando sea posible
- Siempre termina con pregunta o llamado a la acción
- Si el estudiante parece frustrado, sé más empático
- Usa las funciones cuando necesites datos reales
- Si no tienes datos, di que consultarás y ofrece ayuda general"""
        
        # Definir funciones disponibles
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_student_progress",
                    "description": "Consulta progreso académico: porcentaje completado, tareas, cursos activos",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {
                                "type": "string",
                                "description": "Teléfono del estudiante"
                            }
                        },
                        "required": ["student_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pending_tasks",
                    "description": "Lista tareas pendientes con fechas de vencimiento",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {"type": "string"},
                            "limit": {
                                "type": "integer",
                                "default": 5,
                                "description": "Cantidad máxima de tareas"
                            }
                        },
                        "required": ["student_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_next_class",
                    "description": "Consulta próxima clase o módulo programado",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {"type": "string"}
                        },
                        "required": ["student_phone"]
                    }
                }
            }
        ]
        
        # Mapeo de funciones
        self.available_functions = {
            "get_student_progress": get_student_progress,
            "get_pending_tasks": get_pending_tasks,
            "get_next_class": get_next_class
        }
    
    def generar_respuesta(
        self, 
        mensaje: str, 
        telefono: str,
        incluir_historial: bool = True,
        max_historial: int = 5
    ) -> str:
        """
        Genera respuesta usando Function Calling con caché y optimizaciones.
        
        Args:
            mensaje: Mensaje del estudiante
            telefono: Número de teléfono
            incluir_historial: Si incluir conversación previa
            max_historial: Cantidad máxima de mensajes previos
            
        Returns:
            Respuesta generada
        """
        try:
            # Construir mensajes
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Agregar historial si se solicita
            if incluir_historial:
                historial = self._get_conversation_history(telefono, max_historial)
                messages.extend(historial)
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": mensaje})
            
            # Primera llamada a OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=300  # Respuestas cortas para WhatsApp
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # Si la IA quiere llamar funciones
            if tool_calls:
                messages.append(response_message)
                
                # Ejecutar funciones
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"🔧 Function call: {function_name}({function_args})")
                    
                    # Ejecutar función
                    function_response = self.available_functions[function_name](**function_args)
                    
                    # Agregar resultado
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response)
                    })
                
                # Segunda llamada con resultados
                second_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=300
                )
                
                return second_response.choices[0].message.content
            
            # Si no necesitó funciones
            return response_message.content
            
        except Exception as e:
            logger.error(f"Error en generar_respuesta: {str(e)}")
            return self._respuesta_fallback()
    
    def _get_conversation_history(self, telefono: str, limit: int) -> List[Dict]:
        """Obtiene historial de conversación optimizado"""
        logs = WhatsappLog.objects.filter(
            telefono=telefono
        ).only('mensaje', 'estado').order_by('-fecha')[:limit]
        
        messages = []
        for log in reversed(logs):
            role = "user" if log.estado == "INCOMING" else "assistant"
            if log.mensaje:
                messages.append({"role": role, "content": log.mensaje})
        
        return messages
    
    def _respuesta_fallback(self) -> str:
        """Respuesta de emergencia si falla todo"""
        return """¡Hola! 👋 Soy Eki, tu asistente educativo.

En este momento tengo problemas técnicos, pero estoy aquí para ayudarte.

¿Qué necesitas? Escríbeme tu pregunta."""


# ============================================================================
# FUNCIÓN PRINCIPAL PARA USAR EN VIEWS.PY
# ============================================================================

def responder_con_ia_mejorado(mensaje: str, telefono: str) -> str:
    """
    Función principal para generar respuestas con IA + Function Calling.
    Usa esta en lugar de responder_con_ia() en views.py
    
    Args:
        mensaje: Texto del usuario
        telefono: Número del estudiante
        
    Returns:
        Respuesta generada con IA
    """
    try:
        # Crear agente
        agente = EkiAIAgent()
        
        # Detectar bienvenida
        mensaje_lower = mensaje.lower().strip()
        if any(s in mensaje_lower for s in ['hola', 'holi', 'hey', 'buenos', 'buenas']):
            try:
                estudiante = Estudiante.objects.only('nombre').get(telefono=telefono)
                # Si es primera vez (menos de 2 mensajes), bienvenida especial
                if WhatsappLog.objects.filter(telefono=telefono).count() < 2:
                    return f"""¡Hola {estudiante.nombre}! 👋 Bienvenido a Eki

Soy tu asistente educativo inteligente. Puedo ayudarte con:

📊 Consultar tu progreso
📝 Ver tus tareas pendientes
💡 Responder dudas de estudio

¿En qué puedo ayudarte hoy?"""
            except Estudiante.DoesNotExist:
                pass
        
        # Generar respuesta con IA + Function Calling
        return agente.generar_respuesta(mensaje, telefono, incluir_historial=True)
        
    except Exception as e:
        logger.error(f"Error en responder_con_ia_mejorado: {str(e)}")
        
        # Fallback a sistema básico
        from .intent_detector import detect_intent
        from .response_templates import get_response_for_intent
        
        intent = detect_intent(mensaje)
        try:
            estudiante = Estudiante.objects.only('nombre').get(telefono=telefono)
            nombre = estudiante.nombre
        except:
            nombre = "Estudiante"
        
        return get_response_for_intent(intent, nombre)
