"""
Script para poblar la base de datos con sistema de gamificación completo
Crea badges, niveles y datos de ejemplo
"""
import os
import django
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.gamificacion import Badge, PerfilGamificacion, BadgeEstudiante, TransaccionPuntos
from core.models import Estudiante, Curso

logger = logging.getLogger("crear_datos_gamificacion")

def main():
    try:
        print("\n" + "="*70)
        print("🎮 RECREANDO SISTEMA DE GAMIFICACIÓN - EKI")
        print("="*70 + "\n")

# ==================== LIMPIAR DATOS ANTERIORES ====================
print("🧹 Limpiando datos anteriores de gamificación...")
Badge.objects.all().delete()
print("   ✅ Badges eliminados")

# ==================== CREAR BADGES ====================

badges_data = [
    # ========== BADGES DE NIVEL (10 niveles) ==========
    {
        'nombre': 'Semilla 🌱',
        'descripcion': '¡Comenzaste tu camino! Bienvenido a Eki',
        'icono': '🌱',
        'tipo': 'NIVEL',
        'nivel_requerido': 1,
        'puntos_bonus': 10,
        'orden': 1
    },
    {
        'nombre': 'Brote 🌿',
        'descripcion': 'Estás creciendo. Ya tienes experiencia',
        'icono': '🌿',
        'tipo': 'NIVEL',
        'nivel_requerido': 2,
        'puntos_bonus': 20,
        'orden': 2
    },
    {
        'nombre': 'Planta Joven 🍃',
        'descripcion': 'Tu conocimiento florece día a día',
        'icono': '🍃',
        'tipo': 'NIVEL',
        'nivel_requerido': 3,
        'puntos_bonus': 50,
        'orden': 3
    },
    {
        'nombre': 'Cultivo Establecido 🌾',
        'descripcion': 'Nivel intermedio alcanzado. ¡Excelente!',
        'icono': '🌾',
        'tipo': 'NIVEL',
        'nivel_requerido': 4,
        'puntos_bonus': 75,
        'orden': 4
    },
    {
        'nombre': 'Árbol Fuerte 🌳',
        'descripcion': 'Conocimiento sólido. Eres un experto',
        'icono': '🌳',
        'tipo': 'NIVEL',
        'nivel_requerido': 5,
        'puntos_bonus': 100,
        'orden': 5
    },
    {
        'nombre': 'Bosque Sabio 🌲',
        'descripcion': 'Nivel avanzado. Compartes sabiduría',
        'icono': '🌲',
        'tipo': 'NIVEL',
        'nivel_requerido': 6,
        'puntos_bonus': 150,
        'orden': 6
    },
    {
        'nombre': 'Maestro del Campo 🎋',
        'descripcion': 'Dominio completo del conocimiento',
        'icono': '🎋',
        'tipo': 'NIVEL',
        'nivel_requerido': 7,
        'puntos_bonus': 200,
        'orden': 7
    },
    {
        'nombre': 'Flor de Loto 🌺',
        'descripcion': 'Excelencia pura. Inspiras a otros',
        'icono': '🌺',
        'tipo': 'NIVEL',
        'nivel_requerido': 8,
        'puntos_bonus': 300,
        'orden': 8
    },
    {
        'nombre': 'Diamante Verde 💎',
        'descripcion': 'Élite agrícola. Rareza excepcional',
        'icono': '💎',
        'tipo': 'NIVEL',
        'nivel_requerido': 9,
        'puntos_bonus': 500,
        'orden': 9
    },
    {
        'nombre': 'Corona de Oro 👑',
        'descripcion': '¡NIVEL MÁXIMO! Leyenda del agro',
        'icono': '👑',
        'tipo': 'NIVEL',
        'nivel_requerido': 10,
        'puntos_bonus': 1000,
        'orden': 10
    },
    
    # ========== BADGES DE RACHA ==========
    {
        'nombre': 'Fuego Inicial 🔥',
        'descripcion': '3 días consecutivos de aprendizaje',
        'icono': '🔥',
        'tipo': 'RACHA',
        'valor_requerido': 3,
        'puntos_bonus': 30,
        'orden': 11
    },
    {
        'nombre': 'Llamarada 🔥🔥',
        'descripcion': '¡Una semana completa sin fallar!',
        'icono': '🔥🔥',
        'tipo': 'RACHA',
        'valor_requerido': 7,
        'puntos_bonus': 100,
        'orden': 12
    },
    {
        'nombre': 'Incendio Forestal 🔥🔥🔥',
        'descripcion': '2 semanas de constancia total',
        'icono': '🔥🔥🔥',
        'tipo': 'RACHA',
        'valor_requerido': 14,
        'puntos_bonus': 250,
        'orden': 13
    },
    {
        'nombre': 'Volcán Activo 🌋',
        'descripcion': '3 semanas imparables. ¡Increíble!',
        'icono': '🌋',
        'tipo': 'RACHA',
        'valor_requerido': 21,
        'puntos_bonus': 400,
        'orden': 14
    },
    {
        'nombre': 'Sol Eterno ☀️',
        'descripcion': '¡UN MES COMPLETO! Dedicación ejemplar',
        'icono': '☀️',
        'tipo': 'RACHA',
        'valor_requerido': 30,
        'puntos_bonus': 700,
        'orden': 15
    },
    
    # ========== BADGES POR CURSOS ESPECÍFICOS ==========
    {
        'nombre': 'Cafetero Experto ☕',
        'descripcion': 'Completaste el curso de Café con excelencia',
        'icono': '☕',
        'tipo': 'CURSO',
        'puntos_bonus': 200,
        'orden': 16
    },
    {
        'nombre': 'Maestro del Aguacate 🥑',
        'descripcion': 'Dominaste la producción de Aguacate',
        'icono': '🥑',
        'tipo': 'CURSO',
        'puntos_bonus': 200,
        'orden': 17
    },
    {
        'nombre': 'Rey del Plátano 🍌',
        'descripcion': 'Experto en cultivo de Plátano',
        'icono': '🍌',
        'tipo': 'CURSO',
        'puntos_bonus': 200,
        'orden': 18
    },
    {
        'nombre': 'Chocolatero Maestro 🍫',
        'descripcion': 'Maestría en el cultivo de Cacao',
        'icono': '🍫',
        'tipo': 'CURSO',
        'puntos_bonus': 200,
        'orden': 19
    },
    
    # ========== BADGES POR EXÁMENES ==========
    {
        'nombre': 'Primera Victoria 🎯',
        'descripcion': 'Aprobaste tu primer examen',
        'icono': '🎯',
        'tipo': 'EXAMEN',
        'puntos_bonus': 50,
        'orden': 20
    },
    {
        'nombre': 'Perfección 💯',
        'descripcion': 'Sacaste 100% en un examen',
        'icono': '💯',
        'tipo': 'EXAMEN',
        'puntos_bonus': 150,
        'orden': 21
    },
    {
        'nombre': 'Sabio del Examen 📝',
        'descripcion': 'Aprobaste 10 exámenes',
        'icono': '📝',
        'tipo': 'EXAMEN',
        'valor_requerido': 10,
        'puntos_bonus': 300,
        'orden': 22
    },
    
    # ========== BADGES DE PARTICIPACIÓN ==========
    {
        'nombre': 'Primer Paso 👣',
        'descripcion': 'Te inscribiste en tu primer curso',
        'icono': '👣',
        'tipo': 'PARTICIPACION',
        'puntos_bonus': 25,
        'orden': 23
    },
    {
        'nombre': 'Estudiante Dedicado 📚',
        'descripcion': 'Completaste 5 módulos',
        'icono': '📚',
        'tipo': 'PARTICIPACION',
        'valor_requerido': 5,
        'puntos_bonus': 100,
        'orden': 24
    },
    {
        'nombre': 'Maratón de Aprendizaje 🏃',
        'descripcion': 'Completaste 3 módulos en un día',
        'icono': '🏃',
        'tipo': 'PARTICIPACION',
        'puntos_bonus': 150,
        'orden': 25
    },
    {
        'nombre': 'Voz del Campo 🎤',
        'descripcion': 'Enviaste 50 mensajes de audio',
        'icono': '🎤',
        'tipo': 'PARTICIPACION',
        'valor_requerido': 50,
        'puntos_bonus': 75,
        'orden': 26
    },
    
    # ========== BADGES ESPECIALES (Secretos) ==========
    {
        'nombre': 'Madrugador 🌅',
        'descripcion': 'Estudiaste antes de las 6:00 AM',
        'icono': '🌅',
        'tipo': 'ESPECIAL',
        'puntos_bonus': 50,
        'es_secreto': True,
        'orden': 27
    },
    {
        'nombre': 'Búho Nocturno 🦉',
        'descripcion': 'Estudiaste después de las 10:00 PM',
        'icono': '🦉',
        'tipo': 'ESPECIAL',
        'puntos_bonus': 50,
        'es_secreto': True,
        'orden': 28
    },
    {
        'nombre': 'Rayo Veloz ⚡',
        'descripcion': 'Completaste un módulo en menos de 30 minutos',
        'icono': '⚡',
        'tipo': 'ESPECIAL',
        'puntos_bonus': 100,
        'es_secreto': True,
        'orden': 29
    },
    {
        'nombre': 'Coleccionista 🏆',
        'descripcion': 'Completaste TODOS los cursos disponibles',
        'icono': '🏆',
        'tipo': 'ESPECIAL',
        'puntos_bonus': 1000,
        'es_secreto': True,
        'orden': 30
    },
    {
        'nombre': 'Leyenda de Eki 🌟',
        'descripcion': 'Alcanzaste 5000 puntos totales',
        'icono': '🌟',
        'tipo': 'ESPECIAL',
        'puntos_bonus': 2000,
        'es_secreto': True,
        'orden': 31
    },
]

print("\n🏆 Creando badges del sistema...")
badges_creados = 0

for badge_data in badges_data:
    badge = Badge.objects.create(
        nombre=badge_data['nombre'],
        descripcion=badge_data['descripcion'],
        icono=badge_data['icono'],
        tipo=badge_data['tipo'],
        nivel_requerido=badge_data.get('nivel_requerido'),
        valor_requerido=badge_data.get('valor_requerido'),
        puntos_bonus=badge_data['puntos_bonus'],
        es_secreto=badge_data.get('es_secreto', False),
        orden=badge_data['orden'],
        activo=True
    )
    badges_creados += 1
    secreto = " (SECRETO)" if badge.es_secreto else ""
    print(f"   ✅ {badge.icono} {badge.nombre}{secreto} (+{badge.puntos_bonus} pts)")

print(f"\n📊 Total de badges creados: {badges_creados}")

# ==================== ESTADÍSTICAS DE BADGES ====================

print("\n" + "="*70)
print("📊 ESTADÍSTICAS DE BADGES CREADOS\n")

for tipo, nombre_tipo in Badge.TIPO_CHOICES:
    count = Badge.objects.filter(tipo=tipo).count()
    if count > 0:
        print(f"   {nombre_tipo}: {count} badges")

secretos = Badge.objects.filter(es_secreto=True).count()
print(f"   Badges secretos: {secretos}")

print("\n" + "="*70)

# ==================== VERIFICAR PERFILES DE ESTUDIANTES ====================

print("\n🧑‍🌾 Verificando perfiles de gamificación de estudiantes...")

estudiantes = Estudiante.objects.all()
print(f"   Total de estudiantes: {estudiantes.count()}")

perfiles_creados = 0
for estudiante in estudiantes:
    perfil, created = PerfilGamificacion.objects.get_or_create(
        estudiante=estudiante
    )
    if created:
        perfiles_creados += 1

if perfiles_creados > 0:
    print(f"   ✅ {perfiles_creados} perfiles de gamificación creados")
else:
    print(f"   ℹ️ Todos los estudiantes ya tienen perfil de gamificación")

# ==================== MOSTRAR INFORMACIÓN DEL SISTEMA ====================

print("\n" + "="*70)
print("📋 INFORMACIÓN DEL SISTEMA DE GAMIFICACIÓN\n")

print("🎯 NIVELES:")
print("   Nivel 1: 0-50 puntos       🌱 Semilla")
print("   Nivel 2: 50-150 puntos     🌿 Brote")
print("   Nivel 3: 150-300 puntos    🍃 Planta Joven")
print("   Nivel 4: 300-500 puntos    🌾 Cultivo Establecido")
print("   Nivel 5: 500-800 puntos    🌳 Árbol Fuerte")
print("   Nivel 6: 800-1200 puntos   🌲 Bosque Sabio")
print("   Nivel 7: 1200-1700 puntos  🎋 Maestro del Campo")
print("   Nivel 8: 1700-2300 puntos  🌺 Flor de Loto")
print("   Nivel 9: 2300-3000 puntos  💎 Diamante Verde")
print("   Nivel 10: 3000+ puntos     👑 Corona de Oro")

print("\n💰 ACCIONES Y PUNTOS:")
print("   Mensaje enviado: +1 punto")
print("   Audio enviado: +2 puntos")
print("   Módulo iniciado: +10 puntos")
print("   Módulo completado: +100 puntos")
print("   Examen aprobado: +50 puntos base")
print("   Curso completado: +200 puntos")
print("   Primer curso: +300 puntos")

print("\n🔥 RACHAS:")
print("   3 días: +30 puntos + Badge Fuego Inicial")
print("   7 días: +100 puntos + Badge Llamarada")
print("   14 días: +250 puntos + Badge Incendio Forestal")
print("   21 días: +400 puntos + Badge Volcán Activo")
print("   30 días: +700 puntos + Badge Sol Eterno")

print("\n" + "="*70)
        print("✅ SISTEMA DE GAMIFICACIÓN CONFIGURADO EXITOSAMENTE")
        print("="*70 + "\n")

        print("📝 PRÓXIMOS PASOS:")
        print("   1. Los estudiantes automáticamente tendrán perfiles de gamificación")
        print("   2. Los badges se otorgan automáticamente según sus logros")
        print("   3. Ver ranking: Admin → Gamificación → Ranking")
        print("   4. Gestionar badges: Admin → Gamificación → Badges")
        print("\n")
    except Exception as e:
        logger.exception(f"Error al crear datos de gamificación: {e}")
        print(f"\n[ERROR] Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    main()
print("📝 PRÓXIMOS PASOS:")
print("   1. Los estudiantes automáticamente tendrán perfiles de gamificación")
print("   2. Los badges se otorgan automáticamente según sus logros")
print("   3. Ver ranking: Admin → Gamificación → Ranking")
print("   4. Gestionar badges: Admin → Gamificación → Badges")
print("\n")
