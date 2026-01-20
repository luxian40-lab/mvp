"""
Configurar sistema de gamificación motivador y agregar curso de Cacao
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo
from core.gamificacion import Badge

print("🎮 CONFIGURANDO SISTEMA DE GAMIFICACIÓN MOTIVADOR\n")
print("=" * 60)

# ==================== CREAR BADGES MOTIVADORES ====================

badges_config = [
    # BADGES DE NIVEL
    {'nombre': 'Semilla 🌱', 'tipo': 'NIVEL', 'nivel_requerido': 1, 'icono': '🌱', 
     'descripcion': '¡Comenzaste tu camino! Primer módulo completado', 'puntos_bonus': 10},
    
    {'nombre': 'Brote 🌿', 'tipo': 'NIVEL', 'nivel_requerido': 2, 'icono': '🌿', 
     'descripcion': 'Estás creciendo. 2 módulos completados', 'puntos_bonus': 20},
    
    {'nombre': 'Planta Joven 🍃', 'tipo': 'NIVEL', 'nivel_requerido': 3, 'icono': '🍃', 
     'descripcion': '¡Primer curso completo! Vas por buen camino', 'puntos_bonus': 50},
    
    {'nombre': 'Cultivo Establecido 🌾', 'tipo': 'NIVEL', 'nivel_requerido': 4, 'icono': '🌾', 
     'descripcion': 'Tu conocimiento florece. Nivel intermedio', 'puntos_bonus': 75},
    
    {'nombre': 'Árbol Fuerte 🌳', 'tipo': 'NIVEL', 'nivel_requerido': 5, 'icono': '🌳', 
     'descripcion': 'Conocimiento sólido. ¡Eres un experto!', 'puntos_bonus': 100},
    
    {'nombre': 'Bosque Sabio 🌲', 'tipo': 'NIVEL', 'nivel_requerido': 6, 'icono': '🌲', 
     'descripcion': 'Nivel avanzado. Compartes tu sabiduría', 'puntos_bonus': 150},
    
    {'nombre': 'Maestro del Campo 🎋', 'tipo': 'NIVEL', 'nivel_requerido': 7, 'icono': '🎋', 
     'descripcion': 'Dominio completo. Eres un maestro', 'puntos_bonus': 200},
    
    {'nombre': 'Flor de Loto 🌺', 'tipo': 'NIVEL', 'nivel_requerido': 8, 'icono': '🌺', 
     'descripcion': 'Excelencia pura. Inspiras a otros', 'puntos_bonus': 300},
    
    {'nombre': 'Diamante Verde 💎', 'tipo': 'NIVEL', 'nivel_requerido': 9, 'icono': '💎', 
     'descripcion': 'Élite agrícola. Rareza excepcional', 'puntos_bonus': 500},
    
    {'nombre': 'Corona de Oro 👑', 'tipo': 'NIVEL', 'nivel_requerido': 10, 'icono': '👑', 
     'descripcion': '¡NIVEL MÁXIMO! Leyenda del agro colombiano', 'puntos_bonus': 1000},
    
    # BADGES DE RACHA
    {'nombre': 'Fuego Inicial 🔥', 'tipo': 'RACHA', 'valor_requerido': 3, 'icono': '🔥', 
     'descripcion': '3 días consecutivos de aprendizaje', 'puntos_bonus': 30},
    
    {'nombre': 'Llamarada 🔥🔥', 'tipo': 'RACHA', 'valor_requerido': 7, 'icono': '🔥🔥', 
     'descripcion': '¡Una semana completa sin fallar!', 'puntos_bonus': 100},
    
    {'nombre': 'Incendio Forestal 🔥🔥🔥', 'tipo': 'RACHA', 'valor_requerido': 14, 'icono': '🔥🔥🔥', 
     'descripcion': '2 semanas de constancia total', 'puntos_bonus': 250},
    
    {'nombre': 'Volcán Activo 🌋', 'tipo': 'RACHA', 'valor_requerido': 21, 'icono': '🌋', 
     'descripcion': '3 semanas imparables. ¡Increíble!', 'puntos_bonus': 400},
    
    {'nombre': 'Sol Eterno ☀️', 'tipo': 'RACHA', 'valor_requerido': 30, 'icono': '☀️', 
     'descripcion': '¡UN MES COMPLETO! Dedicación ejemplar', 'puntos_bonus': 700},
    
    # BADGES ESPECIALES
    {'nombre': 'Cafetero Experto ☕', 'tipo': 'ESPECIAL', 'icono': '☕', 
     'descripcion': 'Completaste el curso de Café con excelencia', 'puntos_bonus': 200},
    
    {'nombre': 'Maestro del Aguacate 🥑', 'tipo': 'ESPECIAL', 'icono': '🥑', 
     'descripcion': 'Dominaste la producción de Aguacate Hass', 'puntos_bonus': 200},
    
    {'nombre': 'Rey del Plátano 🍌', 'tipo': 'ESPECIAL', 'icono': '🍌', 
     'descripcion': 'Experto en cultivo de Plátano Hartón', 'puntos_bonus': 200},
    
    {'nombre': 'Chocolatero Maestro 🍫', 'tipo': 'ESPECIAL', 'icono': '🍫', 
     'descripcion': 'Maestría en el cultivo de Cacao Fino', 'puntos_bonus': 200},
    
    {'nombre': 'Coleccionista de Conocimiento 📚', 'tipo': 'ESPECIAL', 'icono': '📚', 
     'descripcion': 'Completaste TODOS los cursos disponibles', 'puntos_bonus': 1000, 'es_secreto': True},
    
    {'nombre': 'Madrugador 🌅', 'tipo': 'PARTICIPACION', 'icono': '🌅', 
     'descripcion': 'Estudiaste antes de las 6:00 AM', 'puntos_bonus': 50, 'es_secreto': True},
    
    {'nombre': 'Búho Nocturno 🦉', 'tipo': 'PARTICIPACION', 'icono': '🦉', 
     'descripcion': 'Estudiaste después de las 10:00 PM', 'puntos_bonus': 50, 'es_secreto': True},
    
    {'nombre': 'Rayo Veloz ⚡', 'tipo': 'PARTICIPACION', 'icono': '⚡', 
     'descripcion': 'Completaste un módulo en menos de 30 minutos', 'puntos_bonus': 100, 'es_secreto': True},
]

print("\n🏆 Creando badges motivadores...")
badges_creados = 0
badges_existentes = 0

for idx, badge_data in enumerate(badges_config, 1):
    badge, created = Badge.objects.get_or_create(
        nombre=badge_data['nombre'],
        defaults={
            'descripcion': badge_data['descripcion'],
            'icono': badge_data['icono'],
            'tipo': badge_data['tipo'],
            'puntos_bonus': badge_data.get('puntos_bonus', 0),
            'es_secreto': badge_data.get('es_secreto', False),
            'nivel_requerido': badge_data.get('nivel_requerido'),
            'valor_requerido': badge_data.get('valor_requerido'),
            'orden': idx,
            'activo': True
        }
    )
    
    if created:
        badges_creados += 1
        print(f"   ✅ {badge.icono} {badge.nombre}")
    else:
        badges_existentes += 1

print(f"\n📊 Resultado: {badges_creados} nuevos, {badges_existentes} ya existían")

# ==================== CREAR CURSO DE CACAO ====================

print("\n" + "=" * 60)
print("\n🍫 CREANDO CURSO DE CACAO FINO...\n")

curso_cacao, created = Curso.objects.get_or_create(
    nombre="Cultivo de Cacao Fino",
    defaults={
        'descripcion': 'Aprende a cultivar cacao fino de aroma, desde la siembra hasta la cosecha y fermentación. Conviértete en un cacaocultor experto y accede a mercados premium.',
        'emoji': '🍫',
        'duracion_semanas': 6,
        'orden': 4,
        'activo': True
    }
)

if created:
    print(f"✅ Curso creado: {curso_cacao.emoji} {curso_cacao.nombre}")
    
    # Crear módulos del curso
    modulos = [
        {
            'numero': 1,
            'titulo': 'Introducción al Cacao Fino',
            'contenido': '''🍫 BIENVENIDO AL MUNDO DEL CACAO

El cacao (Theobroma cacao) significa "alimento de los dioses". Es uno de los cultivos más nobles y rentables de Colombia.

🌍 ¿POR QUÉ CACAO FINO?

Colombia produce cacao fino de aroma, el más valorado del mundo:
• Solo 5% de la producción mundial
• Precio premium: 30-50% más que cacao común
• Demanda creciente en chocolatería gourmet

📍 CONDICIONES IDEALES:

🌡️ Clima:
• Temperatura: 24-28°C constante
• Altitud: 0-800 msnm
• Lluvia: 1,500-2,500 mm/año bien distribuida
• Humedad relativa: 70-80%

🌳 Suelo:
• Profundo (mínimo 1.5 m)
• Bien drenado
• Rico en materia orgánica
• pH: 5.5 - 7.0

💰 RENTABILIDAD:

Una hectárea bien manejada produce:
• 800-1,200 kg de cacao seco/año
• Precio cacao fino: $9,000-12,000/kg
• Ingreso potencial: $7-14 millones/ha/año
• Primera cosecha: Año 3
• Vida productiva: 25-30 años

🎯 EN ESTE CURSO APRENDERÁS:

✅ Establecer tu cacaotal técnicamente
✅ Manejo agronómico profesional
✅ Control de plagas y enfermedades
✅ Cosecha y beneficio para calidad premium
✅ Comercialización a mercados especiales''',
            'duracion_minutos': 40
        },
        {
            'numero': 2,
            'titulo': 'Establecimiento del Cacaotal',
            'contenido': '''🌱 ESTABLECIMIENTO PROFESIONAL

PASO 1: SELECCIÓN DEL LOTE

Evalúa tu terreno:
✅ Historial: Sin erosión ni compactación
✅ Topografía: Plano o pendiente suave (<30%)
✅ Agua: Disponible para riego en verano
✅ Acceso: Camino para transporte

PASO 2: ANÁLISIS DE SUELO

Antes de invertir, haz análisis químico:
• pH, materia orgánica
• NPK, calcio, magnesio
• Micronutrientes
• Costo: $80,000-150,000

PASO 3: DISEÑO DEL SISTEMA AGROFORESTAL

El cacao NECESITA sombra. Diseña en 3 estratos:

🌳 Estrato Alto (15-20m):
• Nogal cafetero, guamo
• Distancia: 12x12m

🌿 Estrato Medio (5-10m):
• Plátano, cítricos
• Sombra temporal primer año

🍫 Estrato Bajo (3-4m):
• CACAO
• Distancia: 3x3 metros = 1,111 plantas/ha

PASO 4: PREPARACIÓN Y SIEMBRA

1. Trazado con cuerdas y estacas
2. Ahoyado: 40x40x40 cm
3. Mezclar suelo con:
   - 5 kg materia orgánica
   - 100 g roca fosfórica
   - 50 g cal dolomita

4. Siembra:
   - Época: Inicio de lluvias (Abril-Mayo)
   - Material: Plántulas injertadas 6 meses
   - Plantar al mismo nivel del cuello
   - Regar 5 litros inmediatamente

PASO 5: ESTABLECER SOMBRA

Mes 0: Sembrar plátano (sombra temporal)
Mes 6: Sembrar cacao
Mes 12: Sembrar árboles permanentes
Año 3: Eliminar plátano gradualmente''',
            'duracion_minutos': 50
        },
        {
            'numero': 3,
            'titulo': 'Manejo y Podas del Cacao',
            'contenido': '''✂️ PODAS PARA MÁXIMA PRODUCCIÓN

¿POR QUÉ PODAR?

• Más luz = Más flores = Más mazorcas
• Previene enfermedades (mejor ventilación)
• Facilita cosecha
• Alarga vida productiva

🌳 FORMACIÓN DEL ÁRBOL (Años 1-2)

Objetivo: Árbol de 3-4 pisos

1. Seleccionar 3-5 ramas principales
   - A 1.5m de altura (jorqueta)
   - Distribuidas uniformemente
   - Ángulo 45° respecto al tronco

2. Eliminar:
   - Ramas hacia abajo
   - Chupones del tronco
   - Ramas cruzadas

🔪 PODA DE MANTENIMIENTO (Anual)

Hacer en época seca (Diciembre-Febrero):

✂️ Eliminar 4 "C":
• Chupones (brotes del tronco)
• Cruzadas (ramas que se entrecruzan)
• Colgantes (ramas hacia abajo)
• Cercanas (muy juntas)

✂️ Eliminar:
• Ramas secas y enfermas
• Frutos momificados
• Plantas parásitas (muérdago)

🌿 PODA SANITARIA (Mensual)

Revisión rápida cada mes:
• Cortar brotes de tronco
• Eliminar mazorcas enfermas
• Retirar material del cacaotal

⚙️ HERRAMIENTAS:

• Tijera de podar (desinfectada)
• Serrucho curvo
• Pértiga podadora (altura)
• Hipoclorito 10% (desinfección)

💡 REGLA DE ORO:

"Un cacaotal bien podado permite que una persona camine entre los árboles y vea el cielo"

📊 INDICADORES:

✅ Buena poda:
• Luz entra al interior
• Ramas espaciadas
• Fácil acceso para cosechar

❌ Mala poda:
• Cacaotal oscuro
• Muchas ramas secas
• Mazorcas con hongos''',
            'duracion_minutos': 45
        },
        {
            'numero': 4,
            'titulo': 'Fertilización del Cacao',
            'contenido': '''🌿 NUTRICIÓN PARA ALTA PRODUCCIÓN

El cacao es exigente en nutrientes. Una fertilización técnica aumenta tu producción 40-60%.

📊 REQUERIMIENTOS NUTRICIONALES

Por hectárea/año en producción:
• Nitrógeno (N): 80-120 kg
• Fósforo (P2O5): 40-60 kg  
• Potasio (K2O): 100-150 kg
• Calcio (Ca): 60-80 kg
• Magnesio (Mg): 30-40 kg

🗓️ PLAN DE FERTILIZACIÓN

AÑO 1-2 (Establecimiento):

Aplicación cada 3 meses:
• 50-80g NPK 17-6-18-2 / planta
• 30g úrea (adicional)
• 3-5 kg compost/planta

AÑO 3+ (Producción plena):

3 aplicaciones/año:

1️⃣ INICIO DE LLUVIAS (Marzo-Abril):
   • 150g NPK 15-5-20 / planta
   • 50g sulfato de magnesio
   • Estimula floración

2️⃣ MITAD DE LLUVIAS (Julio):
   • 150g NPK 10-20-20 / planta  
   • Desarrollo de frutos

3️⃣ FINAL DE LLUVIAS (Octubre):
   • 100g NPK 12-12-17-2 / planta
   • Preparación para próxima cosecha

🍂 MATERIA ORGÁNICA (Fundamental)

Aplicar 2 veces/año:
• 10-15 kg compost maduro/planta
• O 5 kg lombricompost
• Mejora estructura del suelo
• Aumenta vida microbiana

♻️ ABONO DEL MISMO CACAO:

Aprovecha los residuos:

🍌 Cáscaras de mazorca:
• Picar y esparcir en plantación
• Aporta K, Ca, Mg
• 60-80% del peso del fruto

🍃 Hojarasca:
• Dejar bajo los árboles
• Mantillo natural
• Conserva humedad

✅ FORMA CORRECTA DE APLICAR:

1. Hacer corona de 30-50cm del tronco
2. Aplicar fertilizante uniformemente
3. Incorporar ligeramente (3-5cm)
4. NO dejar sobre raíces expuestas
5. Aplicar cuando hay humedad

⚠️ ERRORES COMUNES:

❌ Fertilizar en verano sin agua
❌ Aplicar en el tronco (quema)
❌ No incorporar al suelo
❌ Dosis excesivas (contamina)

🎯 RESULTADO ESPERADO:

Con buena fertilización:
• Más flores y frutos
• Mazorcas más grandes
• Mejor calidad de grano
• Mayor rentabilidad''',
            'duracion_minutos': 50
        },
        {
            'numero': 5,
            'titulo': 'Cosecha y Beneficio Premium',
            'contenido': '''📦 COSECHA Y BENEFICIO PARA CALIDAD PREMIUM

El 80% de la calidad del chocolate se define en beneficio. Aquí está tu diferenciación.

🔍 PUNTO ÓPTIMO DE COSECHA

Indicadores de madurez:

✅ Color:
• Criollo: Rojo-naranja intenso
• Trinitario: Amarillo brillante

✅ Sonido:
• Golpear suavemente
• Sonido hueco = Granos sueltos

✅ Tiempo:
• 5-6 meses desde floración
• Cosechar cada 15 días

🔪 TÉCNICA DE CORTE:

1. Usar machete afilado o tijera
2. Cortar pedúnculo (no jalar)
3. NO golpear tronco ni ramas
4. Cuidar cojines florales
5. Separar mazorcas sanas de enfermas

⚠️ NUNCA cosechar:
• Mazorcas verdes (inmaduras)
• Mazorcas enfermas (monilia, fitóftora)
• Frutos dañados o perforados

⚙️ BENEFICIO - PROCESO CRÍTICO

PASO 1: QUIEBRA Y DESGRANE (Mismo día)

• Partir con mazo de madera
• Extraer granos con placenta
• Eliminar granos:
  - Planos (sin desarrollar)
  - Germinados
  - Con moho

🔥 PASO 2: FERMENTACIÓN (5-7 días)

¡El paso más importante!

Equipo:
• Cajones de madera con drenaje
• Sacos limpios o hojas de plátano
• Termómetro

Proceso:

Día 1-2:
• Llenar cajón 40-50cm
• Cubrir con hojas de plátano
• Temp: 38-40°C
• NO voltear aún

Día 3:
• PRIMER VOLTEO
• Temp: 45-48°C
• Olor a vinagre (normal)

Día 4-5:
• Voltear diariamente
• Temp: 48-50°C
• Color cambia a marrón

Día 6-7:
• Olor a chocolate emerge
• Grano quebradizo
• Listo para secar

✅ Fermentación correcta:
• Grano completamente marrón
• Grietas superficiales
• Aroma a chocolate
• Sabor menos amargo

☀️ PASO 3: SECADO (5-7 días)

Objetivo: 7% humedad final

Métodos:

1. Solar (preferido):
   • Tendales limpios
   • Capa de 3-5cm
   • Remover cada hora
   • 6-8 horas/día
   • Proteger de lluvia

2. Artificial:
   • Secador a 50-60°C máximo
   • Flujo de aire constante
   • Más rápido pero costoso

📊 PASO 4: CLASIFICACIÓN

Separar:
✅ Primera calidad (80%):
   • Fermentados
   • Sin defectos
   • Tamaño uniforme

⚠️ Segunda calidad (15%):
   • Ligeramente defectuosos
   • Para mercado común

❌ Descartar (5%):
   • Mohosos, partidos, insectos

📦 PASO 5: EMPAQUE Y ALMACENAMIENTO

• Sacos de fique o yute (50kg)
• Bodega seca y ventilada
• Sobre estibas (no en suelo)
• Humedad ambiente <70%

💰 CERTIFICACIÓN Y MERCADO:

Para precio premium conseguir:
✅ Certificación Orgánica
✅ Fair Trade
✅ Rainforest Alliance
✅ Trazabilidad completa

🎯 CALIDAD = DINERO:

Cacao común: $8,000/kg
Cacao fino bien beneficiado: $12,000/kg
Diferencia: +50% de ingreso

¡El beneficio correcto transforma tu negocio!''',
            'duracion_minutos': 60
        }
    ]
    
    print(f"\n📚 Creando {len(modulos)} módulos...")
    for mod_data in modulos:
        # Remover campo que no existe en el modelo
        duracion = mod_data.pop('duracion_minutos', None)
        Modulo.objects.create(
            curso=curso_cacao,
            **mod_data
        )
        print(f"   ✅ Módulo {mod_data['numero']}: {mod_data['titulo']}")
    
    print(f"\n✅ Curso completo: {len(modulos)} módulos creados")
else:
    print(f"ℹ️ El curso ya existía")

# ==================== RESUMEN FINAL ====================

print("\n" + "=" * 60)
print("\n🎉 CONFIGURACIÓN COMPLETADA")
print("\n📚 CURSOS FINALES DIVERSOS:\n")

cursos = Curso.objects.filter(activo=True).order_by('orden')
for idx, c in enumerate(cursos, 1):
    modulos_count = c.modulos.count()
    print(f"   {idx}. {c.emoji} {c.nombre} ({modulos_count} módulos)")

print(f"\n🏆 Total de Badges: {Badge.objects.count()}")
print("\n✅ Sistema de gamificación optimizado y motivador")
print("✅ 4 cursos diversos y profesionales")
print("✅ Niveles más alcanzables")
print("✅ Recompensas más generosas")
print("\n🚀 ¡LISTO PARA IMPRESIONAR!")
print("\n" + "=" * 60)
