"""
Módulo de Evaluación Automática con IA
Sistema de evaluación educativa para ejercicios prácticos y retroalimentación
"""

import os
import json
import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

from django.conf import settings
from openai import OpenAI

from .models import (
    EjercicioPractico, RespuestaEjercicio, RubricaEvaluacion,
    Estudiante, Modulo, InteraccionLog
)

logger = logging.getLogger(__name__)


# ========================================
# EVALUACIÓN DE EJERCICIOS NUMÉRICOS
# ========================================

def evaluar_ejercicio_numerico(
    ejercicio: EjercicioPractico,
    respuesta_numerica: Decimal,
    estudiante: Estudiante,
    intento: int = 1
) -> Dict:
    """
    Evalúa un ejercicio numérico comparando la respuesta con la esperada.
    
    Args:
        ejercicio: Instancia del ejercicio
        respuesta_numerica: Respuesta numérica del estudiante
        estudiante: Instancia del estudiante
        intento: Número de intento
    
    Returns:
        Dict con: puntaje, es_correcto, feedback, respuesta_creada
    """
    if not ejercicio.respuesta_numerica_esperada:
        raise ValueError("El ejercicio no tiene respuesta numérica esperada")
    
    esperada = ejercicio.respuesta_numerica_esperada
    tolerancia = ejercicio.tolerancia_porcentual or 5
    
    # Calcular diferencia porcentual
    if esperada != 0:
        diferencia_abs = abs(float(respuesta_numerica) - float(esperada))
        diferencia_pct = (diferencia_abs / abs(float(esperada))) * 100
    else:
        diferencia_pct = 0 if respuesta_numerica == 0 else 100
    
    # Determinar puntaje basado en tolerancia
    if diferencia_pct == 0:
        puntaje = 100
        es_correcto = True
        nivel = "perfecto"
    elif diferencia_pct <= tolerancia:
        puntaje = 100
        es_correcto = True
        nivel = "excelente"
    elif diferencia_pct <= tolerancia * 2:
        puntaje = 80
        es_correcto = True
        nivel = "bueno"
    elif diferencia_pct <= tolerancia * 3:
        puntaje = 60
        es_correcto = False
        nivel = "regular"
    else:
        puntaje = 30
        es_correcto = False
        nivel = "necesita_mejorar"
    
    # Generar feedback
    feedback = _generar_feedback_numerico(
        respuesta_numerica=respuesta_numerica,
        esperada=esperada,
        diferencia_pct=diferencia_pct,
        nivel=nivel,
        formula=ejercicio.formula_evaluacion,
        intento=intento
    )
    
    # Guardar respuesta
    respuesta = RespuestaEjercicio.objects.create(
        ejercicio=ejercicio,
        estudiante=estudiante,
        intento=intento,
        respuesta_numerica=respuesta_numerica,
        puntaje_obtenido=puntaje,
        es_correcto=es_correcto,
        feedback_ia=feedback,
        evaluado_por_ia=True,
        modalidad='texto'
    )
    
    # Registrar en InteraccionLog
    InteraccionLog.objects.create(
        estudiante=estudiante,
        curso=ejercicio.modulo.curso if ejercicio.modulo else None,
        modulo=ejercicio.modulo,
        tipo='ejercicio',
        modalidad='texto',
        puntaje=puntaje,
        es_correcto=es_correcto,
        respuesta_raw=str(respuesta_numerica),
        feedback_generado=feedback,
        municipio=estudiante.municipio,
        # Eliminado departamento
    )
    
    return {
        'puntaje': puntaje,
        'es_correcto': es_correcto,
        'feedback': feedback,
        'respuesta': respuesta,
        'diferencia_porcentual': round(diferencia_pct, 2)
    }


def _generar_feedback_numerico(
    respuesta_numerica: Decimal,
    esperada: Decimal,
    diferencia_pct: float,
    nivel: str,
    formula: str,
    intento: int
) -> str:
    """Genera feedback para ejercicio numérico"""
    
    if nivel == "perfecto":
        return f"""✅ ¡Perfecto! Tu respuesta ${respuesta_numerica:,.0f} es exactamente correcta.

¡Excelente trabajo! Dominas este concepto."""
    
    elif nivel == "excelente":
        return f"""✅ ¡Muy bien! Tu respuesta ${respuesta_numerica:,.0f} es correcta.

La respuesta esperada era ${esperada:,.0f}, y tu cálculo está dentro del margen aceptable (diferencia: {diferencia_pct:.1f}%)."""
    
    elif nivel == "bueno":
        return f"""👍 Bien hecho. Tu respuesta ${respuesta_numerica:,.0f} es aceptable.

La respuesta esperada era ${esperada:,.0f}. Tu cálculo tiene una pequeña diferencia ({diferencia_pct:.1f}%), pero demuestra que comprendes el concepto.

💡 Tip: Revisa los decimales y redondeos en tu cálculo."""
    
    elif nivel == "regular":
        return f"""⚠️ Tu respuesta ${respuesta_numerica:,.0f} necesita ajustes.

La respuesta esperada era ${esperada:,.0f}. Hay una diferencia del {diferencia_pct:.1f}%.

💡 Recuerda la fórmula: {formula or 'revisa el procedimiento'}

¿Quieres intentarlo de nuevo?"""
    
    else:  # necesita_mejorar
        if intento == 1:
            return f"""❌ Tu respuesta ${respuesta_numerica:,.0f} no es correcta.

La respuesta esperada era ${esperada:,.0f} (diferencia: {diferencia_pct:.1f}%).

💡 Revisa estos pasos:
1. {formula or 'Identifica los datos del problema'}
2. Aplica la fórmula correcta
3. Verifica tu operación

¡No te desanimes! Intenta de nuevo. 💪"""
        else:
            return f"""❌ Tu respuesta ${respuesta_numerica:,.0f} aún no es correcta.

La respuesta esperada era ${esperada:,.0f}.

💡 Ejemplo paso a paso:
{formula or 'Consulta el material del módulo'}

Si necesitas ayuda adicional, escribe "AYUDA" para conectar con un tutor. 🤝"""


# ========================================
# EVALUACIÓN DE RESPUESTAS ABIERTAS
# ========================================

def evaluar_respuesta_abierta(
    ejercicio: EjercicioPractico,
    respuesta_texto: str,
    estudiante: Estudiante,
    intento: int = 1,
    modalidad: str = 'texto'
) -> Dict:
    """
    Evalúa una respuesta abierta usando LLM y rúbrica.
    
    Args:
        ejercicio: Instancia del ejercicio
        respuesta_texto: Respuesta del estudiante
        estudiante: Instancia del estudiante
        intento: Número de intento
        modalidad: texto, audio o mixto
    
    Returns:
        Dict con: puntaje, es_correcto, feedback, respuesta_creada
    """
    if not ejercicio.rubrica:
        raise ValueError("El ejercicio no tiene rúbrica asociada")
    
    rubrica = ejercicio.rubrica
    
    # Evaluar con LLM
    resultado_evaluacion = _evaluar_con_llm(
        enunciado=ejercicio.enunciado,
        contexto=ejercicio.contexto_previo,
        respuesta=respuesta_texto,
        rubrica=rubrica,
        palabras_clave=rubrica.palabras_clave
    )
    
    puntaje = resultado_evaluacion['puntaje']
    es_correcto = puntaje >= 70  # Umbral de aprobación
    feedback = resultado_evaluacion['feedback']
    
    # Guardar respuesta
    respuesta = RespuestaEjercicio.objects.create(
        ejercicio=ejercicio,
        estudiante=estudiante,
        intento=intento,
        respuesta_texto=respuesta_texto,
        puntaje_obtenido=puntaje,
        es_correcto=es_correcto,
        feedback_ia=feedback,
        evaluado_por_ia=True,
        modalidad=modalidad
    )
    
    # Registrar en InteraccionLog
    InteraccionLog.objects.create(
        estudiante=estudiante,
        curso=ejercicio.modulo.curso if ejercicio.modulo else None,
        modulo=ejercicio.modulo,
        tipo='ejercicio',
        modalidad=modalidad,
        puntaje=puntaje,
        es_correcto=es_correcto,
        respuesta_raw=respuesta_texto[:500],  # Limitar tamaño
        feedback_generado=feedback,
        municipio=estudiante.municipio,
        departamento=estudiante.departamento
    )
    
    return {
        'puntaje': puntaje,
        'es_correcto': es_correcto,
        'feedback': feedback,
        'respuesta': respuesta,
        'criterios_evaluados': resultado_evaluacion.get('criterios', {})
    }


def _evaluar_con_llm(
    enunciado: str,
    contexto: str,
    respuesta: str,
    rubrica: RubricaEvaluacion,
    palabras_clave: str
) -> Dict:
    """Evalúa respuesta abierta usando OpenAI"""
    
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    except Exception:
        logger.error("No se pudo inicializar cliente OpenAI")
        return {
            'puntaje': 50,
            'feedback': "⚠️ Error en evaluación automática. Tu respuesta será revisada manualmente.",
            'criterios': {}
        }
    
    # Construir prompt de evaluación
    criterios_str = json.dumps(rubrica.criterios, indent=2, ensure_ascii=False) if rubrica.criterios else "No especificados"
    
    prompt = f"""Eres un tutor experto que evalúa respuestas de estudiantes rurales de manera constructiva y empática.

**EJERCICIO:**
{enunciado}

{f"**CONTEXTO:** {contexto}" if contexto else ""}

**RESPUESTA DEL ESTUDIANTE:**
{respuesta}

**RÚBRICA DE EVALUACIÓN:**
{criterios_str}

**PALABRAS CLAVE ESPERADAS:**
{palabras_clave or "No especificadas"}

**INSTRUCCIONES:**
1. Evalúa la respuesta según la rúbrica
2. Asigna un puntaje de 0 a 100
3. Genera feedback constructivo y específico
4. Reconoce aciertos y sugiere mejoras concretas
5. Usa lenguaje cercano y motivador

Responde en formato JSON:
{{
  "puntaje": 85,
  "nivel": "bueno",
  "aciertos": ["Punto fuerte 1", "Punto fuerte 2"],
  "mejoras": ["Aspecto a mejorar 1"],
  "feedback": "Retroalimentación completa para el estudiante"
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un tutor educativo empático y constructivo. Respondes SOLO con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        contenido = response.choices[0].message.content.strip()
        
        # Limpiar markdown si existe
        if contenido.startswith('```'):
            contenido = contenido.replace('```json', '').replace('```', '').strip()
        
        resultado = json.loads(contenido)
        
        return {
            'puntaje': resultado.get('puntaje', 50),
            'feedback': resultado.get('feedback', 'Tu respuesta ha sido evaluada.'),
            'criterios': {
                'nivel': resultado.get('nivel', 'regular'),
                'aciertos': resultado.get('aciertos', []),
                'mejoras': resultado.get('mejoras', [])
            }
        }
    
    except Exception as e:
        logger.error(f"Error en evaluación LLM: {e}")
        return {
            'puntaje': 50,
            'feedback': "⚠️ Error en evaluación automática. Tu respuesta será revisada manualmente.",
            'criterios': {}
        }


# ========================================
# GENERACIÓN DE RETOS HIPOTÉTICOS
# ========================================

def generar_reto_hipotetico(
    modulo: Modulo,
    estudiante: Estudiante
) -> str:
    """
    Genera una situación hipotética basada en el contenido del módulo.
    
    Args:
        modulo: Módulo recién completado
        estudiante: Estudiante que completó el módulo
    
    Returns:
        str: Texto del reto hipotético
    """
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    except Exception:
        return _reto_fallback(modulo)
    
    contenido_modulo = f"{modulo.titulo}\n\n{modulo.descripcion}\n\n{modulo.contenido[:2000]}"
    
    prompt = f"""Eres un tutor creativo que diseña situaciones prácticas para estudiantes rurales.

**CONTENIDO DEL MÓDULO:**
{contenido_modulo}

**TAREA:**
Crea una situación hipotética práctica donde el estudiante {estudiante.nombre} debe aplicar lo aprendido.

REQUISITOS:
- Situación realista y relevante para contexto rural
- Debe requerir aplicar conceptos del módulo
- Longitud: 2-3 párrafos
- Termina con una pregunta abierta
- Usa lenguaje cercano y motivador

Ejemplo: "Imagina que en tu finca de café, notas que las plantas tienen manchas en las hojas..."

Responde SOLO con el texto de la situación (sin JSON, sin títulos)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un tutor experto en educación rural práctica."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=300
        )
        
        reto = response.choices[0].message.content.strip()
        logger.info(f"Reto generado para módulo {modulo.id}")
        return reto
    
    except Exception as e:
        logger.error(f"Error generando reto: {e}")
        return _reto_fallback(modulo)


def _reto_fallback(modulo: Modulo) -> str:
    """Reto genérico si falla la generación con IA"""
    return f"""💡 **Reto Práctico**

Ahora que completaste el módulo "{modulo.titulo}", piensa en una situación real de tu día a día donde podrías aplicar lo aprendido.

📝 Descríbeme:
- ¿Qué situación es?
- ¿Cómo aplicarías los conceptos del módulo?
- ¿Qué resultados esperas?

¡Comparte tu respuesta! 🌱"""


# ========================================
# PREGUNTAS DE COMPRENSIÓN
# ========================================

def generar_pregunta_comprension(modulo: Modulo) -> str:
    """
    Genera una pregunta simple de comprensión para validar entendimiento.
    
    Args:
        modulo: Módulo a evaluar
    
    Returns:
        str: Pregunta de comprensión
    """
    preguntas_genericas = [
        f"¿Entendiste los conceptos principales del módulo '{modulo.titulo}'?",
        f"¿Te quedó claro el contenido sobre {modulo.titulo}?",
        f"¿Lograste comprender los temas tratados en este módulo?",
    ]
    
    import random
    return random.choice(preguntas_genericas)


# ========================================
# FUNCIONES AUXILIARES
# ========================================

def registrar_interaccion_comprension(
    estudiante: Estudiante,
    modulo: Modulo,
    respuesta: str,
    entendio: bool
):
    """Registra respuesta a pregunta de comprensión"""
    InteraccionLog.objects.create(
        estudiante=estudiante,
        curso=modulo.curso,
        modulo=modulo,
        tipo='comprension',
        modalidad='texto',
        puntaje=100 if entendio else 0,
        es_correcto=entendio,
        respuesta_raw=respuesta,
        feedback_generado="¡Excelente!" if entendio else "Te ayudaré con lo que no entendiste",
        municipio=estudiante.municipio,
        departamento=estudiante.departamento
    )
