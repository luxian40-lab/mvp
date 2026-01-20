"""
Agregar curso de Cacao y optimizar gamificación
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo
from core.gamificacion import Badge

print("🍫 CREANDO CURSO DE CACAO...\n")
print("=" * 60)

# Crear curso de Cacao
curso_cacao, created = Curso.objects.get_or_create(
    nombre="Cultivo de Cacao Fino",
    defaults={
        'descripcion': 'Aprende a cultivar cacao fino de aroma, desde la siembra hasta la cosecha y fermentación. Conviértete en un cacaocultor experto.',
        'emoji': '🍫',
        'duracion_semanas': 6,
        'nivel_dificultad': 'INTERMEDIO',
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
            'titulo': 'Introducción al Cacao',
            'contenido': '''🍫 INTRODUCCIÓN AL CULTIVO DE CACAO

El cacao (Theobroma cacao) es el árbol del chocolate, un cultivo ancestral de gran valor económico.

📍 ORIGEN Y VARIEDADES:
• Criollo: Cacao fino, aromático
• Forastero: Más resistente, mayor producción
• Trinitario: Híbrido de ambos

🌡️ CONDICIONES IDEALES:
• Temperatura: 24-28°C
• Altitud: 0-800 msnm
• Lluvia: 1,500-2,500 mm/año
• Sombra: 30-50% (cultivo bajo árboles)

🌳 SISTEMA AGROFORESTAL:
El cacao crece mejor con árboles de sombra como:
• Plátano, guamo, nogal
• Protege el suelo y mejora biodiversidad

💰 MERCADO:
• Cacao fino: Premium para chocolate gourmet
• Certificaciones: Orgánico, Fair Trade
• Precio especial para calidad superior''',
            'duracion_minutos': 45
        },
        {
            'numero': 2,
            'titulo': 'Establecimiento de la Plantación',
            'contenido': '''🌱 ESTABLECIMIENTO DEL CACAOTAL

PREPARACIÓN DEL TERRENO:

1. Selección del lote:
   • Suelo profundo, bien drenado
   • pH 5.5 - 7.0
   • Pendiente menor a 30%

2. Trazado y ahoyado:
   • Distancia: 3x3 metros
   • Hoyos: 40x40x40 cm
   • 1,111 plantas/hectárea

3. Siembra de árboles de sombra:
   • PRIMERO: Plátano, guamo
   • 6 meses antes del cacao
   • Provee sombra temporal

🌳 SIEMBRA DEL CACAO:

Época: Inicio de lluvias
Material: Plántulas injertadas (4-6 meses)

PROCESO:
1. Preparar hoyo con materia orgánica
2. Plantar al nivel del cuello
3. Regar abundantemente
4. Colocar estaca tutora

🛡️ SOMBRA INICIAL:
• Temporal: Plátano, yuca
• Permanente: Guamo, nogal, cítricos
• Reducir a 30% después de 3 años''',
            'duracion_minutos': 50
        },
        {
            'numero': 3,
            'titulo': 'Nutrición y Fertilización',
            'contenido': '''🌿 NUTRICIÓN DEL CACAO

REQUERIMIENTOS NUTRICIONALES:

Macronutrientes principales:
• Nitrógeno (N): Crecimiento vegetativo
• Fósforo (P): Raíces y floración
• Potasio (K): Calidad de mazorcas

Secundarios importantes:
• Calcio, Magnesio, Azufre

⚗️ PLAN DE FERTILIZACIÓN:

AÑO 1-2 (Establecimiento):
• 100-150 g NPK 15-15-15 / planta
• Aplicar cada 3 meses
• Materia orgánica: 5 kg/planta/año

AÑO 3+ (Producción):
• 300-500 g NPK 10-20-20 / planta
• Aplicar 3-4 veces/año
• Adicionar micronutrientes

🍂 ABONOS ORGÁNICOS:
• Compost de pulpa de cacao
• Bocashi fermentado
• Mantillo de hojarasca
• Lombricompost

📍 FORMA DE APLICACIÓN:
• En corona, a 30 cm del tronco
• Incorporar ligeramente al suelo
• Después de lluvias o con riego''',
            'duracion_minutos': 45
        },
        {
            'numero': 4,
            'titulo': 'Manejo de Plagas y Enfermedades',
            'contenido': '''🐛 SANIDAD DEL CACAOTAL

PRINCIPALES ENFERMEDADES:

1. 🦠 MONILIASIS (Moniliophthora roreri):
   • Pudrición de mazorcas
   • Control: Remover mazorcas enfermas semanalmente
   • Fungicidas cúpricos preventivos

2. 🍄 ESCOBA DE BRUJA (Moniliophthora perniciosa):
   • Deformación de brotes y flores
   • Poda sanitaria rigurosa
   • Eliminar tejido enfermo

3. 🔴 FITÓFTORA (Phytophthora spp.):
   • Pudrición de raíces y tronco
   • Buen drenaje
   • Aplicación de caldo bordelés

🐜 PLAGAS COMUNES:

• Hormiga arriera: Barreras físicas
• Áfidos y trips: Control biológico
• Chinches: Trampas y monitoreo

🌿 MANEJO INTEGRADO:

1. Cultural:
   • Poda regular para ventilación
   • Deshierbe oportuno
   • Eliminar plantas hospederas

2. Biológico:
   • Trichoderma para control de hongos
   • Beauveria bassiana para insectos
   • Fomentar enemigos naturales

3. Químico (último recurso):
   • Productos autorizados para orgánico
   • Respetar tiempos de carencia''',
            'duracion_minutos': 55
        },
        {
            'numero': 5,
            'titulo': 'Cosecha y Beneficio',
            'contenido': '''📦 COSECHA Y PROCESAMIENTO

INDICADORES DE MADUREZ:

• Color: Amarillo o rojo (según variedad)
• Sonido: Hueco al golpear
• Edad: 5-6 meses desde floración

🔪 TÉCNICA DE COSECHA:

1. Usar machete afilado
2. Cortar pedúnculo sin dañar cojín floral
3. Evitar golpear el tronco
4. Hacer 2 cortes por semana

⚙️ BENEFICIO DEL CACAO:

1. DESGRANE (Mismo día):
   • Partir mazorca con mazo
   • Extraer granos con placenta
   • Separar granos defectuosos

2. FERMENTACIÓN (5-7 días):
   • Cajas de madera con drenaje
   • Capas de 40-50 cm
   • Voltear diariamente después del día 2
   • Temperatura: 45-50°C
   • Objetivo: Desarrollar sabor y aroma

3. SECADO (5-7 días):
   • Al sol sobre tendales
   • Remover cada hora
   • Hasta 7% de humedad
   • Proteger de lluvia

4. CLASIFICACIÓN Y ALMACENAMIENTO:
   • Eliminar granos planos o mohosos
   • Ensacar en sacos de yute
   • Almacenar en lugar seco y ventilado

💰 CALIDAD PREMIUM:
• Fermentación completa
• Sin defectos
• Aroma a chocolate
• Precio 30-50% superior''',
            'duracion_minutos': 60
        }
    ]
    
    print(f"\n📚 Creando {len(modulos)} módulos...")
    for mod_data in modulos:
        Modulo.objects.create(
            curso=curso_cacao,
            **mod_data
        )
        print(f"   ✅ Módulo {mod_data['numero']}: {mod_data['titulo']}")
    
    print(f"\n✅ Curso completo creado con {len(modulos)} módulos")
else:
    print(f"ℹ️ El curso ya existía: {curso_cacao.nombre}")

print("\n" + "=" * 60)
print("\n📚 CURSOS FINALES (4 cursos diversos):\n")

cursos = Curso.objects.filter(activo=True).order_by('orden')
for idx, c in enumerate(cursos, 1):
    modulos_count = c.modulos.count()
    print(f"   {idx}. {c.emoji} {c.nombre} ({modulos_count} módulos)")

print("\n🎉 ¡Sistema con 4 cursos bien hechos y diversos!")
