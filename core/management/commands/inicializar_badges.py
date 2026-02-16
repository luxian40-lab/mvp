"""
Comando para inicializar badges del sistema de gamificación
"""

from django.core.management.base import BaseCommand
from core.gamificacion import Badge
from core.models import Curso


class Command(BaseCommand):
    help = 'Inicializa los badges del sistema de gamificación de EKI'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('🎮 INICIALIZANDO SISTEMA DE GAMIFICACIÓN - EKI'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        badges_creados = 0
        
        # 1. BADGES POR NIVEL
        self.stdout.write('📊 Creando badges de nivel...')
        badges_nivel = [
            (1, '🌱 Semilla', 'Comenzaste tu camino educativo'),
            (2, '🌿 Brote', 'Nivel 2 alcanzado'),
            (3, '🍃 Hoja', 'Nivel 3 alcanzado'),
            (4, '🌾 Planta', 'Nivel 4 alcanzado'),
            (5, '🌳 Árbol Joven', 'Nivel 5 alcanzado - ¡Vas muy bien!'),
            (6, '🌲 Árbol Fuerte', 'Nivel 6 alcanzado'),
            (7, '🎋 Bambú Sabio', 'Nivel 7 alcanzado - ¡Experto!'),
            (8, '🌺 Flor Maestra', 'Nivel 8 alcanzado - ¡Impresionante!'),
            (9, '💎 Diamante Rural', 'Nivel 9 alcanzado - ¡Élite!'),
            (10, '👑 Maestro Campesino', 'Nivel máximo - ¡LEYENDA!'),
        ]
        
        for nivel, nombre, descripcion in badges_nivel:
            badge, created = Badge.objects.get_or_create(
                tipo='NIVEL',
                nivel_requerido=nivel,
                defaults={
                    'nombre': nombre,
                    'descripcion': descripcion,
                    'icono': nombre.split()[0],
                    'puntos_bonus': nivel * 10,
                    'orden': nivel
                }
            )
            if created:
                badges_creados += 1
                self.stdout.write(f'  ✅ {nombre} (Nivel {nivel})')
        
        # 2. BADGES POR RACHA
        self.stdout.write('\n🔥 Creando badges de racha...')
        badges_racha = [
            (3, '🔥 Racha Iniciada', 'Mantuviste 3 días consecutivos de actividad'),
            (7, '⚡ Racha Semanal', 'Una semana completa de dedicación'),
            (30, '🌟 Racha Mensual', '¡30 días consecutivos! Eres imparable'),
        ]
        
        for dias, nombre, descripcion in badges_racha:
            badge, created = Badge.objects.get_or_create(
                tipo='RACHA',
                valor_requerido=dias,
                defaults={
                    'nombre': nombre,
                    'descripcion': descripcion,
                    'icono': nombre.split()[0],
                    'puntos_bonus': dias * 5,
                    'orden': 20 + dias
                }
            )
            if created:
                badges_creados += 1
                self.stdout.write(f'  ✅ {nombre} ({dias} días)')
        
        # 3. BADGES POR CURSOS
        self.stdout.write('\n📚 Creando badges de cursos...')
        cursos = Curso.objects.all()
        for curso in cursos:
            badge, created = Badge.objects.get_or_create(
                tipo='CURSO',
                curso_requerido=curso,
                defaults={
                    'nombre': f'{curso.emoji} Experto en {curso.nombre}',
                    'descripcion': f'Completaste el curso de {curso.nombre}',
                    'icono': curso.emoji,
                    'puntos_bonus': 100,
                    'orden': 50
                }
            )
            if created:
                badges_creados += 1
                self.stdout.write(f'  ✅ Experto en {curso.nombre}')
        
        # 4. BADGES ESPECIALES
        self.stdout.write('\n✨ Creando badges especiales...')
        badges_especiales = [
            ('🎯 Primer Paso', 'Te inscribiste en tu primer curso'),
            ('🎓 Estudiante Dedicado', 'Aprobaste 5 exámenes'),
            ('🌟 Estrella Naciente', 'Alcanzaste el top 10 del ranking'),
            ('💬 Conversador', 'Enviaste 100 mensajes'),
            ('🎤 Voz del Campo', 'Enviaste 50 audios'),
            ('🤝 Ayudante', 'Ayudaste a otro estudiante'),
            ('📖 Lector Ávido', 'Completaste 10 módulos'),
            ('🏆 Campeón', 'Obtuviste 10 badges'),
        ]
        
        for i, (nombre, descripcion) in enumerate(badges_especiales):
            badge, created = Badge.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': descripcion,
                    'icono': nombre.split()[0],
                    'tipo': 'ESPECIAL',
                    'puntos_bonus': 50,
                    'orden': 100 + i
                }
            )
            if created:
                badges_creados += 1
                self.stdout.write(f'  ✅ {nombre}')
        
        # 5. BADGE SECRETO
        self.stdout.write('\n🔐 Creando badge secreto...')
        badge_secreto, created = Badge.objects.get_or_create(
            nombre='🎭 El Invisible',
            defaults={
                'descripcion': 'Descubriste el badge secreto',
                'icono': '🎭',
                'tipo': 'ESPECIAL',
                'puntos_bonus': 500,
                'es_secreto': True,
                'orden': 999
            }
        )
        if created:
            badges_creados += 1
            self.stdout.write('  ✅ Badge secreto creado')
        
        # Resumen
        total_badges = Badge.objects.count()
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'✅ {badges_creados} badges nuevos creados'))
        self.stdout.write(self.style.SUCCESS(f'📊 Total de badges en el sistema: {total_badges}'))
        self.stdout.write('='*80 + '\n')
