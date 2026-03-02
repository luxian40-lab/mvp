"""
Comando para poblar cursos profesionales de eki
Incluye:
1. Café Arábigo (Fondo Nacional de Cafeteros)
2. Aguacate Hass (Producción comercial)
"""

from django.core.management.base import BaseCommand
from core.models import Curso, Modulo

class Command(BaseCommand):
    help = 'Crea cursos profesionales con módulos completos'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Creando cursos profesionales...\n')
        
        # =====================================================
        # 1. CURSO: CAFÉ ARÁBIGO - FONDO NACIONAL DE CAFETEROS
        # =====================================================
        
        cafe_curso, created = Curso.objects.get_or_create(
            nombre="Café Arábigo: Producción Sostenible",
            defaults={
                'descripcion': '''Curso completo sobre producción sostenible de café arábigo en Colombia.
                
Desarrollado para el Fondo Nacional de Cafeteros, este curso cubre desde la siembra hasta la cosecha, incluyendo manejo integrado de plagas, fertilización y buenas prácticas agrícolas.

Al finalizar serás capaz de:
• Establecer y manejar cultivos de café de alta calidad
• Implementar prácticas sostenibles certificables
• Identificar y controlar plagas y enfermedades
• Optimizar la cosecha y beneficio del café
• Cumplir con estándares de calidad internacional''',
                'emoji': '☕',
                'duracion_semanas': 8,
                'activo': True,
                'orden': 1
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Curso creado: {cafe_curso}'))
            
            # Módulos del curso de Café
            modulos_cafe = [
                {
                    'numero': 1,
                    'titulo': 'Establecimiento del Cultivo',
                    'descripcion': 'Selección del lote, variedades y preparación del terreno',
                    'contenido': '''📚 MÓDULO 1: ESTABLECIMIENTO DEL CULTIVO

🌱 **1.1 Selección del Lote**

El café arábigo requiere:
• Altitud: 1.200 - 1.800 msnm (óptimo para calidad)
• Temperatura: 18-22°C promedio
• Precipitación: 1.800 - 2.500 mm/año
• Suelos profundos (>50cm), bien drenados
• pH entre 5.0 y 5.5

⚠️ Evitar:
- Zonas con heladas
- Suelos muy compactados
- Pendientes mayores al 50%

🌾 **1.2 Variedades Recomendadas en Colombia**

**Castillo®** (resistente a roya)
• Producción: Alta (1.8-2.5 ton/ha)
• Calidad en taza: Excelente (>83 puntos)
• Resistencia: Roya del cafeto

**Cenicafé 1**
• Producción: Muy alta
• Porte: Bajo (facilita cosecha)
• Resistencia: Roya y CBD

**Variedad Colombia**
• Tradicional en zonas cafeteras
• Buena adaptación
• Requiere manejo de roya

📏 **1.3 Diseño de Siembra**

Distancias recomendadas:
• 1.5m entre surcos x 1.0m entre plantas = 6.666 plantas/ha
• 2.0m entre surcos x 1.0m entre plantas = 5.000 plantas/ha

Trazo en curvas de nivel (pendientes >10%)

🌿 **1.4 Semillero y Germinador**

Pasos:
1. Seleccionar semilla certificada (Cenicafé)
2. Germinador: Arena limpia, sombra 50%
3. Trasplante a bolsas (chapola)
4. Vivero: 4-6 meses hasta 50cm altura
5. Siembra definitiva en campo

💧 **1.5 Preparación del Lote**

Antes de sembrar:
• Análisis de suelo
• Corrección de pH (cal dolomita)
• Ahoyado: 30x30x30 cm
• Fertilización de fondo (150g/planta)

• Siembra al inicio de lluvias

✅ Actividad: Calcula cuántas plantas necesitas para 1 hectárea con distancia 1.5m x 1.0m''',
                    'duracion_dias': 7
                },
                {
                    'numero': 2,
                    'titulo': 'Nutrición y Fertilización',
                    'descripcion': 'Plan nutricional completo y aplicación de fertilizantes',
                    'contenido': '''📚 MÓDULO 2: NUTRICIÓN Y FERTILIZACIÓN

🧪 **2.1 Requerimientos Nutricionales del Café**

Elementos principales:
• **Nitrógeno (N)**: Crecimiento vegetativo, color verde
• **Fósforo (P)**: Desarrollo radicular, floración
• **Potasio (K)**: Llenado de grano, resistencia

Dosis anual (café adulto/ha):
- N: 250-300 kg/ha
- P₂O₅: 50-80 kg/ha  
- K₂O: 200-250 kg/ha

📊 **2.2 Análisis de Suelo**

Realízalo cada 2-3 años:
• Determina pH, materia orgánica, nutrientes
• Ajusta plan de fertilización
• Reduce costos y mejora resultados

Niveles óptimos:
- pH: 5.0-5.5
- Materia orgánica: >5%
- Ca: >4 meq/100g
- Mg: >1.5 meq/100g

🌿 **2.3 Plan de Fertilización por Edad**

**Año 1 (siembra - 12 meses):**
- 1er mes: 50g de 10-30-10/planta
- 4to mes: 80g de 17-6-18-2/planta
- 8vo mes: 100g de 17-6-18-2/planta

**Año 2:**
- 150g de 17-6-18-2 cada 3 meses (600g/año)

**Café adulto (3+ años):**
- 200-250g de 17-6-18-2 cada 2 meses
- Total: 1.2-1.5 kg/planta/año

📅 **2.4 Épocas de Aplicación**

Fraccionamiento ideal:
• **Marzo-Abril**: Post-cosecha (30%)
• **Junio**: Antes de floración (30%)
• **Septiembre**: Llenado de grano (40%)

Aplicar al inicio de lluvias, en corona (20cm del tallo)

🍂 **2.5 Fertilización Orgánica**

Materia orgánica aporta:
• Mejora estructura del suelo
• Retiene agua y nutrientes
• Favorece microorganismos

Opciones:
- Compost: 2-3 kg/planta/año
- Pulpa de café compostada
- Lombricompuesto: 500g/planta
- Bocashi

💡 **2.6 Síntomas de Deficiencia**

Aprende a identificar:
• **N**: Hojas amarillas (clorosis)
• **P**: Crecimiento lento, hojas oscuras
• **K**: Bordes quemados en hojas viejas
• **Mg**: Amarillamiento entre nervaduras
• **B**: Hojas deformadas, muerte de brotes

✅ Actividad: Calcula la fertilización para 1 hectárea de café de 4 años''',
                    'duracion_dias': 7
                },
                {
                    'numero': 3,
                    'titulo': 'Manejo Integrado de Plagas y Enfermedades',
                    'descripcion': 'Control de roya, broca y otras plagas del café',
                    'contenido': '''📚 MÓDULO 3: MANEJO INTEGRADO DE PLAGAS Y ENFERMEDADES

🍄 **3.1 Roya del Cafeto** (*Hemileia vastatrix*)

La enfermedad más devastadora del café:

**Síntomas:**
• Manchas amarillas-anaranjadas en hojas
• Polvillo amarillo en envés (esporas)
• Defoliación severa
• Pérdida de cosecha hasta 50%

**Control integrado:**
1. **Variedades resistentes**: Castillo®, Cenicafé 1
2. **Nutrición balanceada**: Café bien nutrido resiste mejor
3. **Regulación de sombra**: Evitar humedad excesiva
4. **Fungicidas** (si epidemia):
   - Preventivos: Cobre (oxicloruro 3g/L)
   - Sistémicos: Azoxystrobin (solo en emergencia)

**Umbral de acción:** >10% incidencia

🐛 **3.2 Broca del Café** (*Hypothenemus hampei*)

Insecto que daña el grano:

**Identificación:**
• Perforaciones en frutos
• Granos vanos (vacíos)
• Reducción de calidad hasta 40%

**Manejo IPM:**
1. **Re-re (recolección repase)**: Cosechar todo, no dejar frutos
2. **Trampas BROCAP**: 20 trampas/ha con metanol+etanol
3. **Control biológico**: *Beauveria bassiana* 2x10⁹ esporas/ml
4. **Control químico**: Último recurso (Dimetoato, solo si >5% infestación)

**CLAVE:** No dejar frutos en suelo o árbol post-cosecha

🦟 **3.3 Minador de la Hoja** (*Leucoptera coffeella*)

**Síntomas:**
• Galerías serpenteadas en hojas
• Manchas marrones
• Defoliación en ataques severos

**Control:**
• Controles naturales (avispas parasitoides)
• Aplicar insecticida solo si >30% hojas afectadas
• Cyantraniliprole 100ml/200L

🕷️ **3.4 Control Biológico**

Organismos benéficos:
• **Hongos entomopatógenos**: *Beauveria bassiana*, *Metarhizium*
• **Parasitoides**: Avispas que atacan broca
• **Depredadores**: Hormigas, arañas

Cómo favorecerlos:
- Reducir insecticidas de amplio espectro
- Mantener biodiversidad (flores, arbustos)
- Coberturas vegetales

🌡️ **3.5 Monitoreo y Umbrales**

Sistema de alerta temprana:
• Revisar 30 árboles/ha semanalmente
• Registrar % de incidencia
• Actuar solo si se supera umbral económico

**Umbrales:**
- Roya: 10% hojas infectadas
- Broca: 5% frutos perforados
- Minador: 30% hojas afectadas

📋 **3.6 Manejo Agroecológico**

Prácticas sostenibles:
• Sombra regulada (30-40%)
• Barreras vivas
• Alelopatía (plantas repelentes)
• Diversificación de cultivos
• Reducción de químicos

✅ Actividad: Identifica 3 prácticas preventivas para reducir roya sin químicos''',
                    'duracion_dias': 10
                },
                {
                    'numero': 4,
                    'titulo': 'Cosecha y Beneficio del Café',
                    'descripcion': 'Técnicas de cosecha selectiva y procesamiento post-cosecha',
                    'contenido': '''📚 MÓDULO 4: COSECHA Y BENEFICIO DEL CAFÉ

🍒 **4.1 Momento Óptimo de Cosecha**

El café debe cosecharse maduro:
• Color rojo intenso (cereza madura)
• Fácil desprendimiento
• Grado BRIX >18 (dulzor)

⏰ **Épocas de cosecha en Colombia:**
- Cosecha principal: Octubre-Diciembre
- Mitaca (traviesa): Abril-Junio

⚠️ **NO cosechar:**
- Verdes (inmadura)
- Sobremaduros (fermentados)
- Secos en árbol (pasilla)

Estos reducen calidad y precio hasta 50%

✋ **4.2 Técnica de Cosecha Selectiva**

**Cosecha manual:**
• Recoger solo cerezas maduras
• Pasar cada 8-10 días
• Usar canastos con banda en cintura
• Rendimiento: 80-120 kg café cereza/día

**Ventajas:**
- Calidad superior (café especial)
- Mejor precio (hasta +30%)
- Reduce sobremaduras

📊 **4.3 Rendimiento en Conversión**

Factores de conversión:
• 1 kg café pergamino seco (cps) = 5 kg café cereza
• 1 kg café excelso = 1.25 kg cps

Ejemplo:
- Cosecha: 10.000 kg cereza
- Pergamino seco: 2.000 kg cps
- Café excelso: 1.600 kg

💧 **4.4 Beneficio Húmedo del Café**

Proceso tradicional en Colombia:

**Paso 1: Despulpado (2-6 horas post-cosecha)**
• Máquina despulpadora
• Separar pulpa de grano
• Café en baba (mucílago)

**Paso 2: Fermentación (12-20 horas)**
• Tanques de fermentación
• Microorganismos eliminan mucílago
• Tiempo varía según temperatura:
  - Clima cálido: 12-14h
  - Clima frío: 18-20h
• Punto: Al tacto, granos ásperos (sin babilla)

**Paso 3: Lavado**
• Agua limpia en canales
• Remover mucílago y miel
• 3-4 lavadas
• Clasificación por densidad (flota lo defectuoso)

**Paso 4: Secado**
• Patio de secado o elba (parabólico)
• Humedad final: 10-12%
• Secado lento y uniforme (8-12 días patio, 24-30h elba)
• Voltear cada 2 horas

☀️ **4.5 Beneficio Ecológico (Becolsub)**

Alternativa sostenible:
• Despulpado sin agua
• Desmucilaginadora mecánica
• Ahorra 95% del agua
• Reduce contaminación

Pasos:
1. Despulpado
2. Desmucilaginado mecánico
3. Lavado mínimo (20L/kg)
4. Secado

🌍 **4.6 Control de Calidad Post-Cosecha**

Criterios de calidad:
• Humedad: 10-12%
• Granos defectuosos: <5%
• Color: Verde azulado uniforme
• Olor: Fresco, sin fermentos

Defectos graves:
- Granos vinagre (fermentados)
- Granos negros (hongos)
- Cardenillo (sobresecado)
- Mordidos por broca

💰 **4.7 Valor Agregado - Cafés Especiales**

Certificaciones aumentan precio:
• **Orgánico**: +20-30%
• **Fair Trade**: +15-25%
• **Rainforest Alliance**: +10-15%
• **Denominación de Origen**: +30-50%

Puntuación SCA:
- <80 puntos: Café comercial
- 80-84: Café premium
- 85-89: Café especial
- 90+: Café excepcional

✅ Actividad: Calcula cuántos kg de café excelso obtienes de 5.000 kg de café cereza''',
                    'duracion_dias': 10
                },
                {
                    'numero': 5,
                    'titulo': 'Sostenibilidad y Buenas Prácticas Agrícolas',
                    'descripcion': 'Prácticas sostenibles, conservación y certificaciones',
                    'contenido': '''📚 MÓDULO 5: SOSTENIBILIDAD Y BUENAS PRÁCTICAS AGRÍCOLAS

🌍 **5.1 Principios de Agricultura Sostenible**

Caficultura sostenible = Equilibrio entre:
• **Económico**: Rentabilidad del productor
• **Ambiental**: Conservación de recursos
• **Social**: Bienestar de familias cafeteras

Pilares fundamentales:
1. Producción eficiente
2. Calidad superior
3. Conservación ambiental
4. Responsabilidad social

🌳 **5.2 Conservación de Suelos**

El suelo es tu capital:

**Prácticas recomendadas:**
• **Coberturas vegetales**: Maní forrajero, kudzú
• **Barreras vivas**: Vetiver, king grass
• **Siembra en curvas de nivel**: Reduce erosión 80%
• **Manejo de arvenses**: Controles selectivos, no químicos totales
• **Incorporación de materia orgánica**: 2-3 kg/planta/año

**Evitar:**
- Quemas
- Labranza excesiva
- Monocultivo sin cobertura
- Pendientes sin terrazas

💧 **5.3 Uso Eficiente del Agua**

Agua = recurso estratégico:

**En beneficio:**
• Beneficio húmedo tradicional: 40 litros/kg cps
• Beneficio ecológico (Becolsub): 2-5 litros/kg cps
• Recircular agua de lavado
• Tanques de sedimentación

**Manejo de aguas mieles:**
• Prohibido verterlas a ríos (multa)
• Tratamiento con SMTA (Sistema Modular Anaeróbico)
• Compostar pulpa y mucílago
• Generar biogás

**En riego (si aplica):**
• Riego por goteo (eficiencia 90%)
• Mulching para retener humedad
• Monitoreo de humedad del suelo

🌿 **5.4 Biodiversidad en el Cafetal**

Café bajo sombra:

**Beneficios:**
• Microclima favorable
• Reduce stress hídrico
• Hábitat para fauna benéfica
• Diversificación de ingresos

**Árboles recomendados:**
- Guamo (*Inga spp.*): Fijador de nitrógeno
- Nogal cafetero (*Cordia alliodora*): Madera
- Plátano: Ingresos corto plazo
- Cítricos: Alimento + ingreso

**Sombra ideal:** 30-40% (no exceder)

🏆 **5.5 Certificaciones de Sostenibilidad**

**Café Orgánico (Certificación USDA/UE):**
Requisitos:
• Sin agroquímicos sintéticos (3 años transición)
• Fertilización orgánica
• Control biológico de plagas
• Plan de manejo orgánico
• Inspecciones anuales
Prima: +25-30%

**Rainforest Alliance:**
Requisitos:
• Conservación de ecosistemas
• Protección de fauna silvestre
• Manejo integrado de plagas
• Bienestar laboral
• Prohibición de agroquímicos más peligrosos
Prima: +10-15%

**Fair Trade (Comercio Justo):**
Requisitos:
• Organización cooperativa
• Precio mínimo garantizado
• Prima social ($0.20/lb)
• No trabajo infantil
• Condiciones laborales dignas
Prima: +15-20%

📋 **5.6 Buenas Prácticas Agrícolas (BPA)**

**Registro y trazabilidad:**
• Cuaderno de campo (aplicaciones, cosechas)
• Mapeo del predio
• Análisis de suelo (cada 2-3 años)
• Control de plagas y enfermedades
• Registros de ventas

**Manejo de agroquímicos:**
• Bodega exclusiva (ventilada, señalizada)
• EPP obligatorio (guantes, mascarilla)
• Triple lavado de envases
• Devolución envases vacíos (Campo Limpio)
• Respetar periodos de carencia

**Seguridad laboral:**
• Capacitación en BPA
• EPP disponible
• Agua potable y sanitarios
• Botiquín de primeros auxilios

💰 **5.7 Rentabilidad Sostenible**

Costos de producción (por hectárea):
• Fertilización: $1.5-2.0 M
• Control de plagas: $800k-1.2 M
• Cosecha: $2.0-3.0 M
• Beneficio: $500k
• Otros: $800k
**Total:** $5.6-7.2 M/ha

Ingresos potenciales:
• Producción: 1.800 kg cps/ha
• Precio promedio: $8.000/kg cps
• **Ingreso bruto: $14.4 M/ha**
• **Margen: $7.2-8.8 M/ha**

Cafés especiales (85+ puntos):
• Precio: $15.000-25.000/kg
• **Margen aumenta hasta 200%**

🎯 **5.8 Plan de Acción Sostenible**

Para tu finca:
1. Realizar análisis de suelo
2. Implementar coberturas vegetales
3. Establecer sombra regulada (30%)
4. Adoptar beneficio ecológico
5. Registrar todas las actividades
6. Capacitar a trabajadores
7. Buscar certificación (año 3)

✅ Actividad Final: Diseña un plan de acción sostenible para 1 hectárea de café, incluyendo costos y proyección de ingresos

🎓 **¡FELICITACIONES!**
Has completado el curso de Café Arábigo: Producción Sostenible. 

Ahora estás listo para:
✅ Establecer y manejar un cafetal de alta calidad
✅ Implementar prácticas sostenibles
✅ Controlar plagas y enfermedades
✅ Producir café especial certificable
✅ Obtener mejores precios y rentabilidad

Recuerda tomar el examen final para obtener tu certificado del Fondo Nacional de Cafeteros.''',
                    'duracion_dias': 10
                }
            ]
            
            for modulo_data in modulos_cafe:
                Modulo.objects.create(curso=cafe_curso, **modulo_data)
            
            self.stdout.write(self.style.SUCCESS(f'  ✅ {len(modulos_cafe)} módulos creados para Café'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  El curso {cafe_curso} ya existía'))
        
        # =====================================================
        # 2. CURSO: AGUACATE HASS
        # =====================================================
        
        aguacate_curso, created = Curso.objects.get_or_create(
            nombre="Aguacate Hass: Producción Comercial",
            defaults={
                'descripcion': '''Curso completo sobre producción comercial de aguacate Hass.

Este curso cubre todo el proceso productivo del aguacate Hass, desde el establecimiento del huerto hasta la post-cosecha, con enfoque en prácticas sostenibles y rentables.

Al finalizar serás capaz de:
• Establecer un huerto de aguacate Hass productivo
• Implementar el manejo integrado del cultivo
• Controlar plagas y enfermedades principales
• Realizar cosecha y post-cosecha de calidad exportación
• Maximizar la rentabilidad del cultivo''',
                'emoji': '🥑',
                'duracion_semanas': 7,
                'activo': True,
                'orden': 2
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Curso creado: {aguacate_curso}'))
            
            # Módulos del curso de Aguacate
            modulos_aguacate = [
                {
                    'numero': 1,
                    'titulo': 'Establecimiento del Huerto',
                    'descripcion': 'Selección del sitio, variedades y diseño de plantación',
                    'contenido': '''📚 MÓDULO 1: ESTABLECIMIENTO DEL HUERTO

🥑 **1.1 Requerimientos Agroecológicos**

El aguacate Hass necesita:
• **Altitud**: 1.800 - 2.600 msnm
• **Temperatura**: 16-24°C (óptimo 18-22°C)
• **Precipitación**: 1.200 - 1.800 mm/año (bien distribuida)
• **Humedad relativa**: 60-80%
• **Suelos**: Profundos (>1m), bien drenados
• **pH**: 5.5 - 6.5
• **Pendientes**: <25% (facilita mecanización)

⚠️ **Evitar:**
- Heladas (temperatura <0°C mata el árbol)
- Suelos pesados o con mal drenaje (pudrición de raíz - *Phytophthora*)
- Zonas con vientos fuertes constantes

🌳 **1.2 Variedad Hass**

Características:
• Piel rugosa, cambia de verde a negro al madurar
• Peso: 180-350g
• Alto contenido de aceite (12-17%)
• Excelente calidad organoléptica
• Alta demanda internacional
• Precio premium en mercados

Ventajas comerciales:
- Larga vida post-cosecha (3-4 semanas)
- Resistencia al transporte
- Acepta almacenamiento refrigerado
- Mercado consolidado (USA, Europa, Asia)

📐 **1.3 Diseño de Plantación**

**Marcos de siembra recomendados:**
• **6m x 6m** = 278 árboles/ha (sistema tradicional)
• **7m x 7m** = 204 árboles/ha (más luz, mecanizable)
• **5m x 6m** = 333 árboles/ha (alta densidad, requiere poda)

Sistema en tresbolillo (hexagonal):
- Mejor aprovechamiento de espacio
- Mayor producción por hectárea

Orientación de surcos:
- Norte-Sur (zonas planas)
- Curvas de nivel (pendientes >10%)

🌺 **1.4 Polinización y Portainjertos**

**Polinización cruzada obligatoria:**
El aguacate tiene flores Tipo A y Tipo B:
• **Hass (Tipo A)**: Florece en la mañana como hembra, tarde como macho
• **Polinizadores (Tipo B)**: Fuerte, Zutano, Bacon

Diseño de polinización:
- 10-15% de árboles polinizadores
- Distribución uniforme en el huerto
- Distancia máxima: 20m entre A y B

**Portainjertos recomendados:**
• **Topa Topa**: Tolerante a *Phytophthora*, vigoroso
• **Dusa**: Alta productividad, resistencia a salinidad
• **Criollo antioqueño**: Adaptado a zonas colombianas

🌱 **1.5 Preparación del Terreno y Siembra**

**Meses antes:**
1. Análisis de suelo (enviar muestra a laboratorio)
2. Corrección de pH con cal dolomita (si pH <5.5)
3. Incorporar materia orgánica (10-15 kg/hoyo)

**Ahoyado:**
- Dimensiones: 60x60x60 cm (mínimo)
- Separar tierra superficial (fértil) de profunda
- Rellenar con mezcla: tierra+compost+superfosfato triple

**Trasplante:**
- Plantas de 6-12 meses (40-60cm altura)
- Bolsa de 5-10 litros
- Época: Inicio de lluvias
- Tutoreo obligatorio
- Mulch alrededor (10cm radio)

⚠️ **Errores comunes:**
- Enterrar el cuello de la planta (causa pudrición)
- No desinfectar herramientas (transmite enfermedades)
- Riego excesivo primeros meses (ahoga raíces)

✅ Actividad: Calcula cuántos árboles de Hass y polinizadores necesitas para 2 hectáreas con marco 6x6m''',
                    'duracion_dias': 7
                },
                {
                    'numero': 2,
                    'titulo': 'Nutrición y Manejo del Suelo',
                    'descripcion': 'Plan de fertilización y conservación de suelos',
                    'contenido': '''📚 MÓDULO 2: NUTRICIÓN Y MANEJO DEL SUELO

🥑 **2.1 Requerimientos Nutricionales**

Elementos principales por árbol/año:
• **Nitrógeno (N)**: 200-300 g (crecimiento, follaje)
• **Fósforo (P₂O₅)**: 50-100 g (raíces, floración)
• **Potasio (K₂O)**: 300-500 g (calidad de fruto)
• **Calcio (Ca)**: 150-200 g (estructura celular)
• **Magnesio (Mg)**: 40-60 g (fotosíntesis)
• **Boro (B)**: 2-5 g (floración, cuajado)
• **Zinc (Zn)**: 2-4 g (formación de frutos)

Proporción NPK ideal: **1:0.5:2**

📊 **2.2 Plan de Fertilización por Edad**

**Años 1-2 (Levante):**
- Objetivo: Formación de estructura
- 100-150g N / 50g P₂O₅ / 100-150g K₂O por árbol/año
- Aplicar cada 2 meses (6 aplicaciones/año)
- Fórmula: 10-20-20 o 15-15-15

**Años 3-4 (Preproducción):**
- Inicio de floración
- 150-200g N / 75g P₂O₅ / 200-250g K₂O
- Aplicar cada 2-3 meses
- Refuerzo con Ca y B (floración)

**Años 5+ (Producción):**
- Árbol adulto en plena producción
- 200-300g N / 100g P₂O₅ / 300-500g K₂O
- 4 aplicaciones/año
- Ajustar según análisis foliar y producción

📅 **2.3 Épocas de Aplicación**

Calendario estratégico:
• **Enero-Febrero**: Post-cosecha, preparación para floración (30%)
• **Abril-Mayo**: Cuajado de frutos (25%)
• **Julio-Agosto**: Llenado de frutos (25%)
• **Octubre**: Pre-cosecha (20%)

Aplicar en corona (50-100cm del tronco), no al pie

🍃 **2.4 Análisis Foliar**

Recomendado cada año:
• Muestra: 100 hojas maduras (3er-4to par, rama terminal)
• Época: 3-4 meses post-floración
• Laboratorio: Determina niveles nutricionales reales

Valores óptimos (% o ppm):
- N: 2.0-2.5%
- P: 0.08-0.25%
- K: 0.75-2.0%
- Ca: 1.0-3.0%
- Mg: 0.25-0.80%
- B: 50-100 ppm
- Zn: 30-150 ppm

💧 **2.5 Fertirrigación (Riego por Goteo)**

Ventajas:
• Fertilizante directo a raíz (eficiencia 90%)
• Menor dosis (diluida en agua)
• Aplicación frecuente (semanal)
• Reduce lixiviación
• Ahorra mano de obra

Dosis semanales (árbol adulto):
- Nitrato de potasio: 100g/semana
- MAP (fosfato monoamónico): 50g/semana
- Nitrato de calcio: 80g/semana
- Sulfato de magnesio: 30g/semana

🌿 **2.6 Manejo de Materia Orgánica**

Beneficios:
• Mejora estructura del suelo
• Aumenta retención de agua (20-30%)
• Favorece microbiología benéfica
• Libera nutrientes gradualmente
• Reduce compactación

Fuentes:
- Compost bien maduro: 10-20 kg/árbol/año
- Bocashi: 5-10 kg/árbol
- Lombricompuesto: 3-5 kg/árbol
- Mulch de poda: Cobertura en plato (5-10cm)

🌍 **2.7 Conservación de Suelos**

**Prácticas esenciales:**

**Coberturas vegetales:**
- Kudzú tropical (*Pueraria phaseoloides*)
- Maní forrajero (*Arachis pintoi*)
- Desmodium (*Desmodium ovalifolium*)
- Reducen erosión hasta 80%

**Control de arvenses:**
- Guadaña (no químicos cerca del tronco)
- Mantener 30-40cm altura (no erradicar totalmente)
- Evitar herbicidas de contacto (dañan raíces superficiales)

**Manejo de pendientes:**
- Terrazas individuales
- Canales de desviación
- Barreras vivas (vetiver, king grass)
- Siembra en curvas de nivel

⚠️ **2.8 Síntomas de Deficiencia Común**

Aprende a identificar:
• **N**: Amarillamiento generalizado, hojas pequeñas
• **P**: Hojas verde oscuro, crecimiento lento
• **K**: Necrosis en bordes y puntas de hojas, frutos pequeños
• **Ca**: Tip burn (quemazón de puntas), frutos blandos
• **B**: Frutos deformes, rajados, aborto de flores

✅ Actividad: Diseña un plan de fertilización anual para 1 hectárea de aguacate de 6 años (200 árboles)''',
                    'duracion_dias': 7
                },
                {
                    'numero': 3,
                    'titulo': 'Manejo Integrado de Plagas y Enfermedades',
                    'descripcion': 'Control de Phytophthora, trips y otras plagas',
                    'contenido': '''📚 MÓDULO 3: MANEJO INTEGRADO DE PLAGAS Y ENFERMEDADES

🦠 **3.1 Phytophthora cinnamomi** (Pudrición de Raíz)

La enfermedad más destructiva del aguacate:

**Síntomas:**
• Marchitez repentina (sin recuperación nocturna)
• Hojas amarillas que no caen
• Ramas secas progresivas
• Frutos pequeños, arrugados
• Raíces negras, sin raicillas

**Condiciones favorables:**
- Suelos pesados, mal drenados
- Exceso de riego o lluvias
- Temperaturas 20-30°C
- pH ácido (<5.5)

**Manejo integrado:**

1. **Preventivo (lo más importante):**
   - Portainjertos tolerantes (Dusa, Topa Topa)
   - Drenaje perfecto (nunca encharcamientos)
   - Evitar riego excesivo
   - No labrar cerca del árbol (no herir raíces)
   - Mulch orgánico (suprime patógeno)

2. **Cultural:**
   - Eliminar malezas hospedantes
   - No usar tierra de zonas infectadas
   - Desinfectar herramientas (amonio cuaternario)
   - Manejar escorrentía (canalizar agua)

3. **Químico (solo en emergencia):**
   - Fosetil aluminio: 3-5 g/L aplicado al suelo
   - Metalaxil: 2-3 g/L drench
   - Aplicar cada 3 meses en época lluvias
   - Rotar ingredientes activos

4. **Biológico:**
   - *Trichoderma harzianum*: 10g/árbol cada 4 meses
   - Compost de calidad (compite con patógeno)

⚠️ **Prevención > curación** (no hay cura efectiva una vez establecida)

🐛 **3.2 Trips** (*Frankliniella spp.*)

Insecto que daña frutos:

**Daño:**
• Raspado en piel del fruto (cicatrices)
• Deformaciones (frutos jorobados)
• Reducción de calidad exportable hasta 40%
• NO afecta pulpa (solo estética)

**Identificación:**
- Insectos pequeños (1-2mm), alargados
- Color amarillo-marrón
- Activos en flores y frutos pequeños

**Control IPM:**

1. **Monitoreo:**
   - Trampas adhesivas azules: 10-15 trampas/ha
   - Revisar flores semanalmente
   - Umbral: >5 trips/flor

2. **Control biológico:**
   - Ácaros depredadores (*Amblyseius* spp.)
   - Crisopas (*Chrysoperla* spp.)
   - Hongos entomopatógenos (*Beauveria*, *Metarhizium*)

3. **Control químico (último recurso):**
   - Spinosad: 0.5-1 ml/L (orgánico)
   - Abamectina: 0.5 ml/L
   - Alternar con azadiractina (neem): 3 ml/L
   - Aplicar en floración y fruto pequeño

4. **Prácticas culturales:**
   - Eliminar malezas (hospedan trips)
   - Riego por goteo (reduce población)
   - No aplicar insecticidas de amplio espectro (matan controladores)

🦋 **3.3 Barrenador del Tronco** (*Copturomimus perseae*)

**Síntomas:**
• Ramas que se quiebran con viento
• Aserrín en base de ramas
• Galerías en tronco y ramas
• Muerte de ramas

**Manejo:**
- Poda sanitaria (eliminar ramas afectadas)
- Aplicar insecticida en heridas de poda
- Trampa con feromonas (captura masiva)
- Evitar stress del árbol (riego, nutrición)

🐜 **3.4 Perforador del Fruto** (*Stenoma catenifer*)

**Daño:**
- Larvas perforan fruto
- Pudrición secundaria
- Caída prematura
- Fruto no comercializable

**Control:**
- Trampas de luz
- Bacillus thuringiensis (Bt): 1-2 g/L
- Recolectar frutos caídos (destruir larvas)
- Mantener limpio el huerto

🦟 **3.5 Ácaros** (*Oligonychus* spp.)

**Síntomas:**
- Bronceado de hojas
- Defoliación prematura
- Reducción de fotosíntesis

**Control:**
- Azufre mojable: 2-3 g/L
- Aceite mineral: 7-10 ml/L
- Abamectina: 0.5 ml/L
- Favorecer ácaros depredadores

🍂 **3.6 Antracnosis** (*Colletotrichum gloeosporioides*)

Enfermedad post-cosecha:

**Síntomas:**
- Manchas negras en fruto maduro
- Pudrición de pulpa
- Pérdidas en almacenamiento

**Prevención:**
- Cosechar con pedúnculo largo
- Evitar golpes y heridas
- Tratamiento post-cosecha con fungicida
- Almacenamiento a 5-7°C

**Aplicaciones preventivas:**
- Cobre: 2-3 g/L (pre-cosecha)
- Mancozeb: 2.5 g/L
- Azoxystrobin: 0.5 ml/L

🌱 **3.7 Manejo Agroecológico**

Estrategia holística:
• Biodiversidad funcional (flores, setos)
• Reducir monocultivo (intercalar)
• Conservar enemigos naturales
• Compost de calidad (microbioma benéfico)
• Nutrición balanceada (árboles sanos resisten)
• Eliminar químicos de amplio espectro

✅ Actividad: Diseña un programa MIP (6 meses) para controlar trips sin químicos sintéticos''',
                    'duracion_dias': 10
                },
                {
                    'numero': 4,
                    'titulo': 'Poda y Manejo del Dosel',
                    'descripcion': 'Técnicas de poda para optimizar producción',
                    'contenido': '''📚 MÓDULO 4: PODA Y MANEJO DEL DOSEL

✂️ **4.1 Importancia de la Poda en Aguacate**

Objetivos:
• Controlar altura (facilita cosecha <4m)
• Mejorar entrada de luz (fotosíntesis)
• Favorecer ventilación (reduce enfermedades)
• Renovar ramas productivas
• Aumentar calidad de frutos
• Facilitar aplicaciones fitosanitarias

Aguacate sin poda:
- Alcanza 10-15m altura
- Producción solo en copa alta (imposible cosechar)
- Frutos pequeños por falta de luz
- Mayor incidencia de plagas

🌳 **4.2 Tipos de Poda**

**Poda de formación (años 1-3):**
- Formar estructura de 3-4 ramas principales
- Altura del tronco: 60-80 cm
- Ángulo de ramas: 45-60° (evitar verticales)
- Eliminar chupones y ramas cruzadas
- Objetivo: Copa equilibrada, abierta

**Poda de mantenimiento (año 4+):**
- Controlar altura: 3.5-4.0 m
- Eliminar ramas secas, enfermas, entrecruzadas
- Aclarar centro (penetración luz)
- Renovar ramas viejas (>5 años)

**Poda de renovación (árboles viejos):**
- Cortes drásticos de rejuvenecimiento
- Reducir copa 40-50%
- Estimula brotación nueva
- Recupera productividad

**Poda sanitaria (todo el año):**
- Eliminar ramas con plagas/enfermedades
- Cortar y quemar (no compostar)
- Desinfectar herramientas

📅 **4.3 Épocas de Poda**

**Mejor época: Post-cosecha (Febrero-Marzo)**
- Árbol sin carga de frutos
- Antes de nueva floración
- Heridas cicatrizan rápido

Evitar podar:
- Durante floración (reduce cuajado)
- En lluvias intensas (entrada de patógenos)
- Con frutos pequeños (caída de frutos)

✂️ **4.4 Técnica de Poda Correcta**

Herramientas:
• Tijeras de mano (ramas <2cm)
• Tijeras de pértiga (ramas medias)
• Serrucho curvo (ramas gruesas)
• Motosierra (renovación)

**SIEMPRE desinfectadas** (amonio cuaternario, hipoclorito)

Tipo de cortes:
• Corte raso: Al ras de rama principal (no dejar muñones)
• Corte a yema: 0.5cm sobre yema (45°)
• No desgarrar corteza

🌿 **4.5 Manejo de Chupones**

Chupones = brotes verticales vigorosos:
- No producen frutos
- Consumen nutrientes
- Generan sombra

**Eliminarlos siempre:**
- Cuando están tiernos (fácil)
- Arrancar de base (no cortar)
- Si cortas, rebrotarán con más fuerza

☀️ **4.6 Manejo de Luz (Canopy)**

**Índice de Área Foliar (IAF) óptimo: 3.5-5.0**

Síntomas de exceso de sombra:
- Ramas delgadas, largas
- Hojas grandes, verde oscuro
- Poca floración interior
- Frutos pequeños

Solución:
- Poda de aclareo (eliminar 20-30% ramas interiores)
- Mejorar espaciamiento entre árboles
- Raleo de frutos (si necesario)

💧 **4.7 Poda y Riego**

Después de poda fuerte:
- Reducir riego 30-40%
- Árbol tiene menos follaje (menos transpiración)
- Evitar pudrición de raíz (*Phytophthora*)
- Reanudar riego normal cuando rebrote

🥑 **4.8 Poda y Producción Alternante**

Aguacate tiende a alternar (un año mucho, otro poco):

Manejo para regularizar:
- Raleo de frutos (quitar exceso en año "on")
- Dejar 1 fruto cada 30-40 hojas
- Poda moderada post-cosecha año "on"
- Fertilización balanceada

🛡️ **4.9 Cuidados Post-Poda**

1. **Sellar heridas grandes (>5cm):**
   - Pasta bordelesa
   - Pintura latex + fungicida
   - Evita entrada de patógenos

2. **Fertilizar después de poda:**
   - Estimula brotación
   - Nitrógeno (urea o sulfato de amonio)
   - 100-150g/árbol

3. **Monitorear plagas:**
   - Brotes tiernos atraen trips, ácaros
   - Aplicar preventivos si necesario

⚠️ **Errores comunes:**
- Podar en exceso (>40% copa)
- Dejar muñones (puerta de entrada patógenos)
- No desinfectar herramientas
- Podar durante floración

✅ Actividad: Dibuja un esquema de poda de formación para un aguacate de 2 años''',
                    'duracion_dias': 7
                },
                {
                    'numero': 5,
                    'titulo': 'Cosecha y Post-Cosecha',
                    'descripcion': 'Índices de madurez, cosecha y manejo post-cosecha',
                    'contenido': '''📚 MÓDULO 5: COSECHA Y POST-COSECHA

🥑 **5.1 Índices de Madurez**

El aguacate NO madura en el árbol, pero debe alcanzar **madurez fisiológica**:

**Indicadores obligatorios:**
• **Materia seca**: >23% (Hass exportación >21%)
• **Contenido de aceite**: >12%
• **Tiempo desde floración**: 8-10 meses (depende de clima)

**Métodos prácticos de campo:**

1. **Peso específico (gravedad):**
   - Fruto maduro: Densidad <1.0 (flota en agua)
   - Fruto inmaduro: Densidad >1.0 (se hunde)

2. **Cambio de color pedúnculo:**
   - Verde brillante → Verde amarillento (listo)

3. **Prueba de maduración:**
   - Cosechar fruto de prueba
   - Dejar 5-7 días a temperatura ambiente
   - Si madura uniformemente → listo para cosecha masiva
   - Si se arruga → inmaduro

⏰ **5.2 Épocas de Cosecha en Colombia**

Varía según altitud y región:
• **Zonas altas (2.400-2.600 msnm)**: Mayo-Agosto
• **Zonas medias (1.800-2.200 msnm)**: Marzo-Junio

Floración determina cosecha (8-10 meses después)

✋ **5.3 Técnica de Cosecha**

**Herramientas:**
• Tijera de cosecha (desinfectada)
• Garrocha con canasta (árboles altos)
• Escaleras (3-4m máximo)
• Canastos plásticos forrados

**Procedimiento correcto:**
1. Cortar con pedúnculo completo (3-5cm)
2. NO jalar (desprende piel)
3. NO dejar caer frutos (se golpean)
4. Colocar suavemente en canasto
5. Llevar a sombra inmediatamente

**Frutos a NO cosechar:**
- Golpeados o heridos
- Con manchas oscuras
- Muy pequeños (<120g Hass)
- Deformes

🏭 **5.4 Manejo Post-Cosecha en Finca**

**Centro de acopio:**
- Área techada, ventilada
- Temperatura fresca (15-18°C ideal)
- Piso lavable
- Agua potable disponible

**Proceso:**

1. **Recepción:**
   - Verificar ausencia de golpes
   - Descartar frutos dañados
   - Registro de lotes (trazabilidad)

2. **Lavado:**
   - Agua limpia + desinfectante (hipoclorito 50-100 ppm)
   - Elimina látex, polvo, esporas
   - Reduce carga microbiana

3. **Secado:**
   - Aire ambiente o ventilación forzada
   - Eliminar humedad superficial

4. **Selección y clasificación:**
   - Por peso/calibre
   - Por calidad (Extra, Primera, Segunda)

5. **Tratamiento fungicida (opcional):**
   - Inmersión en tiabendazol (0.5-1 g/L)
   - Previene antracnosis post-cosecha

6. **Encerado (exportación):**
   - Cera a base de carnauba
   - Reduce pérdida de agua
   - Mejora apariencia

📦 **5.5 Empaque y Embalaje**

**Empaque primario:**
• Cajas de cartón corrugado (4kg, 10kg)
• Con ventilación (orificios laterales)
• Etiqueta: Peso, calibre, lote, fecha, productor

**Clasificación por calibre (Hass):**
- Calibre 32: 180-220g
- Calibre 26: 220-260g
- Calibre 22: 260-300g
- Calibre 18: 300-350g

Mercado prefiere calibres 22-26

❄️ **5.6 Almacenamiento y Transporte**

**Cadena de frío:**
• **Temperatura**: 5-7°C
• **Humedad relativa**: 85-90%
• **Tiempo**: 2-4 semanas

⚠️ Evitar:
- Temperaturas <5°C (daño por frío)
- Temperaturas >10°C (maduración rápida)
- Almacenar con manzanas/plátanos (etileno acelera maduración)

**Transporte refrigerado:**
- Camiones refrigerados
- Contenedores reefer (exportación)
- Temperatura constante 5-7°C
- Registro de temperatura (trazabilidad)

🌍 **5.7 Maduración Controlada**

Para mercado local:
• Cámaras de maduración (20-25°C)
• Aplicación de etileno (100 ppm, 24h)
• Maduración en 3-5 días
• Control diario de firmeza

Punto óptimo consumo:
- Firmeza 2-4 kg (penetrómetro)
- Piel empieza a ceder al tacto

💰 **5.8 Canales de Comercialización**

**Exportación (mejor precio):**
- Requiere certificaciones (Global GAP, USDA)
- Trazabilidad completa
- Empacadora certificada
- Precio: $4.000-6.000/kg

**Mercado nacional:**
- Centrales de abastos
- Supermercados (Premium)
- Industria (pulpa, aceite)
- Precio: $2.500-4.000/kg

**Valor agregado:**
- Pulpa congelada
- Guacamole
- Aceite de aguacate
- Harina de semilla

📊 **5.9 Rendimiento y Rentabilidad**

Producción estimada (Hass):
• Año 3: 3-5 ton/ha
• Año 5: 10-15 ton/ha
• Año 8+: 20-25 ton/ha (pico productivo)

Costos producción/ha (año 8):
• Fertilización: $2.5 M
• Fitosanitarios: $1.5 M
• Poda: $800k
• Cosecha: $2.0 M
• Riego: $1.0 M
• Otros: $1.2 M
**Total: $9.0 M/ha**

Ingresos (20 ton/ha × $3.500/kg):
**$70 M/ha**

**Margen neto: $61 M/ha**

ROI excelente después de año 5

🎯 **5.10 Claves del Éxito Post-Cosecha**

1. Cosechar en madurez fisiológica correcta
2. Manejo cuidadoso (sin golpes)
3. Cadena de frío ininterrumpida
4. Clasificación rigurosa
5. Trazabilidad completa
6. Cumplir normas de calidad e inocuidad

✅ Actividad Final: Calcula los ingresos proyectados de 2 hectáreas de aguacate Hass en año 6 (15 ton/ha)

🎓 **¡FELICITACIONES!**
Has completado el curso de Aguacate Hass: Producción Comercial.

Ahora estás listo para:
✅ Establecer un huerto productivo y rentable
✅ Manejar la nutrición y sanidad del cultivo
✅ Controlar plagas y enfermedades
✅ Realizar cosecha y post-cosecha de calidad
✅ Acceder a mercados Premium y exportación

Recuerda tomar el examen final para obtener tu certificado de eki.''',
                    'duracion_dias': 10
                }
            ]
            
            for modulo_data in modulos_aguacate:
                Modulo.objects.create(curso=aguacate_curso, **modulo_data)
            
            self.stdout.write(self.style.SUCCESS(f'  ✅ {len(modulos_aguacate)} módulos creados para Aguacate'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  El curso {aguacate_curso} ya existía'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ ¡Cursos profesionales creados exitosamente!'))
        self.stdout.write(self.style.SUCCESS('Ahora puedes inscribirte vía WhatsApp escribiendo "ver cursos"'))
