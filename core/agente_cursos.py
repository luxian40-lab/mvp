"""
🤖 Sistema de Agentes IA que Aprenden de Cursos
- Los agentes leen y aprenden del contenido de los cursos
- Generan respuestas contextualizadas basadas en el material educativo
- Mejoran la calidad de las respuestas con conocimiento específico del dominio
"""

import os
import logging
from django.conf import settings
from .models import Curso, Modulo, Leccion, Estudiante
from openai import OpenAI

logger = logging.getLogger(__name__)


class AgenteAprendizajeCursos:
    """Agente que aprende del contenido de los cursos para dar respuestas contextualizadas"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.modelo = "gpt-4o-mini"  # Modelo eficiente para contexto
        
    def obtener_contexto_curso(self, curso_id):
        """
        Extrae el contenido completo de un curso para que el agente aprenda
        
        Args:
            curso_id: ID del curso
            
        Returns:
            str: Contexto completo del curso
        """
        try:
            curso = Curso.objects.get(id=curso_id)
            contexto = f"# CURSO: {curso.nombre}\n\n"
            contexto += f"Descripción: {curso.descripcion}\n\n"
            
            # Obtener todos los módulos y lecciones
            modulos = Modulo.objects.filter(curso=curso).order_by('orden')
            
            for modulo in modulos:
                contexto += f"## MÓDULO {modulo.orden}: {modulo.nombre}\n"
                contexto += f"{modulo.descripcion}\n\n"
                
                lecciones = Leccion.objects.filter(modulo=modulo).order_by('orden')
                
                for leccion in lecciones:
                    contexto += f"### Lección {leccion.orden}: {leccion.titulo}\n"
                    contexto += f"{leccion.contenido}\n\n"
                    
                    # Si hay ejercicios, incluirlos
                    if hasattr(leccion, 'ejercicios'):
                        ejercicios = leccion.ejercicios.all()
                        if ejercicios:
                            contexto += "**Ejercicios de práctica:**\n"
                            for ej in ejercicios:
                                contexto += f"- {ej.pregunta}\n"
                            contexto += "\n"
            
            logger.info(f"✅ Contexto extraído del curso {curso.nombre}: {len(contexto)} caracteres")
            return contexto
            
        except Curso.DoesNotExist:
            logger.error(f"❌ Curso {curso_id} no encontrado")
            return ""
        except Exception as e:
            logger.error(f"❌ Error extrayendo contexto del curso: {e}")
            return ""
    
    def generar_respuesta_contextualizada(self, estudiante, pregunta, curso_actual=None):
        """
        Genera una respuesta usando el conocimiento del curso actual del estudiante
        
        Args:
            estudiante: Objeto Estudiante
            pregunta: str, pregunta del estudiante
            curso_actual: Curso opcional, si no se provee usa el progreso del estudiante
            
        Returns:
            str: Respuesta contextualizada
        """
        try:
            # Determinar el curso relevante
            if not curso_actual:
                # Buscar el curso en el que el estudiante tiene progreso
                from .models import ProgresoEstudiante
                progreso = ProgresoEstudiante.objects.filter(
                    estudiante=estudiante,
                    completado=False
                ).select_related('curso').first()
                
                if progreso:
                    curso_actual = progreso.curso
                else:
                    # No hay curso activo, respuesta genérica
                    return self._respuesta_sin_contexto(pregunta)
            
            # Obtener contexto del curso
            contexto_curso = self.obtener_contexto_curso(curso_actual.id)
            
            if not contexto_curso:
                return self._respuesta_sin_contexto(pregunta)
            
            # Crear prompt con contexto del curso
            system_prompt = f"""Eres un asistente educativo especializado en agricultura y desarrollo rural.
            
Tu rol es ayudar a estudiantes que están aprendiendo sobre {curso_actual.nombre}.

IMPORTANTE:
- Responde SOLO basándote en el contenido del curso proporcionado
- Si la pregunta no está relacionada con el curso, di que solo puedes ayudar con temas del curso
- Usa lenguaje simple y claro, apropiado para campesinos y agricultores
- Sé amigable y motivador
- Respuestas cortas (máximo 300 palabras)

CONTENIDO DEL CURSO:
{contexto_curso[:8000]}  # Limitar a ~8000 caracteres para no exceder tokens
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ]
            
            response = self.client.chat.completions.create(
                model=self.modelo,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            respuesta = response.choices[0].message.content.strip()
            logger.info(f"✅ Respuesta generada con contexto de '{curso_actual.nombre}'")
            
            return respuesta
            
        except Exception as e:
            logger.error(f"❌ Error generando respuesta contextualizada: {e}")
            return self._respuesta_sin_contexto(pregunta)
    
    def _respuesta_sin_contexto(self, pregunta):
        """Respuesta genérica cuando no hay contexto disponible"""
        try:
            response = self.client.chat.completions.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": "Eres un asistente educativo amigable para agricultores. Responde de forma breve y clara."},
                    {"role": "user", "content": pregunta}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ Error en respuesta sin contexto: {e}")
            return "Lo siento, no puedo responder en este momento. ¿Puedes intentar de nuevo más tarde?"
    
    def obtener_consejo_personalizado(self, estudiante):
        """
        Genera un consejo personalizado basado en el progreso del estudiante
        
        Args:
            estudiante: Objeto Estudiante
            
        Returns:
            str: Consejo personalizado
        """
        try:
            from .models import ProgresoEstudiante
            
            # Obtener progreso actual
            progresos = ProgresoEstudiante.objects.filter(
                estudiante=estudiante
            ).select_related('curso', 'leccion_actual')
            
            if not progresos:
                return "¡Hola! Te invito a comenzar un curso para aprender sobre agricultura 🌱"
            
            contexto_progreso = "Progreso del estudiante:\n"
            for prog in progresos:
                porcentaje = int(prog.porcentaje_completado)
                contexto_progreso += f"- {prog.curso.nombre}: {porcentaje}% completado"
                if prog.leccion_actual:
                    contexto_progreso += f" (Última lección: {prog.leccion_actual.titulo})"
                contexto_progreso += "\n"
            
            # Generar consejo personalizado
            response = self.client.chat.completions.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": f"""Eres un mentor educativo para agricultores.
                    
Genera un consejo breve, motivador y personalizado basado en el progreso del estudiante.

{contexto_progreso}

El consejo debe:
- Ser motivador y positivo
- Sugerir el próximo paso en su aprendizaje
- Ser específico al curso que está tomando
- Máximo 2-3 oraciones"""},
                    {"role": "user", "content": "Dame un consejo personalizado"}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Error generando consejo personalizado: {e}")
            return "¡Sigue adelante con tu aprendizaje! 💪🌱"


# Instancia global del agente
agente_cursos = AgenteAprendizajeCursos()
