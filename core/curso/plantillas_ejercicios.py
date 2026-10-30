"""
Plantillas de Ejercicios Financieros Predefinidos
Ejercicios listos para usar en cursos de emprendimiento rural
"""

from decimal import Decimal
from typing import Dict, List


# ========================================
# PLANTILLAS DE EJERCICIOS NUMÉRICOS
# ========================================

EJERCICIOS_FINANCIEROS = {
    'calculo_ingresos_basico': {
        'tipo': 'numerico',
        'titulo': 'Cálculo de Ingresos por Ventas',
        'enunciado': """
📊 **Calculemos tus Ingresos**

María tiene una finca donde cultiva aguacates. Esta semana vendió:
- 80 aguacates a $2,500 cada uno

**Pregunta:** ¿Cuánto dinero recibió María por la venta total?

💡 Recuerda: Ingresos = Cantidad × Precio
""",
        'respuesta_esperada': Decimal('200000'),  # 80 × 2,500
        'tolerancia': 2,
        'formula': 'Cantidad vendida × Precio unitario = 80 × $2,500',
        'contexto': 'módulo de ingresos y ventas'
    },
    
    'calculo_costos_basico': {
        'tipo': 'numerico',
        'titulo': 'Cálculo de Costos Totales',
        'enunciado': """
💰 **Suma de Costos**

Pedro está haciendo queso. Sus gastos este mes fueron:
- Leche: $350,000
- Cuajo y sal: $45,000
- Gas para cocinar: $30,000
- Transporte: $75,000

**Pregunta:** ¿Cuál es el costo total de producción?

💡 Recuerda: Suma todos los gastos
""",
        'respuesta_esperada': Decimal('500000'),
        'tolerancia': 3,
        'formula': 'Costo Total = Suma de todos los gastos',
        'contexto': 'módulo de costos de producción'
    },
    
    'calculo_utilidad_basico': {
        'tipo': 'numerico',
        'titulo': 'Cálculo de Utilidad Neta',
        'enunciado': """
💵 **Tu Ganancia Real**

Ana vende arepas en el mercado. Este mes:
- Vendió $850,000 en arepas (Ingresos)
- Gastó $520,000 en maíz, queso y transporte (Costos)

**Pregunta:** ¿Cuál fue la utilidad (ganancia) de Ana?

💡 Recuerda: Utilidad = Ingresos - Costos
""",
        'respuesta_esperada': Decimal('330000'),
        'tolerancia': 5,
        'formula': 'Utilidad = Ingresos ($850,000) - Costos ($520,000)',
        'contexto': 'módulo de utilidad y rentabilidad'
    },
    
    'calculo_ingresos_avanzado': {
        'tipo': 'numerico',
        'titulo': 'Ingresos con Múltiples Productos',
        'enunciado': """
🌽 **Venta de Varios Productos**

Luis vendió en su finca:
- 120 mazorcas de maíz a $1,800 cada una
- 45 kilos de frijol a $4,500 el kilo

**Pregunta:** ¿Cuánto dinero recibió Luis en total?

💡 Calcula cada producto por separado y luego suma
""",
        'respuesta_esperada': Decimal('418500'),  # (120×1800) + (45×4500)
        'tolerancia': 5,
        'formula': '(Mazorcas × Precio) + (Frijol × Precio) = (120×1,800) + (45×4,500)',
        'contexto': 'módulo de ingresos múltiples'
    },
    
    'calculo_utilidad_cafe': {
        'tipo': 'numerico',
        'titulo': 'Utilidad en Cultivo de Café',
        'enunciado': """
☕ **Negocio de Café**

Juan tiene una finca de café. Esta cosecha:

**Ingresos:**
- Vendió 200 kilos de café pergamino a $9,500 el kilo

**Costos:**
- Fertilizante: $480,000
- Mano de obra (recolección): $650,000
- Transporte: $120,000
- Despulpado: $150,000

**Pregunta:** ¿Cuál fue la utilidad de Juan en esta cosecha?

💡 Primero calcula ingresos totales, luego suma los costos, y finalmente resta
""",
        'respuesta_esperada': Decimal('500000'),  # (200×9500) - 1,400,000
        'tolerancia': 7,
        'formula': 'Ingresos (200×9,500) - Costos totales (480k+650k+120k+150k) = 1,900,000 - 1,400,000',
        'contexto': 'módulo de utilidad en agricultura'
    },
    
    'precio_venta_adecuado': {
        'tipo': 'numerico',
        'titulo': 'Definir Precio de Venta',
        'enunciado': """
🏷️ **¿A Qué Precio Vender?**

Sofía hace mermeladas artesanales. Cada frasco le cuesta:
- Frutas: $3,000
- Azúcar y pectin: $1,500
- Frasco y etiqueta: $800
- Energía y gas: $200

Sofía quiere ganar $2,500 por cada frasco.

**Pregunta:** ¿A qué precio debe vender cada frasco de mermelada?

💡 Precio de Venta = Costo Total + Utilidad Deseada
""",
        'respuesta_esperada': Decimal('8000'),  # 5,500 + 2,500
        'tolerancia': 3,
        'formula': 'Suma todos los costos (3k+1.5k+800+200=5,500) y agrega la ganancia (2,500)',
        'contexto': 'módulo de fijación de precios'
    },
    
    'calculo_margen_ganancia': {
        'tipo': 'numerico',
        'titulo': 'Margen de Ganancia Porcentual',
        'enunciado': """
📈 **¿Cuánto Ganas en Porcentaje?**

Carlos compra panela en bloque a $12,000 y la vende a $18,000.

Su ganancia es: $18,000 - $12,000 = $6,000

**Pregunta:** ¿Qué porcentaje de ganancia está obteniendo Carlos sobre el costo?

💡 Fórmula: (Ganancia ÷ Costo) × 100
         ($6,000 ÷ $12,000) × 100

Responde solo el número (sin el símbolo %)
""",
        'respuesta_esperada': Decimal('50'),  # (6000/12000)*100
        'tolerancia': 2,
        'formula': 'Margen = (Ganancia/Costo) × 100 = (6,000/12,000) × 100',
        'contexto': 'módulo de rentabilidad'
    },
    
    'punto_equilibrio': {
        'tipo': 'numerico',
        'titulo': 'Punto de Equilibrio',
        'enunciado': """
⚖️ **¿Cuánto Debo Vender para No Perder?**

Rosa hace empanadas. Sus costos fijos al mes son:
- Arriendo del local: $400,000
- Servicios: $150,000

Cada empanada:
- Costo de hacer una empanada: $1,200
- Precio de venta: $2,500

**Pregunta:** ¿Cuántas empanadas debe vender Rosa al mes para cubrir todos sus gastos (no ganar ni perder)?

💡 Punto de Equilibrio = Costos Fijos ÷ (Precio Venta - Costo Unitario)
                       = 550,000 ÷ (2,500 - 1,200)

Responde solo el número de empanadas (sin decimales)
""",
        'respuesta_esperada': Decimal('423'),  # 550,000 / 1,300
        'tolerancia': 5,
        'formula': 'Costos Fijos (550,000) ÷ Margen por unidad (2,500-1,200=1,300)',
        'contexto': 'módulo de punto de equilibrio'
    },
}


# ========================================
# PLANTILLAS DE PREGUNTAS ABIERTAS
# ========================================

PREGUNTAS_COMPRENSION = {
    'identificar_ingresos': {
        'tipo': 'abierto',
        'titulo': 'Identificación de Ingresos',
        'enunciado': """
💭 **Reflexiona:**

En tu negocio o finca, ¿cuáles son tus principales fuentes de ingresos?

Menciona al menos 2 ejemplos de cómo recibes dinero.
""",
        'palabras_clave': 'venta, ventas, dinero, pago, ingreso, recibo, cobro, cliente',
        'contexto': 'módulo de ingresos'
    },
    
    'identificar_costos': {
        'tipo': 'abierto',
        'titulo': 'Identificación de Costos',
        'enunciado': """
💭 **Piensa en tu negocio:**

¿Cuáles son los gastos más importantes que tienes que pagar para producir o vender?

Menciona al menos 3 costos diferentes.
""",
        'palabras_clave': 'gasto, costo, pagar, comprar, materia, insumo, transporte, salario, arriendo',
        'contexto': 'módulo de costos'
    },
    
    'diferencia_ingreso_utilidad': {
        'tipo': 'abierto',
        'titulo': 'Diferencia entre Ingreso y Utilidad',
        'enunciado': """
💭 **¿Entiendes la diferencia?**

Con tus propias palabras, explica:
¿Qué diferencia hay entre los ingresos y la utilidad de un negocio?

¿Por qué es importante conocer ambos?
""",
        'palabras_clave': 'ingreso, utilidad, ganancia, resta, costo, diferencia, venta, gasto',
        'contexto': 'módulo de utilidad'
    },
    
    'importancia_registros': {
        'tipo': 'abierto',
        'titulo': 'Importancia de Llevar Registros',
        'enunciado': """
💭 **Reflexión:**

¿Por qué crees que es importante anotar (registrar) las ventas y gastos de tu negocio?

¿Qué beneficios trae llevar estos registros?
""",
        'palabras_clave': 'control, saber, conocer, anotar, registrar, cuánto, ganancia, pérdida, decisión',
        'contexto': 'módulo de registros financieros'
    },
}


# ========================================
# RÚBRICAS PREDEFINIDAS
# ========================================

RUBRICAS_FINANCIERAS = {
    'rubrica_conceptos_basicos': {
        'nombre': 'Comprensión Conceptos Financieros Básicos',
        'criterios': {
            'excelente': {
                'puntaje': 100,
                'descripcion': 'Explica correctamente el concepto con ejemplos propios. Demuestra comprensión profunda.'
            },
            'bueno': {
                'puntaje': 80,
                'descripcion': 'Explica el concepto correctamente pero sin ejemplos o con explicación básica.'
            },
            'regular': {
                'puntaje': 60,
                'descripcion': 'Tiene idea del concepto pero con confusiones o explicación incompleta.'
            },
            'insuficiente': {
                'puntaje': 30,
                'descripcion': 'No comprende el concepto o respuesta fuera de contexto.'
            }
        },
        'palabras_clave': 'ingreso, costo, utilidad, ganancia, venta, gasto, resta, suma'
    },
    
    'rubrica_aplicacion_practica': {
        'nombre': 'Aplicación Práctica de Conceptos',
        'criterios': {
            'excelente': {
                'puntaje': 100,
                'descripcion': 'Identifica claramente cómo aplicar el concepto en su contexto real. Ejemplos específicos y relevantes.'
            },
            'bueno': {
                'puntaje': 80,
                'descripcion': 'Menciona aplicaciones prácticas pero sin mucho detalle o contexto.'
            },
            'regular': {
                'puntaje': 60,
                'descripcion': 'Menciona aplicaciones genéricas sin conexión clara con su realidad.'
            },
            'insuficiente': {
                'puntaje': 30,
                'descripcion': 'No identifica aplicaciones prácticas o respuesta irrelevante.'
            }
        },
        'palabras_clave': 'negocio, finca, vender, producir, mejorar, aumentar, calcular'
    },
}


# ========================================
# FUNCIÓN PARA CARGAR PLANTILLAS
# ========================================

def crear_ejercicio_desde_plantilla(
    plantilla_key: str,
    modulo,
    objetivo,
    rubrica=None
) -> Dict:
    """
    Crea un ejercicio a partir de una plantilla predefinida
    
    Args:
        plantilla_key: Clave del diccionario de plantillas
        modulo: Instancia del Modulo
        objetivo: Instancia del ObjetivoCurso
        rubrica: Instancia de RubricaEvaluacion (opcional, para ejercicios abiertos)
    
    Returns:
        Dict con datos del ejercicio creado
    """
    
    # Buscar en ejercicios numéricos
    if plantilla_key in EJERCICIOS_FINANCIEROS:
        plantilla = EJERCICIOS_FINANCIEROS[plantilla_key]
        
        return {
            'modulo': modulo,
            'objetivo': objetivo,
            'tipo': plantilla['tipo'],
            'enunciado': plantilla['enunciado'],
            'respuesta_numerica_esperada': plantilla['respuesta_esperada'],
            'tolerancia_porcentual': plantilla['tolerancia'],
            'formula_evaluacion': plantilla['formula'],
            'contexto_previo': plantilla['contexto'],
            'puntaje_maximo': 100
        }
    
    # Buscar en preguntas abiertas
    elif plantilla_key in PREGUNTAS_COMPRENSION:
        plantilla = PREGUNTAS_COMPRENSION[plantilla_key]
        
        if not rubrica:
            raise ValueError("Se requiere una rúbrica para preguntas abiertas")
        
        return {
            'modulo': modulo,
            'objetivo': objetivo,
            'rubrica': rubrica,
            'tipo': plantilla['tipo'],
            'enunciado': plantilla['enunciado'],
            'contexto_previo': plantilla['contexto'],
            'puntaje_maximo': 100
        }
    
    else:
        raise ValueError(f"Plantilla '{plantilla_key}' no encontrada")


def listar_plantillas_disponibles() -> Dict:
    """Retorna todas las plantillas disponibles organizadas por categoría"""
    return {
        'ejercicios_numericos': list(EJERCICIOS_FINANCIEROS.keys()),
        'preguntas_abiertas': list(PREGUNTAS_COMPRENSION.keys()),
        'rubricas': list(RUBRICAS_FINANCIERAS.keys())
    }


def obtener_plantilla_info(plantilla_key: str) -> Dict:
    """Obtiene información detallada de una plantilla"""
    
    if plantilla_key in EJERCICIOS_FINANCIEROS:
        plantilla = EJERCICIOS_FINANCIEROS[plantilla_key]
        return {
            'tipo': 'numerico',
            'titulo': plantilla['titulo'],
            'contexto': plantilla['contexto'],
            'respuesta_esperada': str(plantilla['respuesta_esperada'])
        }
    
    elif plantilla_key in PREGUNTAS_COMPRENSION:
        plantilla = PREGUNTAS_COMPRENSION[plantilla_key]
        return {
            'tipo': 'abierto',
            'titulo': plantilla['titulo'],
            'contexto': plantilla['contexto']
        }
    
    elif plantilla_key in RUBRICAS_FINANCIERAS:
        rubrica = RUBRICAS_FINANCIERAS[plantilla_key]
        return {
            'tipo': 'rubrica',
            'nombre': rubrica['nombre'],
            'palabras_clave': rubrica['palabras_clave']
        }
    
    return None
