#!/usr/bin/env python
"""
Script para cargar datos de prueba: 2 cursos de café con 6 módulos y preguntas
Ejecutar: python manage.py shell < load_cafe_data.py
"""

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo, PreguntaExamen

# Limpiar datos anteriores (opcional)
Curso.objects.all().delete()

# ==================== CURSO 1: FUNDAMENTOS DEL CAFÉ ====================
curso1 = Curso.objects.create(
    nombre="Fundamentos del Café ☕",
    descripcion="Curso completo sobre los fundamentos del cultivo y procesamiento del café",
    duracion_semanas=4,
    nivel="principiante"
)

# Módulo 1: Introducción al Café
modulo1_1 = Modulo.objects.create(
    curso=curso1,
    numero=1,
    titulo="Introducción al Café",
    descripcion="Conoce la historia y origen del café en el mundo",
    contenido="""
☕ **LECCIÓN 1: Historia del Café**

📚 El café es la segunda bebida más consumida en el mundo después del agua.

**Origen:**
- Originario de Etiopía (siglo IX)
- Llegó a Arabia en el siglo XV
- Se expandió por Europa en el siglo XVII
- Hoy se cultiva en 70+ países

**Variedades principales:**
1. Arábica (60% mundial) - Más suave y aromática
2. Robusta (40% mundial) - Más fuerte y amarga
3. Libérica - Menos común

**Consumo global:**
- 2 mil millones de tazas diarias
- Colombia es 2do productor mundial

¿Sabías? Una taza de café tiene 95-200 mg de cafeína.
""",
    duracion_dias=3
)

PreguntaExamen.objects.create(
    modulo=modulo1_1,
    pregunta="¿De qué país es originario el café?",
    opcion_a="Etiopía",
    opcion_b="Brasil",
    opcion_c="Colombia",
    opcion_d="Vietnam",
    respuesta_correcta="A"
)

PreguntaExamen.objects.create(
    modulo=modulo1_1,
    pregunta="¿Cuál es la variedad de café más consumida mundialmente?",
    opcion_a="Robusta",
    opcion_b="Arábica",
    opcion_c="Libérica",
    opcion_d="Excelsa",
    respuesta_correcta="B"
)

# Módulo 2: Siembra del Café
modulo1_2 = Modulo.objects.create(
    curso=curso1,
    numero=2,
    titulo="Siembra y Establecimiento",
    descripcion="Cómo preparar y sembrar correctamente un cafetal",
    contenido="""
🌱 **LECCIÓN 2: Siembra del Café**

📍 **Condiciones ideales:**
   ✓ Altitud: 1.200-2.000 msnm
   ✓ Temperatura: 17-23°C
   ✓ Sombra: 30-50% (con árboles)

🌳 **Preparación del terreno:**
   1. Hoyos: 30x30x30 cm
   2. Distancia: 1.5 x 1.5 metros
   3. Abono orgánico en el hoyo
   4. Compactación del suelo

⏰ **Mejor época:** Inicio de lluvias (abril-junio)

💡 **Consejo:** El café necesita sombra para producir mejor.
""",
    duracion_dias=4
)

PreguntaExamen.objects.create(
    modulo=modulo1_2,
    pregunta="¿Cuál es la temperatura ideal para el cultivo de café?",
    opcion_a="Entre 17°C y 23°C",
    opcion_b="Entre 10°C y 15°C",
    opcion_c="Entre 30°C y 35°C",
    opcion_d="Más de 40°C",
    respuesta_correcta="A"
)

PreguntaExamen.objects.create(
    modulo=modulo1_2,
    pregunta="¿Cuál es la distancia recomendada entre plantas de café?",
    opcion_a="1 metro x 1 metro",
    opcion_b="1.5 metros x 1.5 metros",
    opcion_c="2 metros x 2 metros",
    opcion_d="3 metros x 3 metros",
    respuesta_correcta="B"
)

# Módulo 3: Cuidados y Mantenimiento
modulo1_3 = Modulo.objects.create(
    curso=curso1,
    numero=3,
    titulo="Cuidados y Mantenimiento",
    descripcion="Mantenimiento diario y control de plagas",
    contenido="""
🛡️ **LECCIÓN 3: Cuidados del Cafetal**

**Riego:**
   - Frecuencia: 2-3 veces por semana
   - Profundidad: 30-40 cm
   - Mejor en horas de la mañana

**Fertilización:**
   - Abono orgánico cada 3 meses
   - Nitrógeno, fósforo y potasio
   - Mulch para retener humedad

**Plagas comunes:**
   - Roya (hongo) → Fungicida
   - Broca del café → Trampas
   - Nemátodos → Rotación de cultivos

**Poda:**
   - Anual, en época seca
   - Elimina ramas muertas
   - Forma la planta

⚠️ Revisar plantas cada 15 días.
""",
    duracion_dias=5
)

PreguntaExamen.objects.create(
    modulo=modulo1_3,
    pregunta="¿Con qué frecuencia se debe regar un cafetal?",
    opcion_a="Una vez por semana",
    opcion_b="2-3 veces por semana",
    opcion_c="Diariamente",
    opcion_d="Una vez al mes",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo1_3,
    pregunta="¿Cuál es la plaga más común en cafetales?",
    opcion_a="Roya",
    opcion_b="Mosca blanca",
    opcion_c="Gusano del maíz",
    opcion_d="Ácaros",
    respuesta_correcta="A"
)

# Módulo 4: Cosecha
modulo1_4 = Modulo.objects.create(
    curso=curso1,
    numero=4,
    titulo="Cosecha del Café",
    descripcion="Técnicas de cosecha y selección de granos",
    contenido="""
🌾 **LECCIÓN 4: Cosecha del Café**

**Maduración:**
   - Fruto rojo brillante = listo
   - Toma 6-8 meses desde flor
   - Cosecha: octubre-diciembre

**Métodos de cosecha:**
   1. Picking (selectivo) - Granos rojos
   2. Stripping (mecanizado) - Todos los granos

**Selección:**
   - Flotación: separar defectuosos
   - Granos verdes o negros se descartan
   - Densidad diferencia buenos de malos

**Rendimiento:**
   - 1 hectárea: 2.000-3.000 kg café cereza
   - Rinde 400-500 kg café pergamino

📊 Mejor método: picking manual (mejor calidad).
""",
    duracion_dias=3
)

PreguntaExamen.objects.create(
    modulo=modulo1_4,
    pregunta="¿Cuándo está listo el fruto del café para cosechar?",
    opcion_a="Cuando está verde",
    opcion_b="Cuando es rojo brillante",
    opcion_c="Cuando es marrón oscuro",
    opcion_d="Cuando cae al suelo",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo1_4,
    pregunta="¿Cuál es el rendimiento de 1 hectárea de café?",
    opcion_a="500-700 kg café pergamino",
    opcion_b="400-500 kg café pergamino",
    opcion_c="1.000-1.500 kg café pergamino",
    opcion_d="100-200 kg café pergamino",
    respuesta_correcta="B"
)

# Módulo 5: Procesamiento
modulo1_5 = Modulo.objects.create(
    curso=curso1,
    numero=5,
    titulo="Procesamiento del Café",
    descripcion="Métodos de procesamiento: fermentación y secado",
    contenido="""
⚙️ **LECCIÓN 5: Procesamiento del Café**

**Método Húmedo (Lavado):**
   1. Despulpe: quitar pulpa roja
   2. Fermentación: 24-48 horas
   3. Lavado: con agua limpia
   4. Secado: 10-14 días a 11% humedad

**Método Seco (Natural):**
   1. Secar fruto completo: 20-30 días
   2. Descascarado manual
   3. Menos inversión, más riesgo

**Calidad final:**
   - Defectos: almendras, negros, verdes
   - Porcentaje defectos < 5% = Calidad

**Almacenamiento:**
   - Lugar seco y fresco
   - Sacos de 60 kg
   - Evitar humedad > 12%

🎯 Método húmedo = mejor calidad.
""",
    duracion_dias=4
)

PreguntaExamen.objects.create(
    modulo=modulo1_5,
    pregunta="¿Cuáles son los dos métodos principales de procesamiento?",
    opcion_a="Tostado y molido",
    opcion_b="Húmedo y seco",
    opcion_c="Fermentado y natural",
    opcion_d="Rápido y lento",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo1_5,
    pregunta="¿Cuánto tiempo toma el secado en el método húmedo?",
    opcion_a="3-5 días",
    opcion_b="10-14 días",
    opcion_c="20-30 días",
    opcion_d="2-3 meses",
    respuesta_correcta="B"
)

# Módulo 6: Comercialización
modulo1_6 = Modulo.objects.create(
    curso=curso1,
    numero=6,
    titulo="Comercialización y Mercado",
    descripcion="Venta, precios y oportunidades de mercado",
    contenido="""
💰 **LECCIÓN 6: Mercado del Café**

**Precios internacionales:**
   - Cotización en dólares/libra
   - Varía por calidad
   - Arábica: $1.50-2.50/libra
   - Robusta: $0.80-1.50/libra

**Clasificación por calidad:**
   - Specialty (>85 pts): +50% precio
   - High grown: altitud > 1800 msnm
   - Estate coffee: mismo origen

**Canales de venta:**
   1. Exportadores locales
   2. Cooperativas (mejor precio)
   3. Comerciantes privados
   4. Venta directa online

**Tendencias:**
   - Café sustentable: +20% premium
   - Origen trazable: más valor
   - Certificaciones: Fair Trade, UTZ

📈 Asociarse en cooperativas mejora ingresos.
""",
    duracion_dias=3
)

PreguntaExamen.objects.create(
    modulo=modulo1_6,
    pregunta="¿Cuál es el precio aproximado del café Arábica internacionalmente?",
    opcion_a="$0.50-0.80/libra",
    opcion_b="$1.50-2.50/libra",
    opcion_c="$3.00-4.00/libra",
    opcion_d="$5.00+/libra",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo1_6,
    pregunta="¿Cuál de estas opciones mejora el precio del café?",
    opcion_a="Cultivarlo a baja altitud",
    opcion_b="Venderlo sin procesar",
    opcion_c="Tener certificaciones de sustentabilidad",
    opcion_d="Secarlo rápidamente",
    respuesta_correcta="C"
)

# ==================== CURSO 2: CAFÉ ESPECIALIZADO ====================
curso2 = Curso.objects.create(
    nombre="Café Especializado 🌟",
    descripcion="Técnicas avanzadas para producir café de alta calidad y specialty",
    duracion_semanas=6,
    nivel="avanzado"
)

# Módulo 1: Fermentación Controlada
modulo2_1 = Modulo.objects.create(
    curso=curso2,
    numero=1,
    titulo="Fermentación Controlada",
    descripcion="Técnicas de fermentación para mejorar sabor y aroma",
    contenido="""
🧪 **LECCIÓN 1: Fermentación Avanzada**

**Tipos de fermentación:**
   - Anaerobia: sin oxígeno (24-48h) → cuerpo completo
   - Aerobia: con oxígeno (12-24h) → acidez brillante
   - Mixta: combinación de ambas

**Variables críticas:**
   - Temperatura: 20-25°C ideal
   - pH: 3.5-4.5 óptimo
   - Humedad relativa: 70-85%
   - Microorganismos: bacterias ácido-lácticas

**Sabores resultantes:**
   - Frutas: piña, frutos rojos, mango
   - Florales: jazmin, rosa
   - Especiados: canela, clavos

**Monitoreo:**
   - Probar pH diariamente
   - Olor característico a fermentación
   - Burbujas en la superficie

⚡ Fermentación correcta = 15-20% aumento de precio.
""",
    duracion_dias=5
)

PreguntaExamen.objects.create(
    modulo=modulo2_1,
    pregunta="¿Cuál es la temperatura ideal para fermentación controlada?",
    opcion_a="10-15°C",
    opcion_b="20-25°C",
    opcion_c="30-35°C",
    opcion_d="40°C+",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo2_1,
    pregunta="¿Qué tipo de fermentación produce sabores más brillantes y ácidos?",
    opcion_a="Anaerobia",
    opcion_b="Aerobia",
    opcion_c="Mixta",
    opcion_d="Ninguna",
    respuesta_correcta="B"
)

# Módulo 2: Análisis Sensorial
modulo2_2 = Modulo.objects.create(
    curso=curso2,
    numero=2,
    titulo="Análisis Sensorial del Café",
    descripcion="Evaluación de calidad mediante cata (cupping)",
    contenido="""
👃 **LECCIÓN 2: Cupping - Análisis Sensorial**

**Protocolo SCA (Specialty Coffee Association):**
   1. Evaluación visual: color, defectos
   2. Aroma en seco (grano tostado)
   3. Aroma en mojado (agua caliente)
   4. Sabor: notas en boca
   5. Retrogusto: sabor residual
   6. Acidez: brillantez
   7. Cuerpo: peso en boca
   8. Uniformidad y limpieza

**Escala 0-100:**
   - 90+: Specialty (Excelente)
   - 85-89: Specialty (Muy Bueno)
   - 80-84: Specialty (Bueno)
   - <80: No specialty

**Descriptores de sabor:**
   - Frutales: frambuesa, cereza, durazno
   - Florales: rosa, jazmín, violeta
   - Especias: canela, nuez moscada
   - Chocolate, caramelo, tabaco

🎯 Entrenamiento necesario para evaluar correctamente.
""",
    duracion_dias=4
)

PreguntaExamen.objects.create(
    modulo=modulo2_2,
    pregunta="¿Cuál es la puntuación mínima para café Specialty?",
    opcion_a="75 puntos",
    opcion_b="80 puntos",
    opcion_c="85 puntos",
    opcion_d="90 puntos",
    respuesta_correcta="B"
)

PreguntaExamen.objects.create(
    modulo=modulo2_2,
    pregunta="¿Cuántos aspectos evalúa el protocolo SCA en cupping?",
    opcion_a="3 aspectos",
    opcion_b="5 aspectos",
    opcion_c="8 aspectos",
    opcion_d="10 aspectos",
    respuesta_correcta="C"
)

# Módulo 3: Trazabilidad y Sostenibilidad
modulo2_3 = Modulo.objects.create(
    curso=curso2,
    numero=3,
    titulo="Trazabilidad y Sostenibilidad",
    descripcion="Certificaciones y prácticas sostenibles en café",
    contenido="""
🌱 **LECCIÓN 3: Café Sostenible**

**Certificaciones principales:**
   - Fair Trade: precio justo a productores
   - Rainforest Alliance: biodiversidad
   - UTZ: prácticas responsables
   - Orgánico: sin químicos sintéticos

**Beneficios de la sostenibilidad:**
   - Precios 20-40% más altos
   - Acceso a mercados premium
   - Preservación de biodiversidad
   - Mejor calidad del suelo

**Prácticas recomendadas:**
   1. Sombra nativa (biodiversidad)
   2. Manejo de agua responsable
   3. Compostaje de residuos
   4. Energías renovables
   5. Registro documentado

**Trazabilidad:**
   - Código QR en sacos
   - Información de origen
   - Historial de procesamiento
   - Laboratorio de análisis

💚 Mercado crece 15% anual en cafés sostenibles.
""",
    duracion_dias=5
)

PreguntaExamen.objects.create(
    modulo=modulo2_3,
    pregunta="¿Cuánto más caro es el café con certificación Fair Trade?",
    opcion_a="5-10% más",
    opcion_b="10-15% más",
    opcion_c="20-40% más",
    opcion_d="50%+ más",
    respuesta_correcta="C"
)

PreguntaExamen.objects.create(
    modulo=modulo2_3,
    pregunta="¿Cuál es la principal ventaja de la trazabilidad en café?",
    opcion_a="Reducir costos",
    opcion_b="Vender más rápido",
    opcion_c="Garantizar origen y calidad",
    opcion_d="Aumentar producción",
    respuesta_correcta="C"
)

# Módulo 4: Microclimas y Terroir
modulo2_4 = Modulo.objects.create(
    curso=curso2,
    numero=4,
    titulo="Microclimas y Terroir",
    descripcion="Cómo el terreno y clima afectan el sabor del café",
    contenido="""
🏔️ **LECCIÓN 4: Terroir del Café**

**Factores del terroir:**
   - Altitud: 800-2200 msnm (variación sabor)
   - Suelo: Volcánico > rico en minerales
   - Temperatura: fluctuación diaria importante
   - Humedad: 60-70% ideal
   - Exposición solar: norte vs sur

**Altitud y sabor:**
   - <1200 msnm: cuerpo, menos acidez
   - 1200-1600 msnm: balance
   - >1600 msnm: acidez, complejidad

**Suelos ideales:**
   - Volcánicos (Colombia, Etiopía)
   - pH 5.5-6.5
   - Materia orgánica 3-5%
   - Drenaje bueno

**Regiones famosas y sabores:**
   - Etiopía: florales, té
   - Kenia: frambuesa, negro
   - Colombia: chocolate, caramelo
   - Costa Rica: frutas, chocolatoso

🌍 Mismo origen, diferentes fincas = diferentes sabores.
""",
    duracion_dias=4
)

PreguntaExamen.objects.create(
    modulo=modulo2_4,
    pregunta="¿A qué altitud se obtiene más acidez y complejidad en café?",
    opcion_a=">800 msnm",
    opcion_b=">1200 msnm",
    opcion_c=">1600 msnm",
    opcion_d=">2000 msnm",
    respuesta_correcta="C"
)

PreguntaExamen.objects.create(
    modulo=modulo2_4,
    pregunta="¿Cuál es el rango ideal de pH del suelo para café?",
    opcion_a="4.0-4.5",
    opcion_b="5.5-6.5",
    opcion_c="7.0-7.5",
    opcion_d="8.0-8.5",
    respuesta_correcta="B"
)

# Módulo 5: Tecnología en Cultivo
modulo2_5 = Modulo.objects.create(
    curso=curso2,
    numero=5,
    titulo="Tecnología Agrícola Moderna",
    descripcion="Herramientas tecnológicas para optimizar cultivo",
    contenido="""
🚀 **LECCIÓN 5: Tecnología en Café**

**Herramientas digitales:**
   - Drones: monitoreo de plagas
   - Sensores IoT: humedad, temperatura
   - Aplicaciones móviles: registro datos
   - GPS: mapeo de fincas

**Análisis de datos:**
   - Predicción de rendimiento
   - Optimización de riego
   - Detección temprana de plagas
   - Análisis de suelo

**Riego inteligente:**
   - Sistemas de goteo automático
   - Sensores de humedad
   - Ahorro 30-40% agua
   - Mejor distribución

**Financiamiento agrícola:**
   - Créditos digitales
   - Seguros paramétricos
   - Blockchain para trazabilidad

💻 Tecnología puede aumentar rendimiento 20-30%.
""",
    duracion_dias=4
)

PreguntaExamen.objects.create(
    modulo=modulo2_5,
    pregunta="¿Qué ahorro de agua puede lograr un sistema de riego inteligente?",
    opcion_a="10-15%",
    opcion_b="20-25%",
    opcion_c="30-40%",
    opcion_d="50%+",
    respuesta_correcta="C"
)

PreguntaExamen.objects.create(
    modulo=modulo2_5,
    pregunta="¿Cuál es una ventaja de usar drones en cultivo de café?",
    opcion_a="Reducir mano de obra",
    opcion_b="Monitoreo de plagas",
    opcion_c="Aumentar lluvia",
    opcion_d="Cambiar el suelo",
    respuesta_correcta="B"
)

# Módulo 6: Negocio y Exportación
modulo2_6 = Modulo.objects.create(
    curso=curso2,
    numero=6,
    titulo="Negocios y Exportación",
    descripcion="Modelos de negocio y estrategias de exportación",
    contenido="""
📊 **LECCIÓN 6: Café como Negocio**

**Modelos de negocio:**
   1. Productor → Exportador → Cafetería
   2. Directo a tostador (Direct Trade)
   3. Café certificado premium
   4. Agro-turismo (tours de finca)

**Costos de producción:**
   - Establecimiento: $3.000-5.000/ha
   - Mantenimiento anual: $800-1.200/ha
   - Cosecha: $0.50-1.00/kg
   - Procesamiento: $0.20-0.50/kg

**Márgenes de ganancia:**
   - Café commodity: 20-30%
   - Café specialty: 50-100%
   - Directo a consumidor: 200%+

**Exportación:**
   - Documentación: FitosanUp, certificados
   - Transporte: contenedores 40 sacos
   - Seguros y aranceles: 5-10% costo
   - Tiempos: 2-3 meses

**Estrategias:**
   - Asociarse cooperativa: volumen + poder
   - Marca propia: diferenciación
   - Storytelling: origen + sostenibilidad

🎯 Modelo directo = márgenes hasta 300%.
""",
    duracion_dias=5
)

PreguntaExamen.objects.create(
    modulo=modulo2_6,
    pregunta="¿Cuál es el costo anual de mantenimiento de café?",
    opcion_a="$200-300/ha",
    opcion_b="$500-700/ha",
    opcion_c="$800-1.200/ha",
    opcion_d="$2.000+/ha",
    respuesta_correcta="C"
)

PreguntaExamen.objects.create(
    modulo=modulo2_6,
    pregunta="¿Cuál es la margen de ganancia en café Specialty?",
    opcion_a="10-20%",
    opcion_b="20-30%",
    opcion_c="50-100%",
    opcion_d="5-10%",
    respuesta_correcta="C"
)

print("✅ DATOS DE CAFÉ CARGADOS EXITOSAMENTE!")
print(f"✅ Curso 1: {curso1.nombre} con {curso1.modulo_set.count()} módulos")
print(f"✅ Curso 2: {curso2.nombre} con {curso2.modulo_set.count()} módulos")
print(f"✅ Total preguntas: {PreguntaExamen.objects.count()}")
