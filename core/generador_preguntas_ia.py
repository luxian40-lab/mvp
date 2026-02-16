"""
Generador de Preguntas con IA para cualquier módulo
Lee el contenido del módulo y genera preguntas genéricas
"""

import os
import logging
from openai import OpenAI
from core.models import Modulo

logger = logging.getLogger(__name__)

class GeneradorPreguntasIA:
    """
    Genera preguntas automáticamente basándose en el contenido de cualquier módulo.
    """
    def __init__(self, modelo: str = 'gpt-4o-mini'):
        self.modelo = modelo
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def generar_preguntas_desde_modulo(self, modulo_id, cantidad: int = 5):
        """
        Genera preguntas analizando el contenido del módulo.
        Args:
            modulo_id: ID del módulo (int)
            cantidad: Número de preguntas a generar
        Returns:
            Lista de preguntas generadas (str)
        """
        try:
            modulo = Modulo.objects.get(id=modulo_id)
        except Modulo.DoesNotExist:
            logger.error(f"❌ Módulo {modulo_id} no encontrado")
            return []

        prompt = f"""
Eres un generador de preguntas educativas. Lee el siguiente contenido y genera {cantidad} preguntas variadas (abiertas, opción múltiple o verdadero/falso) para evaluar la comprensión del estudiante. Las preguntas deben ser claras, breves y en español. No incluyas las respuestas.

CONTENIDO DEL MÓDULO:
{modulo.contenido[:4000]}
"""
        messages = [
            {"role": "system", "content": "Eres un generador de preguntas educativas en español."},
            {"role": "user", "content": prompt}
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.modelo,
                messages=messages,
                max_tokens=600,
                temperature=0.7
            )
            texto = response.choices[0].message.content.strip()
            preguntas = [p.strip('- ').strip() for p in texto.split('\n') if p.strip()]
            logger.info(f"✅ Generadas {len(preguntas)} preguntas para módulo '{modulo.titulo}'")
            return preguntas
        except Exception as e:
            logger.error(f"❌ Error generando preguntas IA: {e}")
            return []

# Ejemplo de uso:
# generador = GeneradorPreguntasIA()
# preguntas = generador.generar_preguntas_desde_modulo(modulo_id=1, cantidad=5)
# print(preguntas)
