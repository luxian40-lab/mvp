"""
🎯 IMPLEMENTACIÓN: FUNCTION CALLING PARA EKI

Este script implementa OpenAI Function Calling para que el agente
pueda consultar datos reales automáticamente.

Ventajas:
- ✅ IA decide cuándo necesita datos
- ✅ Respuestas más precisas
- ✅ Menos tokens = más económico
- ✅ No requiere infraestructura adicional
"""
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI
from typing import Dict, Any, List

# Importar modelos Django
import django
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, EnvioLog, WhatsappLog, Campana


# ============================================================================
# FUNCIONES QUE LA IA PUEDE LLAMAR
# ============================================================================

def get_student_progress(student_phone: str) -> Dict[str, Any]:
    """
    Obtiene el progreso académico completo del estudiante.
    
    Args:
        student_phone: Teléfono del estudiante
        
    Returns:
        Dict con progreso, tareas completadas, pendientes, etc.
    """
    try:
        estudiante = Estudiante.objects.get(telefono=student_phone)
        
        # Calcular estadísticas
        total_envios = EnvioLog.objects.filter(estudiante=estudiante).count()
        completados = EnvioLog.objects.filter(estudiante=estudiante, estado='ENVIADO').count()
        pendientes = EnvioLog.objects.filter(estudiante=estudiante, estado='PENDIENTE').count()
        
        progreso_porcentaje = int((completados / total_envios * 100) if total_envios > 0 else 0)
        
        # Etiquetas/cursos
        etiquetas = [e.nombre for e in estudiante.etiquetas.all()]
        
        return {
            "success": True,
            "nombre": estudiante.nombre,
            "progreso_porcentaje": progreso_porcentaje,
            "tareas_completadas": completados,
            "tareas_totales": total_envios,
            "tareas_pendientes": pendientes,
            "cursos_activos": etiquetas,
            "activo": estudiante.activo,
            "fecha_registro": estudiante.fecha_registro.strftime("%Y-%m-%d")
        }
        
    except Estudiante.DoesNotExist:
        return {
            "success": False,
            "error": "Estudiante no encontrado"
        }


def get_pending_tasks(student_phone: str, limit: int = 5) -> Dict[str, Any]:
    """
    Obtiene las próximas tareas pendientes del estudiante.
    
    Args:
        student_phone: Teléfono del estudiante
        limit: Cantidad máxima de tareas a retornar
        
    Returns:
        Dict con lista de tareas pendientes
    """
    try:
        estudiante = Estudiante.objects.get(telefono=student_phone)
        
        pendientes = EnvioLog.objects.filter(
            estudiante=estudiante,
            estado='PENDIENTE'
        ).select_related('campana').order_by('fecha_envio')[:limit]
        
        tareas_list = []
        for envio in pendientes:
            dias_hasta_vencimiento = (envio.fecha_envio - datetime.now().date()).days
            
            tareas_list.append({
                "nombre": envio.campana.nombre,
                "fecha_envio": envio.fecha_envio.strftime("%Y-%m-%d"),
                "dias_restantes": dias_hasta_vencimiento,
                "urgente": dias_hasta_vencimiento <= 2
            })
        
        return {
            "success": True,
            "total_pendientes": len(tareas_list),
            "tareas": tareas_list
        }
        
    except Estudiante.DoesNotExist:
        return {
            "success": False,
            "error": "Estudiante no encontrado"
        }


def get_next_class(student_phone: str) -> Dict[str, Any]:
    """
    Obtiene información sobre la próxima clase/módulo del estudiante.
    
    Args:
        student_phone: Teléfono del estudiante
        
    Returns:
        Dict con detalles de la próxima clase
    """
    try:
        estudiante = Estudiante.objects.get(telefono=student_phone)
        
        # Buscar próxima campaña/clase
        proxima_campana = EnvioLog.objects.filter(
            estudiante=estudiante,
            estado='PENDIENTE'
        ).select_related('campana').order_by('fecha_envio').first()
        
        if proxima_campana:
            return {
                "success": True,
                "tiene_proxima_clase": True,
                "nombre": proxima_campana.campana.nombre,
                "fecha": proxima_campana.fecha_envio.strftime("%Y-%m-%d"),
                "dias_restantes": (proxima_campana.fecha_envio - datetime.now().date()).days
            }
        else:
            return {
                "success": True,
                "tiene_proxima_clase": False,
                "mensaje": "No hay clases programadas próximamente"
            }
        
    except Estudiante.DoesNotExist:
        return {
            "success": False,
            "error": "Estudiante no encontrado"
        }


def get_conversation_summary(student_phone: str, days: int = 7) -> Dict[str, Any]:
    """
    Obtiene un resumen de la conversación reciente con el estudiante.
    
    Args:
        student_phone: Teléfono del estudiante
        days: Cantidad de días hacia atrás
        
    Returns:
        Dict con estadísticas de conversación
    """
    fecha_inicio = datetime.now() - timedelta(days=days)
    
    mensajes = WhatsappLog.objects.filter(
        telefono=student_phone,
        fecha__gte=fecha_inicio
    )
    
    total_mensajes = mensajes.count()
    mensajes_entrantes = mensajes.filter(estado='INCOMING').count()
    mensajes_salientes = total_mensajes - mensajes_entrantes
    
    # Temas mencionados (análisis simple)
    temas_mencionados = []
    keywords = {
        "progreso": ["progreso", "avance", "porcentaje"],
        "tareas": ["tarea", "pendiente", "actividad"],
        "ayuda": ["ayuda", "duda", "no entiendo"],
        "motivacion": ["difícil", "cansado", "complicado"]
    }
    
    for tema, palabras in keywords.items():
        for mensaje in mensajes:
            if any(palabra in mensaje.mensaje.lower() for palabra in palabras):
                temas_mencionados.append(tema)
                break
    
    return {
        "success": True,
        "dias_analizados": days,
        "total_mensajes": total_mensajes,
        "mensajes_estudiante": mensajes_entrantes,
        "mensajes_eki": mensajes_salientes,
        "engagement": "alto" if mensajes_entrantes > 5 else "medio" if mensajes_entrantes > 2 else "bajo",
        "temas_principales": list(set(temas_mencionados)),
        "ultima_interaccion": mensajes.order_by('-fecha').first().fecha.strftime("%Y-%m-%d %H:%M") if mensajes.exists() else None
    }


# ============================================================================
# FUNCIÓN PRINCIPAL CON FUNCTION CALLING
# ============================================================================

class EkiAIWithFunctions:
    """Agente IA de Eki con capacidad de llamar funciones"""
    
    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        
        # System prompt
        self.system_prompt = """Eres Eki, un asistente educativo inteligente para estudiantes.

Tu misión:
- Ayudar a estudiantes con su progreso académico
- Responder preguntas sobre tareas y clases
- Motivar y apoyar el aprendizaje
- Ser amigable, conciso y usar emojis

IMPORTANTE:
- Tienes acceso a funciones para consultar datos reales
- Úsalas cuando el estudiante pregunte por progreso, tareas, o clases
- Las respuestas deben ser breves (máximo 3 párrafos) para WhatsApp
- Siempre termina con una pregunta o llamado a la acción

Funciones disponibles:
1. get_student_progress: Progreso académico completo
2. get_pending_tasks: Tareas pendientes (próximas 5)
3. get_next_class: Próxima clase programada
4. get_conversation_summary: Resumen de conversaciones recientes"""
        
        # Definir funciones disponibles
        self.functions = [
            {
                "type": "function",
                "function": {
                    "name": "get_student_progress",
                    "description": "Obtiene el progreso académico completo del estudiante (porcentaje, tareas completadas, pendientes, cursos activos)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {
                                "type": "string",
                                "description": "Número de teléfono del estudiante (sin + ni espacios)"
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
                    "description": "Lista las próximas tareas pendientes del estudiante con fechas de vencimiento",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {
                                "type": "string",
                                "description": "Número de teléfono del estudiante"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Cantidad máxima de tareas a retornar (default: 5)",
                                "default": 5
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
                    "description": "Obtiene información sobre la próxima clase o módulo programado",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {
                                "type": "string",
                                "description": "Número de teléfono del estudiante"
                            }
                        },
                        "required": ["student_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conversation_summary",
                    "description": "Obtiene un resumen de las conversaciones recientes del estudiante (temas, engagement, frecuencia)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "student_phone": {
                                "type": "string",
                                "description": "Número de teléfono del estudiante"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Días hacia atrás para analizar (default: 7)",
                                "default": 7
                            }
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
            "get_next_class": get_next_class,
            "get_conversation_summary": get_conversation_summary
        }
    
    def generar_respuesta(self, mensaje: str, telefono: str) -> str:
        """
        Genera respuesta usando Function Calling.
        
        Args:
            mensaje: Mensaje del estudiante
            telefono: Número de teléfono
            
        Returns:
            Respuesta generada (puede incluir datos de funciones)
        """
        # Construir mensajes
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": mensaje}
        ]
        
        # Primera llamada a OpenAI
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.functions,
            tool_choice="auto"  # IA decide si necesita funciones
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        # Si la IA quiere llamar funciones
        if tool_calls:
            # Agregar respuesta de IA a mensajes
            messages.append(response_message)
            
            # Ejecutar cada función solicitada
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"🔧 IA llama función: {function_name}({function_args})")
                
                # Ejecutar función
                function_response = self.available_functions[function_name](**function_args)
                
                # Agregar resultado a mensajes
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(function_response)
                })
            
            # Segunda llamada con resultados de funciones
            second_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            return second_response.choices[0].message.content
        
        # Si no necesitó funciones, retornar respuesta directa
        return response_message.content


# ============================================================================
# DEMO INTERACTIVA
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🤖 EKI AI CON FUNCTION CALLING")
    print("=" * 70)
    
    print("\n✨ Este agente puede consultar datos automáticamente:")
    print("   - Progreso académico")
    print("   - Tareas pendientes")
    print("   - Próximas clases")
    print("   - Historial de conversación")
    
    # Crear agente
    try:
        agente = EkiAIWithFunctions()
        print("\n✅ Agente inicializado correctamente")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        exit(1)
    
    # Obtener o crear estudiante de prueba
    telefono_test = input("\n📱 Teléfono del estudiante (Enter para usar prueba): ").strip()
    
    if not telefono_test:
        telefono_test = "573001234567"
        # Crear estudiante de prueba si no existe
        estudiante, created = Estudiante.objects.get_or_create(
            telefono=telefono_test,
            defaults={"nombre": "Juan Test", "activo": True}
        )
        print(f"   Usando estudiante de prueba: {estudiante.nombre}")
    else:
        telefono_test = telefono_test.replace('+', '').replace(' ', '')
    
    print("\n" + "=" * 70)
    print("💬 CHAT INTERACTIVO")
    print("=" * 70)
    print("\nPrueba preguntas como:")
    print("   - ¿Cuál es mi progreso?")
    print("   - ¿Qué tareas tengo pendientes?")
    print("   - ¿Cuándo es mi próxima clase?")
    print("   - ¿Qué tan activo he sido?")
    print("\nEscribe 'salir' para terminar\n")
    
    while True:
        mensaje = input("👤 Tú: ").strip()
        
        if mensaje.lower() in ['salir', 'exit', 'quit']:
            print("\n👋 ¡Hasta luego!")
            break
        
        if not mensaje:
            continue
        
        try:
            print("\n🤖 Eki: ", end="", flush=True)
            respuesta = agente.generar_respuesta(mensaje, telefono_test)
            print(respuesta)
            print()
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETADA")
    print("=" * 70)
    print("\n💡 Próximos pasos:")
    print("   1. Integrar en views.py (webhook)")
    print("   2. Agregar más funciones según necesites")
    print("   3. Implementar triggers con Celery")
    print("   4. Considerar n8n para workflows complejos")
