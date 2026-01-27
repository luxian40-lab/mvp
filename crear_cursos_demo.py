#!/usr/bin/env python
"""
Crear 4 cursos adicionales para la demo
"""

import os
import django
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo

logger = logging.getLogger("crear_cursos_demo")

def crear_curso_yuca():
    """Curso de Cultivo de Yuca"""
    curso, created = Curso.objects.get_or_create(
        nombre='Cultivo de Yuca',
        defaults={
            'descripcion': 'Aprende a cultivar yuca de manera eficiente y rentable',
            'duracion_dias': 90,
            'nivel': 'Básico',
            'activo': True
        }
    )
    
   if created:
      modulos = [
         ...existing code...

**Pasos de preparación:**

1. **Limpieza**
   • Eliminar malezas
   • Quitar piedras grandes
   • Nivelar el terreno

2. **Arado**
   • Profundidad: 20-30 cm
   • Usar bueyes o tractor
   • Hacer en época seca

3. **Surcado**
   • Distancia entre surcos: 1 metro
   • Altura del surco: 15-20 cm
   • Facilita drenaje

4. **Abonado (opcional)**
   • Estiércol descompuesto
   • Aplicar 2 semanas antes

📱 Responde: ¿Cuántos cm de profundidad debe tener el arado?''',
                'duracion_dias': 2
            },
            {
                'numero': 3,
                'titulo': 'Siembra de Estacas',
                'descripcion': 'Técnica correcta de siembra',
                'contenido': '''🌿 **Siembra de Yuca**

La yuca se siembra con estacas (no semillas)

**Selección de estacas:**
• Tallo maduro (10-12 meses)
• Grosor: 2-4 cm
• Longitud: 20-25 cm
• 5-7 yemas visibles
• Sin daños ni plagas

**Época de siembra:**
• Inicio de lluvias
• Suelo húmedo pero no encharcado

**Proceso de siembra:**

1. Cortar estacas 1-2 días antes
2. Plantar inclinadas (45°)
3. Enterrar 2/3 de la estaca
4. Distancia: 1m entre plantas
5. Apisonar suelo alrededor

**Densidad recomendada:**
10,000 plantas por hectárea

⏰ **Tiempo de germinación:** 10-15 días

📱 Escribe "listo" para continuar''',
                'duracion_dias': 2
            },
            {
                'numero': 4,
                'titulo': 'Manejo del Cultivo',
                'descripcion': 'Cuidados durante el crecimiento',
                'contenido': '''🌱 **Manejo y Cuidados**

**Primeros 3 meses:**

1. **Control de malezas**
   • Desyerbar cada 20-30 días
   • No dañar raíces superficiales
   • 2-3 limpias son suficientes

2. **Aporque**
   • A los 45 días después de siembra
   • Cubrir base de la planta
   • Protege raíces tuberosas

3. **Plagas comunes:**
   • Mosca blanca
   • Ácaros
   • Gusano cachón

4. **Enfermedades:**
   • Pudrición de raíz
   • Bacteriosis
   • Prevención: buen drenaje

**No requiere:**
• Riego frecuente (resistente a sequía)
• Fertilización excesiva

📱 Responde: ¿Cada cuántos días se debe desyerbar?''',
                'duracion_dias': 2
            },
            {
                'numero': 5,
                'titulo': 'Cosecha y Comercialización',
                'descripcion': 'Momento ideal de cosecha',
                'contenido': '''🌾 **Cosecha de Yuca**

**Momento de cosecha:**
• Entre 8-12 meses después de siembra
• Cuando hojas amarillean
• Tallos leñosos y secos

**Señales de madurez:**
✓ Hojas amarillas cayendo
✓ Tallo duro y seco
✓ Raíces grandes (500g-2kg)

**Proceso de cosecha:**

1. Cortar tallos a 10 cm del suelo
2. Aflojar tierra alrededor
3. Jalar planta completa
4. Separar raíces del tallo
5. Guardar tallos para nueva siembra

**Rendimiento esperado:**
• 15-25 toneladas/hectárea
• Depende de variedad y manejo

**Comercialización:**
• Vender fresca (dura 2-3 días)
• O procesar (harina, almidón)
• Precios mejores en época seca

💰 **Rentabilidad:** Alta con buen manejo

📱 Escribe "listo" para el examen final''',
                'duracion_dias': 2
            }
        ]
        
        for mod_data in modulos:
            Modulo.objects.create(curso=curso, **mod_data)
        
        print(f"✅ Creado: {curso.nombre} ({len(modulos)} módulos)")
    else:
        print(f"⚠️  Ya existe: {curso.nombre}")

def crear_curso_ganaderia():
    """Curso de Ganadería de Leche"""
    curso, created = Curso.objects.get_or_create(
        nombre='Ganadería de Leche',
        defaults={
            'descripcion': 'Manejo eficiente de ganado lechero',
            'duracion_dias': 120,
            'nivel': 'Intermedio',
            'activo': True
        }
    )
    
    if created:
        modulos = [
            {
                'numero': 1,
                'titulo': 'Introducción a la Ganadería Lechera',
                'descripcion': 'Conceptos básicos y razas',
                'contenido': '''🐄 **Ganadería de Leche**

Un negocio rentable con dedicación

**Ventajas:**
• Ingreso diario por venta de leche
• No requiere grandes extensiones
• Doble propósito (leche + carne)

**Razas recomendadas para Colombia:**

1. **Holstein**
   • Mayor producción
   • 20-30 litros/día
   • Clima frío

2. **Jersey**
   • Leche de alta calidad
   • 15-20 litros/día
   • Adaptable

3. **Normando**
   • Doble propósito
   • 15-25 litros/día
   • Resistente

4. **Criollas**
   • Muy resistentes
   • 8-12 litros/día
   • Bajo costo

**Inversión inicial:**
• 1 vaca lechera: $3-5 millones
• Instalaciones básicas: $2-3 millones

📱 Escribe "listo" cuando termines''',
                'duracion_dias': 2
            },
            {
                'numero': 2,
                'titulo': 'Instalaciones y Equipos',
                'descripcion': 'Infraestructura necesaria',
                'contenido': '''🏠 **Instalaciones para Ganado Lechero**

**Básico requerido:**

1. **Establo o corral**
   • 8-10 m² por vaca
   • Techo para sombra
   • Piso con drenaje
   • Comederos y bebederos

2. **Sala de ordeño**
   • Limpia y techada
   • Agua disponible
   • Piso de cemento
   • Iluminación adecuada

3. **Área de pastoreo**
   • Mínimo 1 hectárea por 4 vacas
   • Pastos de buena calidad
   • Cerca en buen estado
   • Acceso a sombra y agua

4. **Equipos básicos**
   • Baldes de ordeño (acero inoxidable)
   • Cantinas para transporte
   • Escobas y cepillos
   • Botiquín veterinario

**Opcional pero recomendado:**
• Ordeñadora mecánica
• Tanque enfriador
• Bascula

📱 Responde: ¿Cuántos m² necesita cada vaca?''',
                'duracion_dias': 2
            },
            {
                'numero': 3,
                'titulo': 'Alimentación del Ganado',
                'descripcion': 'Nutrición para buena producción',
                'contenido': '''🌾 **Alimentación Lechera**

Buena alimentación = Más leche

**Componentes de la dieta:**

1. **Forraje (70-80%)**
   • Pasto fresco de calidad
   • 40-60 kg/vaca/día
   • Mejores: kikuyo, raygrass, estrella

2. **Concentrado (20-30%)**
   • 1 kg por cada 3 litros de leche
   • Maíz, soya, melaza
   • Dar en 2-3 porciones diarias

3. **Agua limpia**
   • 80-100 litros/vaca/día
   • Siempre disponible
   • Limpia y fresca

4. **Sales minerales**
   • 50-100 g/día
   • En bloque o mezclada
   • Esencial para salud

**Horario recomendado:**
• 6:00 AM - Concentrado + agua
• 8:00 AM - Pastoreo
• 12:00 PM - Sombra + agua
• 3:00 PM - Concentrado
• 4:00 PM - Pastoreo

💡 **Tip:** Más comida = Más leche

📱 Escribe "listo" para continuar''',
                'duracion_dias': 3
            },
            {
                'numero': 4,
                'titulo': 'Ordeño y Manejo de Leche',
                'descripcion': 'Técnicas de ordeño higiénico',
                'contenido': '''🥛 **Técnica de Ordeño**

Higiene = Leche de calidad

**Antes del ordeño:**

1. Lavar manos y utensilios
2. Limpiar ubres con agua tibia
3. Secar con toalla limpia
4. Descartar primeros chorros

**Durante el ordeño:**

• Usar 5 dedos (no 2)
• Movimientos firmes y rítmicos
• No jalar bruscamente
• Ordeñar completamente

**Después del ordeño:**

1. Aplicar sellador en pezones
2. Dejar vaca parada 30 min
3. Colar leche inmediatamente
4. Enfriar lo antes posible

**Horarios:**
• Mañana: 5-6 AM
• Tarde: 3-4 PM
• Mismo horario diario

**Higiene esencial:**
✓ Utensilios limpios
✓ Manos lavadas
✓ Ubres limpias
✓ Ambiente limpio

⚠️ **Importante:** No mezclar leche de vacas enfermas

📱 Responde: ¿Cuántas veces al día se ordeña?''',
                'duracion_dias': 3
            },
            {
                'numero': 5,
                'titulo': 'Sanidad y Reproducción',
                'descripcion': 'Salud y cría del ganado',
                'contenido': '''💉 **Sanidad Animal**

**Calendario de vacunación:**

• Fiebre aftosa: cada 6 meses
• Brucelosis: hembras jóvenes
• Carbón sintomático: anual
• Desparasitación: cada 3 meses

**Enfermedades comunes:**

1. **Mastitis**
   • Inflamación de ubres
   • Causa: mala higiene
   • Prevención: limpieza

2. **Cojeras**
   • Cuidado de pezuñas
   • Limpieza regular
   • Baños desinfectantes

3. **Parásitos**
   • Externos: garrapatas, moscas
   • Internos: lombrices
   • Control periódico

**Reproducción:**

• Primera monta: 18-24 meses
• Gestación: 9 meses
• Periodo seco: 2 meses antes del parto
• Intervalo entre partos: 12-13 meses

**Señales de celo:**
• Inquieta, muge mucho
• Baja producción de leche
• Monta a otras vacas
• Dura 12-18 horas

💰 **Producción esperada:**
• Primera lactancia: 10-15 litros/día
• Lactancias siguientes: 15-25 litros/día

📱 Escribe "listo" para el examen''',
                'duracion_dias': 3
            }
        ]
        
        for mod_data in modulos:
            Modulo.objects.create(curso=curso, **mod_data)
        
        print(f"✅ Creado: {curso.nombre} ({len(modulos)} módulos)")
    else:
        print(f"⚠️  Ya existe: {curso.nombre}")

def crear_curso_maiz():
    """Curso de Cultivo de Maíz"""
    curso, created = Curso.objects.get_or_create(
        nombre='Cultivo de Maíz',
        defaults={
            'descripcion': 'Producción eficiente de maíz amarillo y blanco',
            'duracion_dias': 100,
            'nivel': 'Básico',
            'activo': True
        }
    )
    
    if created:
        modulos = [
            {
                'numero': 1,
                'titulo': 'Introducción al Maíz',
                'descripcion': 'Variedades y condiciones',
                'contenido': '''🌽 **Cultivo de Maíz**

El grano más versátil de Colombia

**Importancia:**
• Alimento humano y animal
• Materia prima industrial
• Cultivo rentable
• Ciclo corto (4-5 meses)

**Variedades:**

1. **Maíz Blanco**
   • Consumo humano
   • Arepas, mazamorra
   • Mayor precio

2. **Maíz Amarillo**
   • Alimento animal
   • Mayor producción
   • Uso industrial

**Condiciones ideales:**
• Temperatura: 20-30°C
• Altitud: 0-2,600 msnm
• Lluvia: 500-800 mm
• Suelo profundo y fértil

**Rendimiento esperado:**
• Tecnología baja: 2-3 ton/ha
• Tecnología media: 4-5 ton/ha
• Tecnología alta: 6-8 ton/ha

📱 Escribe "listo" cuando termines de leer''',
                'duracion_dias': 1
            },
            {
                'numero': 2,
                'titulo': 'Preparación y Siembra',
                'descripcion': 'Inicio del cultivo',
                'contenido': '''🌱 **Siembra de Maíz**

**Preparación del terreno:**

1. **Arado**
   • Profundidad: 25-30 cm
   • Incorporar residuos
   • 30 días antes de siembra

2. **Rastrillada**
   • Deshacer terrones
   • Nivelar terreno
   • 15 días antes

3. **Surcado**
   • Distancia entre surcos: 70-80 cm
   • Facilita labores
   • Mejor drenaje

**Época de siembra:**
• Inicio de temporada lluviosa
• Marzo-Abril o Septiembre-Octubre

**Semilla:**
• Certificada o mejorada
• 20-25 kg/hectárea
• Tratar con fungicida

**Siembra:**

1. Distancia entre plantas: 25-30 cm
2. Profundidad: 3-5 cm
3. 2-3 semillas por sitio
4. Densidad: 50,000-60,000 plantas/ha

**Fertilización inicial:**
• 150 kg/ha de fertilizante compuesto
• Al momento de siembra
• En banda al lado de la semilla

📱 Responde: ¿Cuál es la distancia entre surcos?''',
                'duracion_dias': 2
            },
            {
                'numero': 3,
                'titulo': 'Manejo del Cultivo',
                'descripcion': 'Cuidados durante crecimiento',
                'contenido': '''🌿 **Manejo Agronómico**

**Primera fase (0-30 días):**

1. **Raleo**
   • A los 15 días
   • Dejar 1 planta por sitio
   • Eliminar plantas débiles

2. **Primera desyerba**
   • A los 20-25 días
   • Manual o química
   • No dañar raíces

3. **Primera fertilización**
   • A los 30 días
   • Urea: 100 kg/ha
   • Aplicar al lado de la planta

**Segunda fase (30-60 días):**

1. **Segunda desyerba**
   • A los 45 días
   • Última desyerba necesaria

2. **Segunda fertilización**
   • A los 45-50 días
   • Urea: 100 kg/ha
   • Aporcar (arrimar tierra)

**Control de plagas:**

• **Cogollero**
  - Gusano que come hojas
  - Control: insecticida

• **Gallina ciega**
  - Daña raíces
  - Control preventivo

• **Gusano elotero**
  - Daña mazorca
  - Control cuando aparece

📱 Escribe "listo" para continuar''',
                'duracion_dias': 2
            },
            {
                'numero': 4,
                'titulo': 'Cosecha y Poscosecha',
                'descripcion': 'Recolección y almacenamiento',
                'contenido': '''🌾 **Cosecha del Maíz**

**Momento de cosecha:**

• 120-150 días después de siembra
• Cuando grano está duro
• Hojas secas y amarillas
• Humedad del grano: 18-20%

**Señales de madurez:**
✓ Hojas totalmente secas
✓ Grano duro (no se marca con uña)
✓ Mazorca doblada hacia abajo
✓ Brácteas (hojas) secas

**Cosecha manual:**

1. Doblar o cortar planta
2. Arrancar mazorca
3. Recoger en costales
4. Transportar al secadero

**Secado:**

• Al sol: 8-10 días
• Extender en patio limpio
• Voltear 2 veces al día
• Hasta 12-14% humedad

**Desgrane:**

• Manual (para poco volumen)
• Desgranadora mecánica
• Limpiar impurezas

**Almacenamiento:**

✓ Lugar seco y ventilado
✓ Costales limpios
✓ Sobre estibas
✓ Proteger de roedores
✓ Revisar cada semana

**Rendimiento esperado:**
• 4-6 toneladas/hectárea
• Precio variable por temporada

💰 **Rentabilidad:** Buena con manejo adecuado

📱 Escribe "listo" para el examen final''',
                'duracion_dias': 2
            }
        ]
        
        for mod_data in modulos:
            Modulo.objects.create(curso=curso, **mod_data)
        
        print(f"✅ Creado: {curso.nombre} ({len(modulos)} módulos)")
    else:
        print(f"⚠️  Ya existe: {curso.nombre}")

def crear_curso_pollos():
    """Curso de Crianza de Pollos"""
    curso, created = Curso.objects.get_or_create(
        nombre='Crianza de Pollos de Engorde',
        defaults={
            'descripcion': 'Producción eficiente de pollo de engorde',
            'duracion_dias': 60,
            'nivel': 'Básico',
            'activo': True
        }
    )
    
    if created:
        modulos = [
            {
                'numero': 1,
                'titulo': 'Introducción a la Avicultura',
                'descripcion': 'Conceptos básicos',
                'contenido': '''🐔 **Crianza de Pollos de Engorde**

Negocio rentable de ciclo corto

**Ventajas:**
• Ciclo corto (42-45 días)
• Alta rentabilidad
• Poco espacio necesario
• Demanda constante

**Tipos de producción:**

1. **Engorde**
   • Carne para consumo
   • 45 días de crianza
   • Mayor volumen

2. **Postura** (otro curso)
   • Producción de huevos
   • Mayor tiempo
   • Ingreso continuo

**Inversión inicial (100 pollos):**
• Pollitos: $200,000
• Alimento: $600,000
• Medicinas: $50,000
• Total: ~$850,000

**Ganancia esperada:**
• Venta: $1,500,000
• Utilidad: $400-500,000
• Por ciclo de 45 días

**Razas recomendadas:**
• Cobb 500
• Ross 308
• Hubbard

📱 Escribe "listo" cuando termines''',
                'duracion_dias': 1
            },
            {
                'numero': 2,
                'titulo': 'Instalaciones y Equipos',
                'descripcion': 'Galpón y equipamiento',
                'contenido': '''🏠 **Galpón Avícola**

**Ubicación:**
• Terreno seco y plano
• Lejos de viviendas (olores)
• Acceso a agua y luz
• Protegido de vientos

**Tamaño del galpón:**
• 10 pollos por m²
• 100 pollos = 10 m²
• Alto: 2.5-3 metros
• Buena ventilación

**Construcción básica:**

1. **Piso**
   • Cemento o tierra
   • Cama de viruta o cascarilla
   • 10 cm de espesor

2. **Paredes**
   • Malla gallinera
   • Base de 50 cm sólida
   • Cortinas para frío

3. **Techo**
   • Zinc o eternit
   • Con aleros
   • Aislante térmico

**Equipos necesarios:**

✓ **Comederos**
  - 1 por cada 25 pollos
  - Tipo bandeja o lineal

✓ **Bebederos**
  - 1 por cada 50 pollos
  - Automáticos o manuales

✓ **Criadoras**
  - Para primeros 15 días
  - Bombillo o gas
  - 32°C inicial

✓ **Termómetro**
  - Control de temperatura
  - Esencial primeros días

📱 Responde: ¿Cuántos pollos por m²?''',
                'duracion_dias': 2
            },
            {
                'numero': 3,
                'titulo': 'Manejo de Pollitos',
                'descripcion': 'Primeros días críticos',
                'contenido': '''🐣 **Manejo Inicial**

Los primeros 7 días son críticos

**Antes de recibir pollitos:**

1. Limpiar y desinfectar galpón
2. Preparar cama limpia
3. Instalar criadora
4. Encender 24h antes
5. Preparar agua con azúcar

**Temperatura ideal:**
• Día 1-7: 32-35°C
• Día 8-14: 28-30°C
• Día 15-21: 25-27°C
• Día 22+: 20-24°C

**Señales de temperatura:**

🔥 **Muy caliente:**
- Pollos alejados de criadora
- Pico abierto jadeando
- Alas separadas del cuerpo

❄️ **Muy frío:**
- Pollos apiñados
- Pían constantemente
- Buscan calor

✅ **Temperatura correcta:**
- Pollos dispersos
- Activos y comiendo
- Descansan tranquilos

**Primera semana:**

• Agua siempre disponible
• Con vitaminas primeros 3 días
• Alimento a libre voluntad
• Luz 24 horas
• Revisar cada 2 horas

**Mortalidad esperada:**
• Normal: 3-5%
• Revisar diario
• Retirar muertos inmediatamente

📱 Escribe "listo" para continuar''',
                'duracion_dias': 2
            },
            {
                'numero': 4,
                'titulo': 'Alimentación y Nutrición',
                'descripcion': 'Plan de alimentación',
                'contenido': '''🌾 **Alimentación del Pollo**

Alimentación = 70% del costo

**Tipos de alimento:**

1. **Iniciación (0-21 días)**
   • 22% proteína
   • Presentación: harina
   • Consumo: 1 kg por pollo

2. **Engorde (22-45 días)**
   • 19% proteína
   • Presentación: pelet
   • Consumo: 3.5 kg por pollo

**Total consumido por pollo:**
• 4.5 kg de alimento
• En 45 días
• Conversión: 1.8-2.0

**Programa de alimentación:**

Semana 1: 20 g/día
Semana 2: 35 g/día
Semana 3: 55 g/día
Semana 4: 85 g/día
Semana 5: 120 g/día
Semana 6+: 140 g/día

**Agua:**
• 2 litros de agua por 1 kg de alimento
• Siempre fresca y limpia
• Cambiar 2-3 veces al día

**Consejos:**

✓ Dar alimento en horas frescas
✓ No mojar el alimento
✓ Limpiar comederos diario
✓ Controlar desperdicio
✓ Almacenar en seco

⚠️ **Importante:** No cambiar de alimento bruscamente

📱 Responde: ¿Cuánto alimento consume cada pollo?''',
                'duracion_dias': 2
            },
            {
                'numero': 5,
                'titulo': 'Sanidad y Comercialización',
                'descripcion': 'Salud y venta',
                'contenido': '''💉 **Plan Sanitario**

**Vacunaciones obligatorias:**

Día 1: Newcastle (gota ocular)
Día 7: Gumboro (agua de bebida)
Día 14: Newcastle refuerzo
Día 21: Gumboro refuerzo

**Enfermedades comunes:**

1. **Newcastle**
   • Síntomas: paro, diarrea, muerte
   • Prevención: vacuna

2. **Gumboro**
   • Síntomas: diarrea blanca
   • Prevención: vacuna

3. **Coccidiosis**
   • Síntomas: diarrea sangre
   • Control: anticoccidial

**Bioseguridad:**

✓ Desinfectar galpón entre lotes
✓ Pediluvio en entrada
✓ Limitar visitas
✓ Retirar aves muertas
✓ Manejo de gallinaza

**Comercialización:**

**Peso de venta:**
• 2.2 - 2.5 kg en pie
• 42-45 días de edad

**Opciones de venta:**

1. **En pie**
   • A intermediario
   • Precio por kg
   • Más fácil

2. **Beneficiado**
   • Directo al consumidor
   • Mejor precio
   • Más trabajo

**Precio aproximado:**
• $7,000-8,000 por kg vivo
• Por pollo: $15,000-20,000
• Depende de la zona

💰 **Rentabilidad por 100 pollos:**
• Inversión: $850,000
• Venta: $1,500,000
• Ganancia: $450,000-500,000
• En 45 días

📱 Escribe "listo" para el examen final''',
                'duracion_dias': 2
            }
        ]
        
        for mod_data in modulos:
            Modulo.objects.create(curso=curso, **mod_data)
        
        print(f"✅ Creado: {curso.nombre} ({len(modulos)} módulos)")
    else:
        print(f"⚠️  Ya existe: {curso.nombre}")


def main():
   try:
      print("=" * 60)
      print("🚀 CREANDO CURSOS PARA DEMO")
      print("=" * 60)
      print()
      crear_curso_yuca()
      crear_curso_ganaderia()
      crear_curso_maiz()
      crear_curso_pollos()
      print()
      print("=" * 60)
      print("✅ PROCESO COMPLETADO")
      print("=" * 60)
      # Resumen
      total_cursos = Curso.objects.count()
      total_modulos = Modulo.objects.count()
      print(f"\n📊 RESUMEN:")
      print(f"   Total de cursos: {total_cursos}")
      print(f"   Total de módulos: {total_modulos}")
      print()
      print("📚 Cursos disponibles para la demo:")
      for curso in Curso.objects.all():
         print(f"   {curso.id}. {curso.nombre} ({curso.modulos.count()} módulos)")
   except Exception as e:
      logger.exception(f"Error al crear cursos demo: {e}")
      print(f"\n[ERROR] Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
   main()
