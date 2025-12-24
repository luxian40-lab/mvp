"""
Asistente de IA para conversaciones inteligentes con estudiantes.
Usa OpenAI GPT para respuestas contextuales y personalizadas.
"""
import os
from openai import OpenAI
from django.conf import settings
from .models import Estudiante, WhatsappLog


class EkiAIAssistant:
    """Asistente de IA para Eki usando OpenAI"""
    
    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en el .env")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Modelo rápido y económico
        
        # Contexto del sistema (personalidad del asistente)
        self.system_prompt = """Eres Eki, un asistente educativo amigable y motivador para estudiantes.

Tu misión:
- Ayudar a estudiantes a consultar su progreso académico
- Responder preguntas sobre sus tareas y actividades
- Motivar y apoyar el aprendizaje
- Ser claro, conciso y usar emojis apropiados

Características:
- Tono amigable pero profesional
- Respuestas cortas (máximo 3 párrafos)
- Usa emojis para hacer las respuestas más atractivas
- Siempre termina con una pregunta o llamado a la acción
- Si no sabes algo específico del estudiante, ofrece ayuda general

Recuerda:
- El estudiante te está escribiendo por WhatsApp
- Mantén las respuestas breves y escaneables
- Si mencionan "progreso", "tareas" o "ayuda", responde específicamente sobre eso"""
    
    def get_conversation_history(self, telefono: str, limit: int = 5):
        """
        Obtiene el historial reciente de conversación del estudiante.
        
        Args:
            telefono: número del estudiante
            limit: cantidad de mensajes a recuperar
            
        Returns:
            Lista de mensajes en formato OpenAI
        """
        # Buscar estudiante
        try:
            estudiante = Estudiante.objects.get(telefono=telefono)
        except Estudiante.DoesNotExist:
            return []
        
        # Obtener últimos mensajes
        logs = WhatsappLog.objects.filter(
            telefono=telefono
        ).order_by('-fecha')[:limit]
        
        # Convertir a formato OpenAI (invertir para que sea cronológico)
        messages = []
        for log in reversed(logs):
            role = "user" if log.estado == "INCOMING" else "assistant"
            messages.append({
                "role": role,
                "content": log.mensaje or ""
            })
        
        return messages
    
    def get_student_context(self, telefono: str) -> str:
        """
        Obtiene contexto del estudiante para personalizar respuestas.
        
        Args:
            telefono: número del estudiante
            
        Returns:
            String con información del estudiante
        """
        try:
            estudiante = Estudiante.objects.get(telefono=telefono)
            
            # Construir contexto
            context = f"Información del estudiante:\n"
            context += f"- Nombre: {estudiante.nombre}\n"
            context += f"- Estado: {'Activo' if estudiante.activo else 'Inactivo'}\n"
            
            # Etiquetas
            if estudiante.etiquetas.exists():
                etiquetas = ", ".join([e.nombre for e in estudiante.etiquetas.all()])
                context += f"- Etiquetas: {etiquetas}\n"
            
            # Estadísticas de mensajes
            total_mensajes = WhatsappLog.objects.filter(telefono=telefono).count()
            context += f"- Total de mensajes: {total_mensajes}\n"
            
            return context
            
        except Estudiante.DoesNotExist:
            return "Estudiante nuevo (sin información previa)"
    
    def generar_respuesta(self, mensaje_usuario: str, telefono: str, incluir_historial: bool = True) -> str:
        """
        Genera una respuesta inteligente usando OpenAI.
        
        Args:
            mensaje_usuario: mensaje enviado por el estudiante
            telefono: número del estudiante
            incluir_historial: si debe incluir conversación previa
            
        Returns:
            Respuesta generada por la IA
        """
        try:
            # Construir mensajes para OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # Agregar contexto del estudiante
            student_context = self.get_student_context(telefono)
            messages.append({
                "role": "system",
                "content": f"Contexto adicional:\n{student_context}"
            })
            
            # Agregar historial de conversación
            if incluir_historial:
                history = self.get_conversation_history(telefono, limit=5)
                messages.extend(history)
            
            # Agregar mensaje actual
            messages.append({
                "role": "user",
                "content": mensaje_usuario
            })
            
            # Llamar a OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,  # Limitar para respuestas concisas
                temperature=0.7,  # Balance entre creatividad y consistencia
            )
            
            respuesta = response.choices[0].message.content.strip()
            return respuesta
            
        except Exception as e:
            # Respuesta de fallback si hay error
            print(f"Error en OpenAI: {str(e)}")
            return self._respuesta_fallback(mensaje_usuario)
    
    def _respuesta_fallback(self, mensaje: str) -> str:
        """Respuesta básica si falla OpenAI"""
        return """¡Hola! 👋

Soy Eki, tu asistente educativo. En este momento tengo problemas para procesar tu mensaje, pero estoy aquí para ayudarte.

¿Qué necesitas?
📊 Ver tu progreso
📝 Consultar tareas
🆘 Ayuda general

*Escríbeme tu pregunta y haré mi mejor esfuerzo por ayudarte.*"""
    
    def respuesta_bienvenida(self, nombre: str) -> str:
        """Mensaje de bienvenida personalizado"""
        return f"""¡Hola {nombre}! 👋

Soy Eki, tu asistente educativo inteligente. Puedo ayudarte con:

📊 **Consultar tu progreso**
📝 **Ver tus tareas pendientes**
🎯 **Recomendaciones de estudio**
💬 **Responder tus dudas**

¿En qué puedo ayudarte hoy?"""


def responder_con_ia(mensaje: str, telefono: str) -> str:
    """
    Función helper para generar respuesta con IA.
    
    Args:
        mensaje: texto del usuario
        telefono: número del estudiante
        
    Returns:
        Respuesta generada
    """
    try:
        assistant = EkiAIAssistant()
        
        # Si es el primer mensaje o saludo, dar bienvenida
        mensaje_lower = mensaje.lower().strip()
        if any(saludo in mensaje_lower for saludo in ['hola', 'holi', 'hey', 'buenos', 'buenas']):
            try:
                estudiante = Estudiante.objects.get(telefono=telefono)
                # Si es la primera interacción, bienvenida completa
                if WhatsappLog.objects.filter(telefono=telefono).count() <= 1:
                    return assistant.respuesta_bienvenida(estudiante.nombre)
            except Estudiante.DoesNotExist:
                pass
        
        # Generar respuesta con IA
        return assistant.generar_respuesta(mensaje, telefono, incluir_historial=True)
        
    except Exception as e:
        print(f"Error al responder con IA: {str(e)}")
        # Fallback a sistema básico
        from .intent_detector import detect_intent
        from .response_templates import get_response_for_intent
        
        intent = detect_intent(mensaje)
        
        try:
            estudiante = Estudiante.objects.get(telefono=telefono)
            nombre = estudiante.nombre
        except:
            nombre = "Estudiante"
        
        return get_response_for_intent(intent, nombre)
