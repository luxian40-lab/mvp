"""
Generador Automático de Ejercicios con IA
Lee el contenido del curso y genera ejercicios personalizados
"""

import os
import json
import logging
from typing import Dict, List, Optional
from decimal import Decimal


import openai

logger = logging.getLogger(__name__)


class GeneradorEjerciciosIA:
    """
    Genera ejercicios automáticamente basándose en el contenido del curso.
    Soporta OpenAI (GPT-4) y Anthropic (Claude).
    """
    
    def __init__(self, modelo: str = 'gpt-4o-mini'):
        """
        Args:
            modelo: 'gpt-4o-mini', 'gpt-3.5-turbo', 'claude-3-sonnet', 'claude-3-opus'
        """
        self.modelo = modelo
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if modelo.startswith('gpt') and not self.openai_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        elif modelo.startswith('claude'):
            if not ANTHROPIC_DISPONIBLE:
                raise ValueError("Anthropic no instalado. Instala con: pip install anthropic")
            if not self.anthropic_key:
                raise ValueError("ANTHROPIC_API_KEY no configurada")
    
    def generar_ejercicios_desde_curso(
        self,
        curso,
        cantidad: int = 5,
        tipo_ejercicios: str = 'mixto'  # 'numerico', 'abierto', 'mixto'
    ) -> List[Dict]:
        """
        Genera ejercicios automáticamente analizando el contenido del curso.
        
        Args:
            curso: Instancia del modelo Curso
            cantidad: Número de ejercicios a generar
            tipo_ejercicios: 'numerico', 'abierto', 'mixto'
            
        Returns:
            Lista de dicts con datos de ejercicios generados
        """
        
        # 1. Recopilar contenido del curso
        contenido_curso = self._extraer_contenido_curso(curso)
        
        # 2. Generar prompt para IA
        prompt = self._construir_prompt(contenido_curso, cantidad, tipo_ejercicios)
        
        # 3. Llamar a IA
        respuesta = self._llamar_ia(prompt)
        
        # 4. Parsear y validar ejercicios
        ejercicios = self._parsear_ejercicios(respuesta, curso)
        
        logger.info(f"✅ Generados {len(ejercicios)} ejercicios para curso '{curso.nombre}'")
        return ejercicios
    
    def _extraer_contenido_curso(self, curso) -> Dict:
        """Extrae todo el contenido relevante del curso"""
        
        from core.models import Modulo
        
        modulos = Modulo.objects.filter(curso=curso).order_by('numero')
        
        contenido = {
            'nombre_curso': curso.nombre,
            'descripcion': getattr(curso, 'descripcion', ''),
            'modulos': []
        }
        
        for modulo in modulos:
            contenido['modulos'].append({
                'numero': modulo.numero,
                'titulo': modulo.titulo,
                'descripcion': modulo.descripcion,
                'contenido': modulo.contenido
            })
        
        return contenido
    
    def _construir_prompt(
        self,
        contenido: Dict,
        cantidad: int,
        tipo_ejercicios: str
    ) -> str:
        """Construye el prompt para la IA"""
        
        # Formatear módulos
        modulos_texto = ""
        for mod in contenido['modulos']:
            modulos_texto += f"""
## Módulo {mod['numero']}: {mod['titulo']}

**Descripción:** {mod['descripcion']}

**Contenido:**
{mod['contenido']}

---
"""
        
        prompt = f"""Eres un experto en educación rural y finanzas para emprendedores agrícolas en Colombia.

Analiza el siguiente curso y genera {cantidad} ejercicios prácticos y realistas para estudiantes rurales colombianos.

# CURSO: {contenido['nombre_curso']}

**Descripción:** {contenido['descripcion']}

{modulos_texto}

# INSTRUCCIONES:

Genera {cantidad} ejercicios que:
1. Sean **relevantes** al contenido del curso
2. Usen **contextos rurales colombianos** (cultivos, fincas, ventas locales)
3. Sean **prácticos** y aplicables a la vida real
4. Tengan **números realistas** (precios, cantidades típicas de Colombia rural)

Tipos de ejercicios a generar:
- Si tipo='{tipo_ejercicios}':
  - **numerico**: Ejercicios con respuesta numérica (cálculos, operaciones)
  - **abierto**: Preguntas de reflexión o aplicación de conceptos
  - **mixto**: Combina ambos tipos

# FORMATO DE RESPUESTA (JSON):

```json
{{
  "ejercicios": [
    {{
      "tipo": "numerico",  // o "abierto"
      "titulo": "Título corto del ejercicio",
      "enunciado": "Enunciado completo con contexto rural colombiano. Incluye 📊 emojis relevantes.",
      "respuesta_esperada": 125000,  // Solo para numéricos (número sin comas)
      "tolerancia_porcentaje": 5,  // Solo para numéricos (2-10)
      "respuesta_explicacion": "Explicación paso a paso de la solución",
      "rubrica_criterios": {{  // Solo para abiertos
        "excelente": {{
          "puntaje": 100,
          "descripcion": "Criterio para máxima calificación"
        }},
        "bueno": {{
          "puntaje": 80,
          "descripcion": "Criterio para buena calificación"
        }},
        "regular": {{
          "puntaje": 60,
          "descripcion": "Criterio para calificación regular"
        }},
        "insuficiente": {{
          "puntaje": 30,
          "descripcion": "Criterio para calificación insuficiente"
        }}
      }},
      "palabras_clave": "palabras, clave, para, evaluacion"  // Solo para abiertos
    }}
  ]
}}
```

**IMPORTANTE:**
- Usa precios realistas para Colombia rural (ej: aguacate $2000-$3000, café $9000-$12000/kg)
- Incluye nombres colombianos (María, Juan, Pedro, Luz, Carlos)
- Menciona cultivos comunes (café, aguacate, plátano, yuca, maíz)
- Para ejercicios numéricos: respuesta_esperada debe ser un NÚMERO (sin comas, sin símbolos)
- Para ejercicios abiertos: incluye rúbrica completa con 4 niveles

Genera exactamente {cantidad} ejercicios ahora:"""
        
        return prompt
    
    def _llamar_ia(self, prompt: str) -> str:
        """Llama a la IA (OpenAI o Claude) y obtiene respuesta"""
        
        if self.modelo.startswith('gpt'):
            return self._llamar_openai(prompt)
        elif self.modelo.startswith('claude'):
            return self._llamar_claude(prompt)
        else:
            raise ValueError(f"Modelo no soportado: {self.modelo}")
    
    def _llamar_openai(self, prompt: str) -> str:
        """Llama a OpenAI GPT"""
        try:
            client = openai.OpenAI(api_key=self.openai_key)
            
            respuesta = client.chat.completions.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": "Eres un experto en educación rural y finanzas para emprendedores agrícolas colombianos. Respondes SOLO en formato JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            return respuesta.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error al llamar OpenAI: {e}")
            raise
    
    def _llamar_claude(self, prompt: str) -> str:
        """Llama a Anthropic Claude"""
        if not ANTHROPIC_DISPONIBLE:
            raise ValueError("Anthropic no instalado")
        
        try:
            client = Anthropic(api_key=self.anthropic_key)
            
            respuesta = client.messages.create(
                model=self.modelo,
                max_tokens=3000,
                temperature=0.7,
                system="Eres un experto en educación rural y finanzas para emprendedores agrícolas colombianos. Respondes SOLO en formato JSON válido.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return respuesta.content[0].text
            
        except Exception as e:
            logger.error(f"Error al llamar Claude: {e}")
            raise
    
    def _parsear_ejercicios(self, respuesta_ia: str, curso) -> List[Dict]:
        """Parsea la respuesta JSON de la IA y valida"""
        
        try:
            # Extraer JSON de la respuesta (puede venir con markdown)
            texto = respuesta_ia.strip()
            
            # Buscar JSON entre ```json y ``` o tomar todo si es JSON directo
            if '```json' in texto:
                inicio = texto.find('```json') + 7
                fin = texto.find('```', inicio)
                texto = texto[inicio:fin]
            elif '```' in texto:
                inicio = texto.find('```') + 3
                fin = texto.find('```', inicio)
                texto = texto[inicio:fin]
            
            datos = json.loads(texto)
            ejercicios = datos.get('ejercicios', [])
            
            # Validar y formatear cada ejercicio
            ejercicios_validos = []
            for ej in ejercicios:
                ejercicio_formateado = self._validar_ejercicio(ej, curso)
                if ejercicio_formateado:
                    ejercicios_validos.append(ejercicio_formateado)
            
            return ejercicios_validos
            
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON: {e}\nRespuesta: {respuesta_ia}")
            raise ValueError(f"La IA no devolvió JSON válido: {e}")
        except Exception as e:
            logger.error(f"Error al procesar ejercicios: {e}")
            raise
    
    def _validar_ejercicio(self, ej: Dict, curso) -> Optional[Dict]:
        """Valida y formatea un ejercicio"""
        
        tipo = ej.get('tipo', 'abierto')
        
        if tipo not in ['numerico', 'abierto']:
            logger.warning(f"Tipo de ejercicio inválido: {tipo}")
            return None
        
        # Datos comunes
        ejercicio = {
            'tipo': tipo,
            'titulo': ej.get('titulo', 'Ejercicio sin título')[:200],
            'enunciado': ej.get('enunciado', 'Sin enunciado'),
        }
        
        # Datos específicos por tipo
        if tipo == 'numerico':
            try:
                respuesta = ej.get('respuesta_esperada')
                
                # Convertir a Decimal
                if isinstance(respuesta, str):
                    # Limpiar comas y símbolos
                    respuesta = respuesta.replace(',', '').replace('$', '').strip()
                
                ejercicio['respuesta_esperada'] = Decimal(str(respuesta))
                ejercicio['tolerancia_porcentaje'] = Decimal(str(ej.get('tolerancia_porcentaje', 5)))
                ejercicio['respuesta_explicacion'] = ej.get('respuesta_explicacion', '')
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error al convertir respuesta numérica: {e}")
                return None
        
        elif tipo == 'abierto':
            rubrica = ej.get('rubrica_criterios', {})
            palabras = ej.get('palabras_clave', '')
            
            if not rubrica:
                logger.warning("Ejercicio abierto sin rúbrica")
                return None
            
            ejercicio['rubrica_criterios'] = rubrica
            ejercicio['palabras_clave'] = palabras
        
        return ejercicio


# ========================================
# FUNCIÓN AUXILIAR PARA USAR EN COMMANDS
# ========================================

def generar_y_guardar_ejercicios(
    curso,
    cantidad: int = 5,
    tipo_ejercicios: str = 'mixto',
    modelo: str = 'gpt-4o-mini',
    modulo=None,
    objetivo=None
) -> int:
    """
    Genera ejercicios con IA y los guarda en la base de datos.
    
    Args:
        curso: Instancia del Curso
        cantidad: Número de ejercicios a generar
        tipo_ejercicios: 'numerico', 'abierto', 'mixto'
        modelo: Modelo de IA a usar
        modulo: Módulo donde guardar (opcional, usa el primero si no se especifica)
        objetivo: Objetivo asociado (opcional)
        
    Returns:
        Número de ejercicios creados
    """
    from core.models import Modulo, ObjetivoCurso, EjercicioPractico, RubricaEvaluacion
    
    # Generar ejercicios
    generador = GeneradorEjerciciosIA(modelo=modelo)
    ejercicios = generador.generar_ejercicios_desde_curso(curso, cantidad, tipo_ejercicios)
    
    # Obtener modulo y objetivo si no se proporcionaron
    if not modulo:
        modulo = Modulo.objects.filter(curso=curso).first()
        if not modulo:
            raise ValueError(f"Curso '{curso.nombre}' no tiene módulos")
    
    if not objetivo:
        objetivo = ObjetivoCurso.objects.filter(curso=curso, tipo='general').first()
        if not objetivo:
            # Crear objetivo genérico
            objetivo = ObjetivoCurso.objects.create(
                curso=curso,
                tipo='general',
                descripcion=f'Comprender y aplicar los conceptos de {curso.nombre}',
                peso_evaluacion=100,
                orden=1
            )
    
    # Guardar ejercicios en BD
    contador = 0
    for ej_data in ejercicios:
        tipo = ej_data['tipo']
        
        # Crear ejercicio
        ejercicio = EjercicioPractico.objects.create(
            modulo=modulo,
            objetivo=objetivo,
            tipo=tipo,
            enunciado=ej_data['enunciado'],
            respuesta_esperada=ej_data.get('respuesta_esperada'),
            tolerancia_porcentaje=ej_data.get('tolerancia_porcentaje', Decimal('5')),
            respuesta_explicacion=ej_data.get('respuesta_explicacion', '')
        )
        
        # Si es abierto, crear rúbrica
        if tipo == 'abierto':
            RubricaEvaluacion.objects.create(
                objetivo=objetivo,
                nombre=f"Rúbrica: {ej_data['titulo'][:50]}",
                criterios=ej_data.get('rubrica_criterios', {}),
                descripcion=f"Evaluación para: {ej_data['titulo']}",
                palabras_clave=ej_data.get('palabras_clave', '')
            )
        
        contador += 1
        logger.info(f"✅ Creado ejercicio: {ej_data['titulo']}")
    
    return contador
