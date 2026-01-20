"""
Script para crear grupos de estudiantes de ejemplo
Ejecutar: python manage.py shell < crear_grupos_ejemplo.py
"""

from core.models import Cliente, Curso
from core.models_extras import GrupoEstudiantes
from django.contrib.auth.models import User

print("🚀 Creando grupos de ejemplo...")

# Obtener o crear un cliente de ejemplo
cliente, created = Cliente.objects.get_or_create(
    nombre="FNC - Federación Nacional de Cafeteros",
    defaults={
        'nit': '860007538-1',
        'contacto_principal': 'Roberto Vélez',
        'email': 'contacto@federaciondecafeteros.org',
        'telefono': '573001234567'
    }
)

if created:
    print(f"✅ Cliente creado: {cliente.nombre}")
else:
    print(f"ℹ️  Cliente existente: {cliente.nombre}")

# Obtener usuario admin (si existe)
try:
    user = User.objects.filter(is_superuser=True).first()
except:
    user = None

# Crear grupos de ejemplo
grupos_data = [
    {
        'nombre': 'Cafeteros Zona Norte',
        'emoji': '☕',
        'descripcion': 'Productores de café de la región norte del país. Especializados en café de altura.',
    },
    {
        'nombre': 'Cafeteros Zona Sur',
        'emoji': '☕',
        'descripcion': 'Productores de café de la región sur. Café orgánico y especial.',
    },
    {
        'nombre': 'Aguacateros 2026',
        'emoji': '🥑',
        'descripcion': 'Cohorte de productores de aguacate iniciando en 2026.',
    },
    {
        'nombre': 'Plataneros del Valle',
        'emoji': '🍌',
        'descripcion': 'Productores de plátano del Valle del Cauca.',
    },
    {
        'nombre': 'Cacaoteros Premium',
        'emoji': '🍫',
        'descripcion': 'Productores de cacao fino de aroma para exportación.',
    },
    {
        'nombre': 'Administradores FNC',
        'emoji': '👔',
        'descripcion': 'Personal administrativo y coordinadores de la federación.',
    },
]

grupos_creados = []

for grupo_data in grupos_data:
    grupo, created = GrupoEstudiantes.objects.get_or_create(
        nombre=grupo_data['nombre'],
        cliente=cliente,
        defaults={
            'emoji': grupo_data['emoji'],
            'descripcion': grupo_data['descripcion'],
            'creado_por': user,
            'activo': True
        }
    )
    
    if created:
        print(f"✅ Grupo creado: {grupo.emoji} {grupo.nombre}")
        grupos_creados.append(grupo)
    else:
        print(f"ℹ️  Grupo existente: {grupo.emoji} {grupo.nombre}")

# Asociar cursos si existen
print("\n📚 Asociando cursos a grupos...")

try:
    # Intentar asociar curso de café
    curso_cafe = Curso.objects.filter(nombre__icontains='café').first()
    if curso_cafe:
        grupo_norte = GrupoEstudiantes.objects.get(nombre='Cafeteros Zona Norte')
        grupo_sur = GrupoEstudiantes.objects.get(nombre='Cafeteros Zona Sur')
        grupo_norte.cursos.add(curso_cafe)
        grupo_sur.cursos.add(curso_cafe)
        print(f"✅ Curso '{curso_cafe.nombre}' asociado a grupos de cafeteros")
    
    # Intentar asociar curso de aguacate
    curso_aguacate = Curso.objects.filter(nombre__icontains='aguacate').first()
    if curso_aguacate:
        grupo_aguacate = GrupoEstudiantes.objects.get(nombre='Aguacateros 2026')
        grupo_aguacate.cursos.add(curso_aguacate)
        print(f"✅ Curso '{curso_aguacate.nombre}' asociado a Aguacateros 2026")
    
    # Intentar asociar curso de plátano
    curso_platano = Curso.objects.filter(nombre__icontains='plátano').first()
    if curso_platano:
        grupo_platano = GrupoEstudiantes.objects.get(nombre='Plataneros del Valle')
        grupo_platano.cursos.add(curso_platano)
        print(f"✅ Curso '{curso_platano.nombre}' asociado a Plataneros del Valle")
    
    # Intentar asociar curso de cacao
    curso_cacao = Curso.objects.filter(nombre__icontains='cacao').first()
    if curso_cacao:
        grupo_cacao = GrupoEstudiantes.objects.get(nombre='Cacaoteros Premium')
        grupo_cacao.cursos.add(curso_cacao)
        print(f"✅ Curso '{curso_cacao.nombre}' asociado a Cacaoteros Premium")

except Exception as e:
    print(f"⚠️  No se pudieron asociar algunos cursos: {str(e)}")

print("\n" + "="*60)
print("✅ ¡Grupos de ejemplo creados exitosamente!")
print("="*60)
print("\n📋 Grupos creados:")
for grupo in GrupoEstudiantes.objects.filter(cliente=cliente):
    cursos_count = grupo.cursos.count()
    estudiantes_count = grupo.estudiantes.count()
    print(f"  {grupo.emoji} {grupo.nombre}")
    print(f"     └─ Estudiantes: {estudiantes_count}")
    print(f"     └─ Cursos: {cursos_count}")

print("\n💡 Siguiente paso:")
print("   1. Ve al admin: /admin/core/grupoestudiantes/")
print("   2. Selecciona un grupo y agrega estudiantes")
print("   3. Crea una campaña y selecciona 'Grupo' como tipo de audiencia")
print("   4. ¡Envía tu primer mensaje grupal!")
print()
