"""
Reorganizar preguntas del primer curso y crear preguntas para el segundo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import PreguntaModulo, Modulo, Curso

print("=" * 70)
print("🔧 REORGANIZACIÓN Y CREACIÓN DE PREGUNTAS")
print("=" * 70)

# ============================================
# PASO 1: REORGANIZAR PREGUNTAS DEL PRIMER CURSO
# ============================================
print("\n📝 PASO 1: Reorganizando preguntas de 'Fundamentos del Cultivo de Café'")
print("-" * 70)

curso1 = Curso.objects.get(nombre="Fundamentos del Cultivo de Café")
modulos1 = curso1.modulos.all().order_by('numero')

# Eliminar preguntas incorrectamente asignadas
PreguntaModulo.objects.filter(modulo__curso=curso1).delete()
print("✅ Preguntas antiguas eliminadas")

# MÓDULO 1: Establecimiento del Cafetal
mod1 = modulos1.get(numero=1)
PreguntaModulo.objects.create(
    modulo=mod1,
    pregunta="¿Cuál es la temperatura ideal para el cultivo de café?",
    opcion_a="Entre 17°C y 23°C",
    opcion_b="Entre 10°C y 15°C",
    opcion_c="Entre 30°C y 35°C",
    opcion_d="Más de 40°C",
    respuesta_correcta='A',
    explicacion="El café requiere temperaturas moderadas entre 17°C y 23°C para un crecimiento óptimo.",
    activa=True
)
print(f"✅ {mod1.titulo}: Pregunta sobre temperatura")

# MÓDULO 2: Manejo y Podas
mod2 = modulos1.get(numero=2)
PreguntaModulo.objects.create(
    modulo=mod2,
    pregunta="¿Cuándo se debe realizar la poda de renovación del café?",
    opcion_a="Durante la cosecha principal",
    opcion_b="En época de lluvias intensas",
    opcion_c="Después de la cosecha principal",
    opcion_d="Durante la floración",
    respuesta_correcta='C',
    explicacion="La poda debe realizarse después de la cosecha para permitir la recuperación de la planta.",
    activa=True
)
print(f"✅ {mod2.titulo}: Pregunta sobre podas")

# MÓDULO 3: Plagas y Enfermedades
mod3 = modulos1.get(numero=3)
PreguntaModulo.objects.create(
    modulo=mod3,
    pregunta="¿Qué es la técnica Re-Re para control de broca del café?",
    opcion_a="Regar y Recoger los frutos",
    opcion_b="Recolectar Repasando cada 15 días los frutos maduros y sobremaduros",
    opcion_c="Repetir Revisión de hojas",
    opcion_d="Remover Raíces dañadas",
    respuesta_correcta='B',
    explicacion="La técnica Re-Re (Recolectar Repasando) consiste en repasar cada 15 días para evitar que la broca se desarrolle.",
    activa=True
)
print(f"✅ {mod3.titulo}: Pregunta sobre control de broca")

# MÓDULO 4: Cosecha y Beneficio
mod4 = modulos1.get(numero=4)
PreguntaModulo.objects.create(
    modulo=mod4,
    pregunta="¿Qué indica que el café está listo para cosechar?",
    opcion_a="Los granos están verdes",
    opcion_b="Los granos están rojos cereza",
    opcion_c="Los granos están amarillos",
    opcion_d="Las hojas se caen",
    respuesta_correcta='B',
    explicacion="El café debe cosecharse cuando está en punto cereza (rojo maduro) para obtener la mejor calidad.",
    activa=True
)
print(f"✅ {mod4.titulo}: Pregunta sobre cosecha")

# MÓDULO 5: Nutrición y Fertilización
mod5 = modulos1.get(numero=5)
PreguntaModulo.objects.create(
    modulo=mod5,
    pregunta="¿Qué nutriente es más importante durante la floración del café?",
    opcion_a="Nitrógeno (N)",
    opcion_b="Fósforo (P)",
    opcion_c="Potasio (K)",
    opcion_d="Calcio (Ca)",
    respuesta_correcta='B',
    explicacion="El fósforo es esencial durante la floración para el desarrollo de flores y frutos.",
    activa=True
)
print(f"✅ {mod5.titulo}: Pregunta sobre nutrición")

# ============================================
# PASO 2: CREAR PREGUNTAS PARA EL SEGUNDO CURSO
# ============================================
print("\n📝 PASO 2: Creando preguntas para 'Manejo Técnico y Riego del Cafetal'")
print("-" * 70)

curso2 = Curso.objects.get(nombre="Manejo Técnico y Riego del Cafetal")
modulos2 = curso2.modulos.all().order_by('numero')

# MÓDULO 1: Análisis de Suelos y Nutrición del Café
mod2_1 = modulos2.get(numero=1)
PreguntaModulo.objects.create(
    modulo=mod2_1,
    pregunta="¿Cuál es el pH ideal del suelo para el cultivo de café?",
    opcion_a="pH 4.0 - 4.5 (muy ácido)",
    opcion_b="pH 5.5 - 6.5 (ligeramente ácido)",
    opcion_c="pH 7.0 - 8.0 (neutro a alcalino)",
    opcion_d="pH 8.5 - 9.0 (muy alcalino)",
    respuesta_correcta='B',
    explicacion="El café prefiere suelos ligeramente ácidos con pH entre 5.5 y 6.5 para una óptima absorción de nutrientes.",
    activa=True
)
print(f"✅ {mod2_1.titulo}: Pregunta sobre pH del suelo")

# MÓDULO 2: Sistemas de Riego para Café
mod2_2 = modulos2.get(numero=2)
PreguntaModulo.objects.create(
    modulo=mod2_2,
    pregunta="¿Cuál es el sistema de riego más eficiente para café en ladera?",
    opcion_a="Riego por inundación",
    opcion_b="Riego por aspersión",
    opcion_c="Riego por goteo",
    opcion_d="Riego manual con manguera",
    respuesta_correcta='C',
    explicacion="El riego por goteo es el más eficiente en laderas, ahorra hasta 60% de agua y permite fertirrigación.",
    activa=True
)
print(f"✅ {mod2_2.titulo}: Pregunta sobre sistemas de riego")

# MÓDULO 3: Podas del Café para Alta Producción
mod2_3 = modulos2.get(numero=3)
PreguntaModulo.objects.create(
    modulo=mod2_3,
    pregunta="¿Cuántos ejes productivos se deben dejar en la poda de renovación por zoqueo?",
    opcion_a="1 eje principal",
    opcion_b="2-3 ejes vigorosos",
    opcion_c="5-6 ejes",
    opcion_d="No se dejan ejes, se corta todo",
    respuesta_correcta='B',
    explicacion="En el zoqueo se deben seleccionar 2-3 ejes vigorosos y bien distribuidos para la renovación.",
    activa=True
)
print(f"✅ {mod2_3.titulo}: Pregunta sobre podas")

# MÓDULO 4: Control Integrado de Roya y Broca
mod2_4 = modulos2.get(numero=4)
PreguntaModulo.objects.create(
    modulo=mod2_4,
    pregunta="¿Cuál es la principal medida preventiva contra la roya del café?",
    opcion_a="Aplicar fungicidas cada semana",
    opcion_b="Nutrición balanceada y manejo de sombra",
    opcion_c="Regar menos las plantas",
    opcion_d="Podar todas las ramas",
    respuesta_correcta='B',
    explicacion="La prevención de roya se basa en nutrición balanceada, manejo de sombra adecuado y monitoreo constante.",
    activa=True
)
print(f"✅ {mod2_4.titulo}: Pregunta sobre control de roya")

# MÓDULO 5: Cosecha y Calidad del Café
mod2_5 = modulos2.get(numero=5)
PreguntaModulo.objects.create(
    modulo=mod2_5,
    pregunta="¿Cuánto tiempo debe durar el proceso de fermentación del café en beneficio húmedo?",
    opcion_a="4-6 horas",
    opcion_b="12-18 horas",
    opcion_c="24-36 horas",
    opcion_d="48-72 horas",
    respuesta_correcta='B',
    explicacion="La fermentación ideal para cafés de calidad es de 12-18 horas, dependiendo de temperatura y altitud.",
    activa=True
)
print(f"✅ {mod2_5.titulo}: Pregunta sobre beneficio del café")

# MÓDULO 6: Comercialización y Cafés Especiales
mod2_6 = modulos2.get(numero=6)
PreguntaModulo.objects.create(
    modulo=mod2_6,
    pregunta="¿Qué puntaje mínimo debe tener un café para ser considerado 'especial' según SCA?",
    opcion_a="70 puntos",
    opcion_b="75 puntos",
    opcion_c="80 puntos",
    opcion_d="85 puntos",
    respuesta_correcta='C',
    explicacion="Según la Specialty Coffee Association (SCA), un café debe tener mínimo 80 puntos sobre 100 para ser considerado especial.",
    activa=True
)
print(f"✅ {mod2_6.titulo}: Pregunta sobre cafés especiales")

# ============================================
# RESUMEN FINAL
# ============================================
print("\n" + "=" * 70)
print("✅ PROCESO COMPLETADO")
print("=" * 70)

total_preguntas = PreguntaModulo.objects.filter(activa=True).count()
print(f"\n📊 Total de preguntas activas: {total_preguntas}")

for curso in Curso.objects.all():
    preguntas_curso = PreguntaModulo.objects.filter(
        modulo__curso=curso,
        activa=True
    ).count()
    modulos_curso = curso.modulos.count()
    print(f"   🎓 {curso.nombre}: {preguntas_curso}/{modulos_curso} módulos con pregunta")

print("\n✅ Todas las preguntas están ahora correctamente asignadas a sus módulos")
print("✅ Sistema listo para validar aprendizaje en ambos cursos")
