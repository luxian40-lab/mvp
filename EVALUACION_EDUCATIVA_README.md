# Sistema de Evaluación Educativa - EKI

## Nuevos Modelos Implementados

### 1. **Estudiante** (extendido)
- **Campos añadidos:**
  - `municipio`: Municipio donde reside
  - `departamento`: Departamento/Estado
  - `ubicacion_detalle`: Vereda, barrio o detalles adicionales

### 2. **ObjetivoCurso**
Define los objetivos de aprendizaje del curso (general y específicos).

**Campos principales:**
- `tipo`: General o Específico
- `descripcion`: Descripción del objetivo
- `peso_evaluacion`: Peso porcentual en la evaluación final (0-100)

**Uso:** Cada curso puede tener 1 objetivo general y 3-5 objetivos específicos. La suma de pesos debe ser 100%.

### 3. **RubricaEvaluacion**
Rúbricas para evaluar respuestas abiertas y ejercicios.

**Campos principales:**
- `objetivo`: Objetivo de curso asociado
- `criterios`: JSON con niveles de desempeño (excelente, bueno, regular, insuficiente)
- `palabras_clave`: Términos esperados en respuestas correctas

**Ejemplo de criterios:**
```json
{
  "comprension_concepto": {
    "excelente": 100,
    "bueno": 75,
    "regular": 50,
    "insuficiente": 25
  },
  "aplicacion_practica": {
    "excelente": 100,
    "bueno": 80,
    "regular": 60,
    "insuficiente": 30
  }
}
```

### 4. **EjercicioPractico**
Ejercicios de diferentes tipos para evaluación continua.

**Tipos de ejercicios:**
- `numerico`: Cálculos (utilidades, ingresos, costos, flujo de caja)
- `abierto`: Respuesta abierta evaluada con LLM + rúbrica
- `hipotetico`: Situación hipotética basada en contenido visto
- `comprension`: Preguntas "¿Entendiste?" al final de módulos

**Campos clave:**
- **Para numéricos:** `respuesta_numerica_esperada`, `tolerancia_porcentual`, `formula_evaluacion`
- **Para abiertos:** `rubrica` (FK a RubricaEvaluacion)
- `enunciado`: Texto del ejercicio
- `contexto_previo`: Información necesaria para resolver

**Ejemplo numérico (finanzas):**
```
Enunciado: "Calcula la utilidad mensual de tu negocio"
Contexto: "Ingresos: $500,000. Costos: $320,000"
Fórmula: "ingresos - costos = utilidad"
Respuesta esperada: 180000
Tolerancia: 5% (±9000)
```

### 5. **RespuestaEjercicio**
Guarda las respuestas de estudiantes a ejercicios.

**Campos principales:**
- `respuesta_texto` / `respuesta_numerica` / `respuesta_audio_url`
- `puntaje_obtenido`: Puntaje (0-100)
- `feedback_ia`: Retroalimentación automática
- `modalidad`: texto, audio o mixto
- `tiempo_respuesta_segundos`
- `intento`: Número de intento (permite reintentos)

### 6. **InteraccionLog**
Log completo de interacciones para análisis de métricas.

**Campos principales:**
- `estudiante`, `curso`, `modulo`
- `tipo`: pregunta, reto, ejercicio, examen, consulta, comprension
- `modalidad`: texto, audio, mixto
- `duracion_segundos`
- `puntaje`, `es_correcto`
- `municipio`, `departamento` (para análisis geográfico)
- `metadata`: JSON con información adicional

**Uso para dashboard:**
- Filtrar por municipio, curso, modalidad
- Comparar rendimiento audio vs texto
- Tendencias temporales de puntajes
- Identificar módulos con mayor dificultad

## Flujo de Evaluación Propuesto

### Al finalizar cada módulo:
1. **Pregunta de comprensión**: "¿Entendiste el concepto?"
   - Tipo: `comprension`
   - Respuesta simple del estudiante
   
2. **Si respondió afirmativamente:**
   - Generar **reto hipotético** basado en contenido visto
   - Tipo: `hipotetico`
   - Ejemplo: "Imagina que tienes una finca de café. ¿Cómo aplicarías lo aprendido sobre control de plagas?"

3. **Evaluación práctica:**
   - Para cursos de finanzas: ejercicios numéricos (calcular utilidades)
   - Para cursos técnicos: ejercicios abiertos con rúbrica

### Al finalizar el curso:
- **Examen final** alineado a objetivos específicos
- Cada pregunta vinculada a un `ObjetivoCurso`
- Puntaje ponderado según `peso_evaluacion`

## Próximos Pasos

1. ✅ Modelos creados
2. ⏳ Crear migraciones: `python manage.py makemigrations`
3. ⏳ Aplicar migraciones: `python manage.py migrate`
4. ⏳ Implementar funciones de evaluación automática en `core/evaluacion_ia.py`
5. ⏳ Crear dashboard de métricas en `/admin/analytics/`
6. ⏳ Modificar flujo conversacional del bot (sin menú 1,2,3)

## Comandos Útiles

```bash
# Crear migraciones
python manage.py makemigrations core

# Aplicar migraciones
python manage.py migrate

# Crear admin para nuevos modelos
# (añadir en core/admin.py)

# Poblar objetivos de ejemplo
python manage.py shell
>>> from core.models import Curso, ObjetivoCurso
>>> curso = Curso.objects.first()
>>> ObjetivoCurso.objects.create(
...     curso=curso,
...     tipo='general',
...     descripcion='Comprender y aplicar conceptos básicos de finanzas rurales',
...     peso_evaluacion=100
... )
```

## Notas Importantes

- **No pedir cédula invasivamente:** Capturar solo nombre y ubicación al inicio
- **Municipio:** Guardar para análisis geográfico en dashboard
- **Audio:** Soportado en respuestas (transcribir con Whisper)
- **Reintentos:** Permitir múltiples intentos en ejercicios (campo `intento`)
- **Feedback:** Siempre generar retroalimentación constructiva (no solo "correcto/incorrecto")
