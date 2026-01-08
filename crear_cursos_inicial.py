"""
Script para crear cursos iniciales con módulos y exámenes
Ejecutar con: python crear_cursos_inicial.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo, Examen, PreguntaExamen

def crear_curso_aguacate():
    """Crea el curso completo de Aguacate Hass"""
    print("🥑 Creando curso de Aguacate...")
    
    # Crear curso
    curso, created = Curso.objects.get_or_create(
        nombre="Producción de Aguacate Hass",
        defaults={
            'descripcion': 'Curso completo sobre cultivo de aguacate Hass en Colombia',
            'emoji': '🥑',
            'duracion_semanas': 5,
            'activo': True,
            'orden': 1
        }
    )
    
    if not created:
        print("  ℹ️ Curso ya existía")
        return
    
    # Módulo 1: Siembra
    Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo="Siembra y Establecimiento",
        descripcion="Aprende cómo sembrar aguacate Hass correctamente",
        contenido="""🥑 **LECCIÓN 1: Siembra de Aguacate**

📚 Aprende a establecer tu cultivo correctamente:

📍 **Ubicación ideal:**
   ✓ Altitud: 1.800-2.400 msnm
   ✓ Temperatura: 18-24°C
   ✓ Pendiente: Máx 45% (con terrazas)

🌱 **Preparación del terreno:**
   1. Haz hoyos de 60x60x60 cm
   2. Distancia: 6x6 metros
   3. Mezcla tierra con abono orgánico

⏰ **Mejor época:** Inicio de lluvias (marzo-abril)

💡 **Consejo del tutor:** Usa portainjertos resistentes a Phytophthora.

¿Necesitas más detalles? Pregúntame específicamente 🙋""",
        duracion_dias=7
    )
    
    # Módulo 2: Riego
    Modulo.objects.create(
        curso=curso,
        numero=2,
        titulo="Riego y Agua",
        descripcion="Sistema de riego y manejo del agua",
        contenido="""💧 **LECCIÓN 2: Riego del Aguacate**

📚 El aguacate necesita agua constante pero NO encharcamiento:

💦 **Sistemas de riego:**
   ✓ Goteo (MEJOR opción - ahorra 40% agua)
   ✓ Microaspersión
   ✓ Evita riego por gravedad

📊 **Frecuencia:**
   • Temporada seca: 2-3 veces/semana
   • Temporada lluvias: 1 vez/semana
   • Usa tensiómetro para medir humedad

🚫 **IMPORTANTE:**
   • Drena el exceso de agua
   • Evita mojar el tronco
   • No riegues en floración intensa

💡 **Consejo del tutor:** El aguacate prefiere "sed moderada" que exceso de agua.

¿Tienes dudas? ¡Pregúntame! 💬""",
        duracion_dias=7
    )
    
    # Módulo 3: Plagas
    Modulo.objects.create(
        curso=curso,
        numero=3,
        titulo="Plagas y Enfermedades",
        descripcion="Prevención y control de plagas",
        contenido="""🐛 **LECCIÓN 3: Plagas del Aguacate**

📚 Las principales amenazas y cómo combatirlas:

🦟 **Trips (Thrips):**
   • Daña flores y frutos
   • Control: Trampas azules + Spinosad
   • Prevención: Monitoreo semanal

🍄 **Phytophthora (Pudrición raíz):**
   • Mata el árbol
   • Control: Drenaje + Fosetil-Al
   • Prevención: No encharcar

🐌 **Ácaros:**
   • Deforman hojas
   • Control: Aceite agrícola + azufre
   • Prevención: Mantén humedad controlada

⚠️ **Monitoreo:**
   • Revisa plantas cada semana
   • Identifica síntomas tempranos
   • Actúa rápido

💡 **Consejo del tutor:** La prevención es 10 veces más barata que curar.

¿Identificaste una plaga? ¡Cuéntame! 🔍""",
        duracion_dias=7
    )
    
    # Módulo 4: Cosecha
    Modulo.objects.create(
        curso=curso,
        numero=4,
        titulo="Cosecha y Poscosecha",
        descripcion="Cuándo y cómo cosechar aguacate",
        contenido="""🧺 **LECCIÓN 4: Cosecha del Aguacate**

📚 El momento de cosecha define la calidad:

📅 **¿Cuándo cosechar?**
   • Mínimo 6-8 meses después de floración
   • Contenido de aceite: mínimo 22%
   • Peso: mínimo 180g por fruto

✂️ **Técnica de corte:**
   1. Usa tijeras podadoras limpias
   2. Deja 1-2 cm de pedúnculo
   3. Maneja con cuidado (se golpea fácil)

📦 **Poscosecha:**
   • Clasifica por tamaño
   • Almacena a 5-7°C
   • Maduración: 18-22°C

💰 **Valor agregado:**
   • Aguacate orgánico: +30% precio
   • Selección premium: mejor precio

💡 **Consejo del tutor:** Un aguacate bien manejado vale 50% más.

¿Dudas sobre cosecha? ¡Pregunta! 📞""",
        duracion_dias=7
    )
    
    # Módulo 5: Fertilización
    Modulo.objects.create(
        curso=curso,
        numero=5,
        titulo="Fertilización",
        descripcion="Nutrición y fertilización del aguacate",
        contenido="""🌿 **LECCIÓN 5: Fertilización del Aguacate**

📚 La nutrición correcta asegura producción:

🧪 **Nutrientes clave:**
   • N (Nitrógeno): Crecimiento
   • P (Fósforo): Raíces y floración
   • K (Potasio): Calidad del fruto

📊 **Plan de fertilización:**
   • Año 1: 100g N/árbol
   • Año 2: 200g N/árbol
   • Año 3+: 300-400g N/árbol
   • Divide en 4 aplicaciones/año

🍂 **Fertilización orgánica:**
   • Compost: 20kg/árbol/año
   • Lombrihumus: Excelente opción
   • Bocashi: Mejora suelo

🔬 **Análisis de suelo:**
   • Hazlo cada 2 años
   • Ajusta según resultados
   • pH ideal: 5.5-6.5

💡 **Consejo del tutor:** El análisis de suelo te ahorra dinero en fertilizantes.

¿Listo para el examen? ¡Escribe "examen"! 🎓""",
        duracion_dias=7
    )
    
    # Crear examen
    examen, _ = Examen.objects.get_or_create(
        curso=curso,
        defaults={
            'instrucciones': 'Responde las siguientes preguntas sobre el cultivo de aguacate. El tutor evaluará tus respuestas.',
            'puntaje_minimo': 70
        }
    )
    
    # Preguntas del examen
    preguntas = [
        {
            'numero': 1,
            'pregunta': '¿Cuál es la altitud ideal para cultivar aguacate Hass en Colombia?',
            'respuesta_correcta': '1800, 2400, msnm, metros, altura, altitud',
            'puntos': 20
        },
        {
            'numero': 2,
            'pregunta': '¿Cuál es el mejor sistema de riego para aguacate y por qué?',
            'respuesta_correcta': 'goteo, ahorra, agua, eficiente, 40%',
            'puntos': 20
        },
        {
            'numero': 3,
            'pregunta': 'Menciona dos plagas o enfermedades principales del aguacate.',
            'respuesta_correcta': 'trips, phytophthora, ácaros, thrips, pudrición',
            'puntos': 20
        },
        {
            'numero': 4,
            'pregunta': '¿Cuántos meses después de la floración se puede cosechar el aguacate?',
            'respuesta_correcta': '6, 8, meses, floración',
            'puntos': 20
        },
        {
            'numero': 5,
            'pregunta': '¿Cuáles son los 3 nutrientes principales que necesita el aguacate?',
            'respuesta_correcta': 'nitrógeno, fósforo, potasio, N, P, K, NPK',
            'puntos': 20
        }
    ]
    
    for p in preguntas:
        PreguntaExamen.objects.get_or_create(
            examen=examen,
            numero=p['numero'],
            defaults={
                'pregunta': p['pregunta'],
                'respuesta_correcta': p['respuesta_correcta'],
                'puntos': p['puntos']
            }
        )
    
    print("✅ Curso de Aguacate creado con 5 módulos y 5 preguntas de examen")


def crear_curso_cafe():
    """Crea el curso completo de Café"""
    print("☕ Creando curso de Café...")
    
    curso, created = Curso.objects.get_or_create(
        nombre="Cultivo de Café Arábigo",
        defaults={
            'descripcion': 'Curso completo sobre producción de café de alta calidad',
            'emoji': '☕',
            'duracion_semanas': 5,
            'activo': True,
            'orden': 2
        }
    )
    
    if not created:
        print("  ℹ️ Curso ya existía")
        return
    
    # Módulo 1: Siembra
    Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo="Establecimiento del Cafetal",
        descripcion="Cómo preparar y sembrar café",
        contenido="""☕ **LECCIÓN 1: Siembra del Café**

📚 Aprende a establecer tu cafetal correctamente:

📍 **Condiciones ideales:**
   ✓ Altitud: 1.200-2.000 msnm
   ✓ Temperatura: 17-23°C
   ✓ Sombra: 30-50% (con árboles)

🌱 **Preparación:**
   1. Hoyos: 30x30x30 cm
   2. Distancia: 1.5 x 1.5 metros
   3. Abono orgánico en el hoyo

🌳 **Sombrío:**
   • Guamos, nogales, cítricos
   • Controla luz del sol
   • Protege del viento

⏰ **Mejor época:** Inicio de lluvias

💡 **Consejo del tutor:** El café necesita sombra para producir mejor.

¿Preguntas? ¡Escríbeme! 💬""",
        duracion_dias=7
    )
    
    # Módulo 2: Manejo
    Modulo.objects.create(
        curso=curso,
        numero=2,
        titulo="Manejo y Podas",
        descripcion="Mantenimiento del cafetal",
        contenido="""✂️ **LECCIÓN 2: Manejo del Cafetal**

📚 Mantén tu cafetal productivo:

✂️ **Tipos de poda:**
   • Poda de formación (año 1-2)
   • Poda de mantenimiento (anual)
   • Poda de renovación (cada 5 años)

🌿 **Control de arvenses:**
   • Desmaleza cada 3 meses
   • Mantén coberturas nobles
   • No uses químicos cerca de raíces

☔ **Manejo de agua:**
   • Mulch orgánico conserva humedad
   • No encharcar
   • Riego en sequías prolongadas

💡 **Consejo del tutor:** Una poda bien hecha aumenta 30% la producción.

¿Tienes dudas? ¡Pregunta! 📞""",
        duracion_dias=7
    )
    
    # Módulo 3: Plagas
    Modulo.objects.create(
        curso=curso,
        numero=3,
        titulo="Plagas y Enfermedades",
        descripcion="Control de broca y roya",
        contenido="""🐛 **LECCIÓN 3: Plagas del Café**

📚 Principales amenazas del cafetal:

🪲 **Broca del café:**
   • Daña el grano
   • Control: Recolección sanitaria (Re-Re)
   • Trampas con alcohol + metanol

🍄 **Roya del café:**
   • Manchas naranja en hojas
   • Control: Fungicidas cúpricos
   • Variedades resistentes (Cenicafé 1)

🐌 **Minador de la hoja:**
   • Túneles en hojas
   • Control: Parasitoides naturales
   • Evita insecticidas de amplio espectro

⚠️ **Monitoreo:**
   • Revisa 20 plantas/semana
   • Re-Re cada 15 días
   • Registra incidencias

💡 **Consejo del tutor:** La broca se controla con disciplina, no con químicos.

¿Identificaste una plaga? ¡Escríbeme! 🔍""",
        duracion_dias=7
    )
    
    # Módulo 4: Cosecha
    Modulo.objects.create(
        curso=curso,
        numero=4,
        titulo="Cosecha y Beneficio",
        descripcion="Recolección y procesamiento del café",
        contenido="""🧺 **LECCIÓN 4: Cosecha del Café**

📚 La calidad del café se define en la cosecha:

🍒 **Punto de cosecha:**
   • Solo cerezas maduras (rojas)
   • Evita verdes y sobremaduras
   • Cosecha selectiva = mejor precio

✋ **Técnica de recolección:**
   1. Cosecha a mano
   2. Usa canasta o cofa
   3. Separa granos dañados

⚗️ **Beneficio del café:**
   • Despulpar el mismo día
   • Fermentación: 12-24 horas
   • Lavado: agua limpia
   • Secado: 10-15 días al sol

💰 **Café especial:**
   • Selección rigurosa: +50% precio
   • Trazabilidad
   • Certificaciones

💡 **Consejo del tutor:** Un café mal cosechado pierde 80% de su valor.

¿Dudas sobre el proceso? ¡Pregunta! 📞""",
        duracion_dias=7
    )
    
    # Módulo 5: Nutrición
    Modulo.objects.create(
        curso=curso,
        numero=5,
        titulo="Nutrición y Fertilización",
        descripcion="Plan de fertilización del café",
        contenido="""🌿 **LECCIÓN 5: Fertilización del Café**

📚 Alimenta tu cafetal correctamente:

🧪 **Nutrientes principales:**
   • N (Nitrógeno): 200-300 kg/ha/año
   • P (Fósforo): 50-100 kg/ha/año
   • K (Potasio): 150-250 kg/ha/año

📅 **Calendario de fertilización:**
   1. Inicio de lluvias: 40% N
   2. Mitad de lluvias: 40% N
   3. Final de lluvias: 20% N

🍂 **Fertilización orgánica:**
   • Pulpa de café compostada
   • Gallinaza: 2-3 kg/planta/año
   • Bocashi mejora el suelo

🔬 **Análisis foliar:**
   • Cada año en agosto
   • Ajusta según resultados
   • pH ideal: 5.0-6.0

💡 **Consejo del tutor:** El análisis foliar te dice exactamente qué necesita la planta.

¿Listo para el examen? ¡Escribe "examen"! 🎓""",
        duracion_dias=7
    )
    
    # Crear examen
    examen, _ = Examen.objects.get_or_create(
        curso=curso,
        defaults={
            'instrucciones': 'Responde las siguientes preguntas sobre el cultivo de café. El tutor evaluará tus respuestas.',
            'puntaje_minimo': 70
        }
    )
    
    # Preguntas del examen
    preguntas = [
        {
            'numero': 1,
            'pregunta': '¿En qué rango de altitud se cultiva mejor el café arábigo en Colombia?',
            'respuesta_correcta': '1200, 2000, msnm, metros, altitud, altura',
            'puntos': 20
        },
        {
            'numero': 2,
            'pregunta': '¿Qué es la Re-Re y por qué es importante?',
            'respuesta_correcta': 'recolección, sanitaria, broca, control, plagas',
            'puntos': 20
        },
        {
            'numero': 3,
            'pregunta': 'Menciona dos enfermedades principales del café.',
            'respuesta_correcta': 'roya, broca, minador, mancha',
            'puntos': 20
        },
        {
            'numero': 4,
            'pregunta': '¿Qué color deben tener las cerezas de café para cosechar?',
            'respuesta_correcta': 'rojas, maduras, rojo',
            'puntos': 20
        },
        {
            'numero': 5,
            'pregunta': '¿Cuáles son los tres macronutrientes principales del café?',
            'respuesta_correcta': 'nitrógeno, fósforo, potasio, N, P, K, NPK',
            'puntos': 20
        }
    ]
    
    for p in preguntas:
        PreguntaExamen.objects.get_or_create(
            examen=examen,
            numero=p['numero'],
            defaults={
                'pregunta': p['pregunta'],
                'respuesta_correcta': p['respuesta_correcta'],
                'puntos': p['puntos']
            }
        )
    
    print("✅ Curso de Café creado con 5 módulos y 5 preguntas de examen")


if __name__ == '__main__':
    print("="*60)
    print("📚 CREANDO CURSOS EDUCATIVOS DE EKI")
    print("="*60)
    
    crear_curso_aguacate()
    crear_curso_cafe()
    
    print("\n" + "="*60)
    print("✅ ¡CURSOS CREADOS EXITOSAMENTE!")
    print("="*60)
    print("\n📝 Próximos pasos:")
    print("1. Ingresa al admin de Django: http://localhost:8000/admin/")
    print("2. Ve a 'Cursos' para ver los cursos creados")
    print("3. Ve a 'Módulos' para ver las lecciones")
    print("4. Ve a 'Exámenes' para ver las preguntas")
    print("\n🚀 ¡Ahora puedes configurar la navegación en WhatsApp!")
