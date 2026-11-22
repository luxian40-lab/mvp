"""
Comando para crear recompensas de ejemplo configurables
"""

from django.core.management.base import BaseCommand
from core.gamificacion.recompensas import Recompensa


class Command(BaseCommand):
    help = 'Inicializa recompensas de ejemplo en el catálogo'

    def handle(self, *args, **kwargs):
        self.stdout.write('🎁 Inicializando catálogo de recompensas...\n')
        
        recompensas_creadas = 0
        
        # ========== RECOMPENSAS DIGITALES ==========
        self.stdout.write('📱 Creando recompensas digitales...')
        
        digitales = [
            {
                'nombre': 'Guía PDF: Fertilización Orgánica',
                'descripcion': 'Guía completa de 20 páginas sobre fertilización orgánica para cultivos de café y cacao',
                'icono': '📄',
                'tipo': 'DIGITAL',
                'puntos_requeridos': 200,
                'enlace_descarga': 'https://ejemplo.com/guias/fertilizacion.pdf',
                'orden': 1,
            },
            {
                'nombre': 'Video Masterclass: Control de Plagas',
                'descripcion': 'Video de 45 minutos con técnicas profesionales de control de plagas sin químicos',
                'icono': '🎥',
                'tipo': 'DIGITAL',
                'puntos_requeridos': 300,
                'enlace_descarga': 'https://ejemplo.com/videos/plagas.mp4',
                'orden': 2,
            },
            {
                'nombre': 'Calculadora de Costos Agrícolas',
                'descripcion': 'Excel interactivo para calcular costos de producción y rentabilidad',
                'icono': '📊',
                'tipo': 'DIGITAL',
                'puntos_requeridos': 150,
                'enlace_descarga': 'https://ejemplo.com/tools/calculadora.xlsx',
                'orden': 3,
            },
        ]
        
        for data in digitales:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        # ========== CONSULTORÍA ==========
        self.stdout.write('\n💬 Creando consultorias...')
        
        consultorias = [
            {
                'nombre': 'Consultoría 1-a-1 (30 min)',
                'descripcion': 'Sesión personalizada de 30 minutos con experto agrónomo vía WhatsApp',
                'icono': '👨‍🌾',
                'tipo': 'CONSULTORIA',
                'puntos_requeridos': 500,
                'cantidad_disponible': 10,
                'instrucciones_entrega': 'Contactar al estudiante por WhatsApp para agendar sesión',
                'orden': 10,
                'destacado': True,
            },
            {
                'nombre': 'Análisis de Suelo Gratis',
                'descripcion': 'Análisis de laboratorio de muestra de suelo (estudiante envía muestra)',
                'icono': '🧪',
                'tipo': 'CONSULTORIA',
                'puntos_requeridos': 800,
                'cantidad_disponible': 5,
                'nivel_minimo': 5,
                'instrucciones_entrega': 'Coordinar envío de muestra y laboratorio',
                'orden': 11,
                'destacado': True,
            },
        ]
        
        for data in consultorias:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        # ========== CERTIFICADOS ==========
        self.stdout.write('\n🏆 Creando certificados...')
        
        certificados = [
            {
                'nombre': 'Certificado de Experto en Café',
                'descripcion': 'Certificado digital firmado que acredita conocimientos en cultivo de café',
                'icono': '📜',
                'tipo': 'CERTIFICADO',
                'puntos_requeridos': 1000,
                'nivel_minimo': 7,
                'enlace_descarga': 'https://ejemplo.com/certificados/generar',
                'orden': 20,
            },
            {
                'nombre': 'Certificado de Maestro Campesino',
                'descripcion': 'Certificado físico premium enviado a domicilio + digital',
                'icono': '🎓',
                'tipo': 'CERTIFICADO',
                'puntos_requeridos': 2000,
                'nivel_minimo': 10,
                'cantidad_disponible': 20,
                'instrucciones_entrega': 'Imprimir certificado y enviar por correo postal',
                'orden': 21,
                'destacado': True,
            },
        ]
        
        for data in certificados:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        # ========== PRODUCTOS FÍSICOS ==========
        self.stdout.write('\n📦 Creando productos físicos...')
        
        fisicos = [
            {
                'nombre': 'Kit de Semillas Premium',
                'descripcion': '5 variedades de semillas orgánicas certificadas (café, aguacate, cacao, etc.)',
                'icono': '🌱',
                'tipo': 'FISICO',
                'puntos_requeridos': 600,
                'cantidad_disponible': 15,
                'instrucciones_entrega': 'Enviar kit por correo certificado',
                'orden': 30,
            },
            {
                'nombre': 'Herramienta: Tijera de Poda Profesional',
                'descripcion': 'Tijera de poda ergonómica marca Felco - herramienta profesional',
                'icono': '✂️',
                'tipo': 'FISICO',
                'puntos_requeridos': 1200,
                'cantidad_disponible': 8,
                'nivel_minimo': 6,
                'instrucciones_entrega': 'Coordinar envío con proveedor',
                'orden': 31,
            },
        ]
        
        for data in fisicos:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        # ========== DESCUENTOS ==========
        self.stdout.write('\n💰 Creando descuentos...')
        
        descuentos = [
            {
                'nombre': '10% Descuento en Fertilizantes',
                'descripcion': 'Cupón de 10% de descuento en compra de fertilizantes orgánicos (min $50)',
                'icono': '🎟️',
                'tipo': 'DESCUENTO',
                'puntos_requeridos': 300,
                'cantidad_disponible': 50,
                'instrucciones_entrega': 'Enviar código de cupón por WhatsApp',
                'orden': 40,
            },
            {
                'nombre': '25% Descuento en Curso Premium',
                'descripcion': 'Cupón de 25% en cualquier curso premium de la plataforma',
                'icono': '🎫',
                'tipo': 'DESCUENTO',
                'puntos_requeridos': 500,
                'cantidad_disponible': 30,
                'nivel_minimo': 4,
                'instrucciones_entrega': 'Aplicar descuento en siguiente curso',
                'orden': 41,
            },
        ]
        
        for data in descuentos:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        # ========== ACCESOS PREMIUM ==========
        self.stdout.write('\n🔓 Creando accesos premium...')
        
        accesos = [
            {
                'nombre': 'Acceso: Grupo Premium WhatsApp',
                'descripcion': 'Acceso a grupo exclusivo con expertos agrónomos y agricultores exitosos',
                'icono': '👥',
                'tipo': 'ACCESO',
                'puntos_requeridos': 400,
                'instrucciones_entrega': 'Agregar al grupo de WhatsApp premium',
                'orden': 50,
                'destacado': True,
            },
            {
                'nombre': 'Acceso: Biblioteca de Videos (1 mes)',
                'descripcion': 'Acceso ilimitado por 1 mes a biblioteca con 50+ videos educativos',
                'icono': '📺',
                'tipo': 'ACCESO',
                'puntos_requeridos': 350,
                'enlace_descarga': 'https://ejemplo.com/biblioteca/acceso',
                'orden': 51,
            },
        ]
        
        for data in accesos:
            recompensa, created = Recompensa.objects.get_or_create(
                nombre=data['nombre'],
                defaults=data
            )
            if created:
                recompensas_creadas += 1
                self.stdout.write(f'  ✅ {data["icono"]} {data["nombre"]}')
        
        self.stdout.write('\n')
        self.stdout.write(self.style.SUCCESS(f'✅ {recompensas_creadas} recompensas nuevas creadas'))
        self.stdout.write(f'📊 Total en catálogo: {Recompensa.objects.count()}')
        self.stdout.write('\n💡 Ahora puedes editar/crear más recompensas desde Django Admin')
