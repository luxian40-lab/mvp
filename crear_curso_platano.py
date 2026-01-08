"""
Script para crear curso de Plátano Hartón
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo

# Crear curso
curso, created = Curso.objects.get_or_create(
    nombre="Cultivo de Plátano Hartón",
    defaults={
        'descripcion': "Aprende técnicas modernas para cultivar plátano hartón de alta calidad en Colombia",
        'duracion_semanas': 5,
        'emoji': '🍌',
        'orden': 3
    }
)

if created:
    print(f"✅ Curso creado: {curso.nombre}")
else:
    print(f"ℹ️ Curso ya existía: {curso.nombre}")

# Módulos del curso
modulos = [
    {
        'numero': 1,
        'titulo': 'Selección de Material de Siembra',
        'descripcion': 'Cómo elegir los mejores colinos para sembrar',
        'contenido': """🍌 **SELECCIÓN DE MATERIAL DE SIEMBRA**

📋 **¿Qué es un colino?**
Es la planta hija que nace del plátano madre. Usamos colinos para sembrar nuevas plantas.

✅ **Características de un buen colino:**
• Altura: 40-60 cm
• Hojas: 4-6 hojas verdes y sanas
• Raíces: Blancas y abundantes
• Sin daños: Libre de plagas y enfermedades
• Edad: 2-3 meses desde que brotó

❌ **NO uses colinos que:**
• Tengan hojas amarillas o secas
• Presenten picaduras de insectos
• Tengan raíces negras o podridas
• Sean muy pequeños (menos de 30 cm)

💡 **Consejo:**
Saca los colinos en horas de la mañana cuando hay menos sol. Así la planta sufre menos estrés.

🔍 **Preparación antes de sembrar:**
1. Limpiar el colino (quitar tierra suelta)
2. Cortar hojas dejando solo 2-3
3. Desinfectar con agua + cal (1 kg cal x 20 litros agua)
4. Dejar secar 2-3 horas a la sombra

⏱️ **Tiempo:** Sembrar máximo 24 horas después de sacar el colino""",
        'duracion_dias': 3
    },
    {
        'numero': 2,
        'titulo': 'Preparación del Terreno',
        'descripcion': 'Cómo preparar la tierra para sembrar plátano',
        'contenido': """🍌 **PREPARACIÓN DEL TERRENO**

📍 **1. Elección del lote:**
• Suelo profundo (más de 1 metro)
• Buen drenaje (no se encharque)
• pH entre 5.5 y 7.0
• Acceso a agua
• Evitar zonas muy ventosas

🔧 **2. Limpieza del terreno:**
• Quitar malezas, piedras y raíces viejas
• Si hay cultivo anterior, dejar descansar 2-3 meses
• No quemar - mejor incorporar materia orgánica

📐 **3. Trazado:**
Distancia de siembra recomendada:
• Sistema cuadrado: 3m x 3m (1,111 plantas/ha)
• Sistema triangular: 3m x 3m (1,280 plantas/ha)
• Alta densidad: 2.5m x 2.5m (1,600 plantas/ha)

⛏️ **4. Ahoyado (hacer huecos):**
• Tamaño: 40cm x 40cm x 40cm
• Hacer con 15-30 días de anticipación
• Separar tierra superficial (negra) de la profunda

🌱 **5. Preparación del hoyo:**
Mezclar en cada hoyo:
• Tierra superficial
• 5-10 kg de abono orgánico (gallinaza o compost)
• 100g de cal dolomita (si suelo ácido)
• 50g de fertilizante completo (10-30-10)

⏱️ **Tiempo:** Dejar reposar 7 días antes de sembrar""",
        'duracion_dias': 5
    },
    {
        'numero': 3,
        'titulo': 'Siembra y Establecimiento',
        'descripcion': 'Técnica correcta para sembrar plátano',
        'contenido': """🍌 **SIEMBRA Y ESTABLECIMIENTO**

📅 **Mejor época para sembrar:**
• Inicio de lluvias (abril-mayo o septiembre-octubre)
• Evitar época seca o muy lluviosa
• Si tienes riego, puedes sembrar todo el año

🌱 **Proceso de siembra:**

1️⃣ **Colocación del colino:**
   • Ponerlo vertical en el centro del hoyo
   • Enterrar hasta el nacimiento de las raíces (10-15 cm)
   • NO enterrar muy profundo

2️⃣ **Llenado del hoyo:**
   • Rellenar con la mezcla preparada
   • Apisonar suavemente alrededor
   • Dejar ligera depresión para riego

3️⃣ **Riego inicial:**
   • Dar 10-15 litros de agua
   • Regar cada 3 días primeras 2 semanas
   • Luego cada semana según lluvia

💧 **Necesidades de agua:**
• Primeros 3 meses: Riego cada semana
• Meses 4-6: Cada 10-15 días
• Después de 6 meses: Solo en sequía
• Evitar encharcamientos

🛡️ **Protección inicial:**
• Poner tutor (palo) si hay viento
• Limpiar malezas en círculo de 1 metro
• Mulch (hojarasca) alrededor para conservar humedad

✅ **Señales de buen establecimiento (2-3 semanas):**
• Sale hoja nueva
• Color verde intenso
• Planta firme

⏱️ **Tiempo al primer corte:** 10-12 meses""",
        'duracion_dias': 4
    },
    {
        'numero': 4,
        'titulo': 'Manejo de Plagas y Enfermedades',
        'descripcion': 'Control de problemas comunes en plátano',
        'contenido': """🍌 **MANEJO DE PLAGAS Y ENFERMEDADES**

🐛 **PLAGAS PRINCIPALES:**

1. **Picudo Negro** (el más dañino)
   • Qué es: Gorgojo que perfora el tallo
   • Síntomas: Hojas amarillas, planta se dobla
   • Control:
     - Usar colinos sanos
     - Trampas con fruta fermentada
     - Aplicar Beauveria bassiana (hongo)
     - Eliminar plantas afectadas

2. **Nematodos**
   • Qué son: Gusanos microscópicos en raíces
   • Síntomas: Raíces negras, planta débil
   • Control:
     - Rotar con maíz o frijol
     - Aplicar materia orgánica
     - Usar colinos limpios

🦠 **ENFERMEDADES PRINCIPALES:**

1. **Sigatoka Negra** (manchas en hojas)
   • Síntomas: Rayas negras en hojas
   • Control:
     - Deshoje (quitar hojas enfermas)
     - Buen drenaje
     - Fungicidas si es grave
     - Variedades resistentes

2. **Moko** (bacteria - muy grave)
   • Síntomas: Hojas amarillas de adentro hacia afuera
   • Control:
     - Desinfectar herramientas
     - Eliminar plantas infectadas
     - Cuarentena del lote

🌿 **CONTROL CULTURAL:**
• Deshierbe cada 2 meses
• Deshije (dejar solo 1 hijo por planta)
• Deshoje (quitar hojas secas)
• Desguasque (quitar calcetas secas del tallo)

🧪 **Productos orgánicos:**
• Caldo bordelés (cobre + cal)
• Extracto de ajo y ají
• Purín de ortiga

⏱️ **Frecuencia de revisión:** Cada 15 días""",
        'duracion_dias': 5
    },
    {
        'numero': 5,
        'titulo': 'Fertilización',
        'descripcion': 'Nutrición del cultivo de plátano',
        'contenido': """🍌 **FERTILIZACIÓN DEL PLÁTANO**

🌱 **Requerimientos nutricionales:**
El plátano consume mucho potasio (K) para formar el racimo.

📊 **Nutrientes principales:**
• Nitrógeno (N): Crecimiento de hojas
• Fósforo (P): Desarrollo de raíces
• Potasio (K): Tamaño y calidad del racimo

📅 **Programa de fertilización:**

**1ra aplicación (mes 1):**
• 100g 10-30-10 por planta
• 5 kg compost

**2da aplicación (mes 3):**
• 150g Urea (N)
• 100g KCl (K)

**3ra aplicación (mes 5):**
• 200g 17-6-18-2 (N-P-K-Mg)

**4ta aplicación (mes 8):**
• 200g KCl
• 100g Urea

🌿 **Fertilización orgánica:**
• Cada 3 meses: 10 kg compost por planta
• Gallinaza: 5 kg cada 2 meses
• Bocashi: 3 kg cada 2 meses

📍 **Forma de aplicar:**
• En corona (círculo) a 30-40 cm del tallo
• Incorporar ligeramente con azadón
• Aplicar sobre suelo húmedo
• Tapar con tierra

💧 **Fertirriego (si tienes riego):**
• Semana 1: Solo agua
• Semanas 2-4: Urea (5g/litro) 
• Repetir mensual

✅ **Señales de buena nutrición:**
• Hojas verde oscuro
• Crecimiento rápido
• Racimos grandes

❌ **Deficiencias comunes:**
• Hojas amarillas: Falta nitrógeno
• Bordes quemados: Falta potasio
• Crecimiento lento: Falta fósforo

⏱️ **Total fertilizante año 1:** ~800g químico + 40kg orgánico por planta""",
        'duracion_dias': 4
    },
    {
        'numero': 6,
        'titulo': 'Cosecha y Poscosecha',
        'descripcion': 'Cuándo y cómo cosechar el plátano',
        'contenido': """🍌 **COSECHA Y POSCOSECHA**

⏱️ **¿Cuándo cosechar?**

**Plátano hartón:**
• 10-12 meses después de la siembra
• 12-14 semanas después de salir la bellota (flor)

📏 **Señales de madurez fisiológica:**
• Dedos llenos (se ven redondos, no angulosos)
• Dedos del centro han perdido aristas
• Cambio de color: Verde oscuro a verde claro
• Se pueden ver líneas oscuras en la cáscara

🔪 **Técnica de corte:**

1. **Preparación:**
   • Limpiar machete con alcohol
   • Tener lista esponja acolchada
   • No cosechar con lluvia

2. **Corte del racimo:**
   • Persona 1: Sostiene el racimo con esponja
   • Persona 2: Corta con machete limpio
   • Dejar 30-40 cm de raquis (tallo del racimo)

3. **Manejo del racimo:**
   • NO tirarlo al suelo
   • Transportar en hombro con esponja
   • Llevar a sombra inmediatamente

📦 **Poscosecha:**

**1. Desbellote:**
• Quitar la bellota (flor seca)
• Cortar recto

**2. Desleche:**
• Colgar racimo 30 minutos
• Dejar escurrir látex (leche)

**3. Desmane:**
• Separar manos (gajos)
• Usar cuchillo desinfectado

**4. Lavado:**
• Agua limpia
• Eliminar látex restante
• Secar al aire

**5. Empaque:**
• Cajas plásticas limpias
• Máximo 20 kg por caja
• No amontonar

💰 **Calidad del producto:**

**Extra (precio alto):**
• Dedos de 24-28 cm
• Sin daños
• Madurez uniforme

**Primera:**
• Dedos 20-24 cm
• Daños menores (< 10%)

**Segunda:**
• Dedos < 20 cm
• Para procesamiento

🚚 **Transporte:**
• Vehículo limpio y cerrado
• Evitar golpes
• Máximo 3 horas al mercado

⏱️ **Vida útil:** 15-20 días en fresco (verde)""",
        'duracion_dias': 4
    }
]

# Crear módulos
print(f"\n📚 Creando módulos para: {curso.nombre}")
for mod_data in modulos:
    modulo, created = Modulo.objects.get_or_create(
        curso=curso,
        numero=mod_data['numero'],
        defaults={
            'titulo': mod_data['titulo'],
            'descripcion': mod_data['descripcion'],
            'contenido': mod_data['contenido'],
            'duracion_dias': mod_data['duracion_dias']
        }
    )
    if created:
        print(f"  ✅ Módulo {modulo.numero}: {modulo.titulo}")
    else:
        print(f"  ℹ️ Módulo {modulo.numero} ya existía")

print(f"\n🎉 ¡Curso completo!")
print(f"📖 Curso: {curso.nombre}")
print(f"📚 Módulos: {curso.modulos.count()}")
print(f"⏱️ Duración: {curso.duracion_semanas} semanas")
print(f"\n💡 Ahora puedes agregar videos a cada módulo desde el admin")
print(f"🌐 http://localhost:8000/admin/core/modulo/")
