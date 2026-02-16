"""
Sistema de Tutor Interactivo con IA
Genera retroalimentación personalizada, retos y preguntas basadas en el contenido del curso
"""
import logging
import random
from typing import Dict, List, Optional, Tuple
from .models import Estudiante, Modulo, ModuloCompletado
from .base_conocimientos import BaseConocimientos

logger = logging.getLogger(__name__)


class TutorInteractivo:
    """
    Tutor que genera preguntas, retos y retroalimentación basada en el contenido del módulo
    """
    
    @classmethod
    def generar_pregunta_modulo(cls, modulo: Modulo, dificultad: str = 'media') -> Dict:
        """
        Genera una pregunta de comprensión basada en el contenido del módulo
        
        Args:
            modulo: Módulo del que generar la pregunta
            dificultad: 'facil', 'media', 'dificil'
            
        Returns:
            Dict con pregunta, opciones y respuesta correcta
        """
        contenido = modulo.contenido
        titulo = modulo.titulo
        
        # Extraer conceptos clave del contenido
        conceptos = cls._extraer_conceptos_clave(contenido)
        
        if not conceptos:
            # Pregunta genérica si no hay conceptos
            return {
                'pregunta': f"¿Cuál es el tema principal del módulo '{titulo}'?",
                'opciones': [
                    titulo,
                    "Otro tema diferente",
                    "No estoy seguro",
                    "Necesito repasar"
                ],
                'respuesta_correcta': 0,
                'explicacion': f"El módulo trata específicamente sobre: {titulo}"
            }
        
        # Generar pregunta basada en conceptos
        concepto = random.choice(conceptos)
        
        preguntas_templates = [
            {
                'pregunta': f"Según el módulo, ¿qué es importante saber sobre {concepto}?",
                'tipo': 'comprension'
            },
            {
                'pregunta': f"¿Cuál de estas afirmaciones sobre {concepto} es correcta?",
                'tipo': 'verificacion'
            },
            {
                'pregunta': f"En el contexto de {titulo}, ¿cómo se relaciona {concepto}?",
                'tipo': 'relacion'
            }
        ]
        
        template = random.choice(preguntas_templates)
        
        # Buscar información del concepto en el contenido
        info_concepto = cls._extraer_info_concepto(contenido, concepto)
        
        return {
            'pregunta': template['pregunta'],
            'opciones': cls._generar_opciones(info_concepto, concepto),
            'respuesta_correcta': 0,  # Primera opción siempre correcta
            'explicacion': info_concepto[:200] + "..." if len(info_concepto) > 200 else info_concepto,
            'concepto_clave': concepto
        }
    
    @classmethod
    def generar_reto_practico(cls, modulo: Modulo) -> Dict:
        """
        Genera un reto práctico basado en el módulo
        
        Returns:
            Dict con reto y criterios de evaluación
        """
        titulo = modulo.titulo
        contenido = modulo.contenido
        
        # Extraer verbos de acción del contenido
        verbos_agricultura = [
            'siembra', 'prepara', 'aplica', 'riega', 'poda',
            'fertiliza', 'controla', 'cosecha', 'almacena', 'comercializa'
        ]
        
        verbo_encontrado = None
        for verbo in verbos_agricultura:
            if verbo in contenido.lower():
                verbo_encontrado = verbo
                break
        
        if verbo_encontrado:
            reto = f"""🎯 *RETO PRÁCTICO - {titulo}*

📋 Tarea: Realiza una actividad relacionada con {verbo_encontrado}

✅ Criterios:
1. Aplica lo aprendido en este módulo
2. Documenta tu proceso (puedes enviar foto)
3. Comparte tus resultados

💡 Cuando lo hayas hecho, responde:
   *"completé el reto"* para continuar"""
        else:
            reto = f"""🎯 *RETO PRÁCTICO - {titulo}*

📋 Tarea: Reflexiona sobre lo aprendido

✅ Escribe en 2-3 líneas:
• ¿Qué fue lo más importante que aprendiste?
• ¿Cómo lo aplicarás en tu trabajo?

Responde aquí tu reflexión para continuar"""
        
        return {
            'reto': reto,
            'tipo': 'practico' if verbo_encontrado else 'reflexion',
            'requiere_evidencia': bool(verbo_encontrado)
        }
    
    @classmethod
    def evaluar_respuesta(cls, respuesta_usuario: str, pregunta_data: Dict) -> Tuple[bool, str]:
        """
        Evalúa la respuesta del usuario y genera feedback
        
        Args:
            respuesta_usuario: respuesta del estudiante
            pregunta_data: datos de la pregunta original
            
        Returns:
            Tuple (es_correcta, mensaje_feedback)
        """
        respuesta_clean = respuesta_usuario.strip().lower()
        
        # Verificar si es un número de opción
        if respuesta_clean.isdigit():
            opcion_num = int(respuesta_clean) - 1  # Usuario escribe 1-4, internamente 0-3
            es_correcta = (opcion_num == pregunta_data['respuesta_correcta'])
        else:
            # Verificar si la respuesta contiene palabras clave
            opcion_correcta = pregunta_data['opciones'][pregunta_data['respuesta_correcta']]
            palabras_clave = opcion_correcta.lower().split()
            es_correcta = any(palabra in respuesta_clean for palabra in palabras_clave if len(palabra) > 3)
        
        if es_correcta:
            feedbacks_positivos = [
                f"🎉 *¡Excelente!* Tu respuesta es correcta.\n\n💡 {pregunta_data['explicacion']}",
                f"✅ *¡Muy bien!* Has comprendido el concepto.\n\n📚 {pregunta_data['explicacion']}",
                f"👏 *¡Correcto!* Demuestras buen entendimiento.\n\n🌱 {pregunta_data['explicacion']}",
            ]
            return True, random.choice(feedbacks_positivos)
        else:
            feedbacks_correctivos = [
                f"🤔 No exactamente. La respuesta correcta es:\n\n✅ {pregunta_data['opciones'][pregunta_data['respuesta_correcta']]}\n\n💡 {pregunta_data['explicacion']}\n\n📖 *Tip:* Repasa el módulo para reforzar este concepto.",
                f"📝 Casi, pero hay un detalle. Mira:\n\n✅ {pregunta_data['opciones'][pregunta_data['respuesta_correcta']]}\n\n🌱 {pregunta_data['explicacion']}\n\n💪 ¡Sigue así, estás aprendiendo!",
                f"❌ Incorrecto esta vez, pero así se aprende:\n\n✅ {pregunta_data['opciones'][pregunta_data['respuesta_correcta']]}\n\n📚 {pregunta_data['explicacion']}\n\n🎯 Intenta recordar esto para el siguiente módulo.",
            ]
            return False, random.choice(feedbacks_correctivos)
    
    @classmethod
    def generar_resumen_modulo(cls, modulo: Modulo) -> str:
        """
        Genera un resumen pedagógico del módulo
        """
        contenido = modulo.contenido
        conceptos = cls._extraer_conceptos_clave(contenido)
        
        resumen = f"""📖 *RESUMEN - {modulo.titulo}*

🎯 *Conceptos clave:*
"""
        for i, concepto in enumerate(conceptos[:5], 1):
            resumen += f"{i}. {concepto.title()}\n"
        
        resumen += f"""
📝 *Lo que aprendiste:*
{contenido[:300]}...

💡 *Para recordar:*
Este módulo es fundamental para tu desarrollo en el cultivo. Asegúrate de comprender bien estos conceptos antes de continuar."""
        
        return resumen
    
    @classmethod
    def _extraer_conceptos_clave(cls, contenido: str) -> List[str]:
        """
        Extrae conceptos clave del contenido
        """
        # Palabras clave agrícolas
        conceptos_agricultura = [
            'siembra', 'cosecha', 'fertilización', 'riego', 'poda',
            'control de plagas', 'suelo', 'semillas', 'nutrientes',
            'abono orgánico', 'compost', 'ph del suelo', 'drenaje',
            'rotación de cultivos', 'intercalado', 'asociación de cultivos',
            'clima', 'temperatura', 'humedad', 'precipitación',
            'variedades', 'híbridos', 'propagación', 'injerto',
            'costos de producción', 'mercado', 'comercialización',
            'buenas prácticas agrícolas', 'agricultura sostenible'
        ]
        
        contenido_lower = contenido.lower()
        conceptos_encontrados = []
        
        for concepto in conceptos_agricultura:
            if concepto in contenido_lower:
                conceptos_encontrados.append(concepto)
        
        return conceptos_encontrados[:8]  # Máximo 8 conceptos
    
    @classmethod
    def _extraer_info_concepto(cls, contenido: str, concepto: str) -> str:
        """
        Extrae información específica sobre un concepto del contenido
        """
        # Buscar el párrafo donde aparece el concepto
        lineas = contenido.split('\n')
        for i, linea in enumerate(lineas):
            if concepto.lower() in linea.lower():
                # Obtener contexto (línea actual + 2 siguientes)
                contexto = ' '.join(lineas[i:min(i+3, len(lineas))])
                return contexto.strip()
        
        return f"El {concepto} es un aspecto importante de este módulo."
    
    @classmethod
    def _generar_opciones(cls, info_correcta: str, concepto: str) -> List[str]:
        """
        Genera opciones de respuesta (primera es correcta)
        """
        opciones = [info_correcta[:100]]  # Opción correcta resumida
        
        # Opciones distractoras genéricas
        distractoras = [
            f"No es relevante para el cultivo de {concepto}",
            f"Debe evitarse completamente en el proceso de {concepto}",
            f"Solo se aplica en condiciones especiales de {concepto}",
            f"Es un método antiguo que ya no se usa para {concepto}"
        ]
        
        opciones.extend(random.sample(distractoras, 3))
        random.shuffle(opciones[1:])  # Mezclar solo las distractoras
        
        return opciones


# Funciones auxiliares
def generar_pregunta_para_modulo(modulo_id: int) -> Optional[Dict]:
    """
    Genera una pregunta para un módulo específico
    """
    try:
        modulo = Modulo.objects.get(id=modulo_id)
        return TutorInteractivo.generar_pregunta_modulo(modulo)
    except Modulo.DoesNotExist:
        logger.error(f"Módulo {modulo_id} no encontrado")
        return None


def evaluar_respuesta_estudiante(respuesta: str, pregunta_data: Dict) -> Tuple[bool, str]:
    """
    Evalúa la respuesta de un estudiante
    """
    return TutorInteractivo.evaluar_respuesta(respuesta, pregunta_data)
