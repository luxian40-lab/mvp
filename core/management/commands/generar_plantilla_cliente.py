"""
Comando para generar plantilla Excel personalizada para clientes
"""

import csv
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera plantilla CSV/Excel para que clientes registren estudiantes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cliente',
            type=str,
            help='Nombre del cliente para personalizar la plantilla',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='plantilla_estudiantes.csv',
            help='Nombre del archivo de salida (default: plantilla_estudiantes.csv)',
        )
        parser.add_argument(
            '--ejemplos',
            type=int,
            default=3,
            help='Cantidad de filas de ejemplo (default: 3)',
        )

    def handle(self, *args, **options):
        cliente_nombre = options.get('cliente')
        output_file = options.get('output')
        cantidad_ejemplos = options.get('ejemplos', 3)
        
        self.stdout.write('📝 Generando plantilla para registro de estudiantes...\n')
        
        # Encabezados
        headers = ['nombre', 'numero_telefono', 'email', 'notas']
        
        # Datos de ejemplo
        ejemplos = [
            {
                'nombre': 'Juan Pérez Gómez',
                'numero_telefono': '573001234567',
                'email': 'juan.perez@ejemplo.com',
                'notas': 'Productor de café - 15 años experiencia'
            },
            {
                'nombre': 'María González López',
                'numero_telefono': '573007654321',
                'email': 'maria.gonzalez@ejemplo.com',
                'notas': 'Líder cooperativa - Cultivo aguacate'
            },
            {
                'nombre': 'Carlos López Ramírez',
                'numero_telefono': '573009876543',
                'email': '',
                'notas': 'Agricultor - Zona valle'
            },
            {
                'nombre': 'Ana Martínez Silva',
                'numero_telefono': '573005432109',
                'email': 'ana.martinez@ejemplo.com',
                'notas': ''
            },
            {
                'nombre': 'Pedro Ramírez Torres',
                'numero_telefono': '573003456789',
                'email': '',
                'notas': 'Nuevo miembro - Cultivo plátano'
            },
        ]
        
        # Limitar ejemplos según parámetro
        ejemplos = ejemplos[:cantidad_ejemplos]
        
        # Generar CSV
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                
                # Escribir encabezados
                writer.writeheader()
                
                # Escribir ejemplos
                for ejemplo in ejemplos:
                    writer.writerow(ejemplo)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Plantilla generada: {output_file}'))
            self.stdout.write(f'📊 Filas de ejemplo: {len(ejemplos)}')
            
            if cliente_nombre:
                self.stdout.write(f'🏢 Cliente: {cliente_nombre}')
            
            self.stdout.write('\n📋 COLUMNAS:')
            self.stdout.write('  • nombre: Nombre completo (OBLIGATORIO)')
            self.stdout.write('  • numero_telefono: WhatsApp con código país 57XXXXXXXXXX (OBLIGATORIO)')
            self.stdout.write('  • email: Correo electrónico (opcional)')
            self.stdout.write('  • notas: Información adicional (opcional)')
            
            self.stdout.write('\n⚠️  IMPORTANTE:')
            self.stdout.write('  • Números de teléfono SIN espacios ni símbolos')
            self.stdout.write('  • Incluir código de país: 57 para Colombia')
            self.stdout.write('  • Verificar que los números estén activos en WhatsApp')
            self.stdout.write('  • No duplicar números de teléfono')
            
            self.stdout.write('\n📤 Enviar plantilla completada a: soporte@eki.com')
            
            # Generar archivo de instrucciones
            instrucciones_file = output_file.replace('.csv', '_INSTRUCCIONES.txt')
            with open(instrucciones_file, 'w', encoding='utf-8') as f:
                f.write('═' * 70 + '\n')
                f.write('INSTRUCCIONES PARA COMPLETAR PLANTILLA DE ESTUDIANTES - EKI\n')
                f.write('═' * 70 + '\n\n')
                
                if cliente_nombre:
                    f.write(f'Cliente: {cliente_nombre}\n')
                    f.write(f'Fecha: {timezone.now().strftime("%Y-%m-%d")}\n\n')
                
                f.write('📋 COLUMNAS OBLIGATORIAS:\n')
                f.write('  1. nombre: Nombre completo del estudiante\n')
                f.write('  2. numero_telefono: WhatsApp con código país (ej: 573001234567)\n\n')
                
                f.write('📌 COLUMNAS OPCIONALES:\n')
                f.write('  3. email: Correo electrónico\n')
                f.write('  4. notas: Información adicional\n\n')
                
                f.write('⚠️  REGLAS IMPORTANTES:\n')
                f.write('  ✗ NO incluir el símbolo + en números\n')
                f.write('  ✗ NO usar espacios o guiones en números\n')
                f.write('  ✗ NO dejar nombre o número vacíos\n')
                f.write('  ✗ NO duplicar números de teléfono\n\n')
                
                f.write('  ✓ SÍ verificar que números estén activos en WhatsApp\n')
                f.write('  ✓ SÍ incluir código de país (57 para Colombia)\n')
                f.write('  ✓ SÍ revisar que no haya duplicados\n\n')
                
                f.write('📱 FORMATO DE NÚMEROS:\n')
                f.write('  Correcto:   573001234567\n')
                f.write('  Incorrecto: +57 300 123-4567\n')
                f.write('  Incorrecto: 300 123 4567\n\n')
                
                f.write('📤 ENVÍO:\n')
                f.write('  Email: soporte@eki.com\n')
                f.write('  Asunto: "Inscripción Estudiantes - ')
                if cliente_nombre:
                    f.write(cliente_nombre)
                else:
                    f.write('[Nombre Organización]')
                f.write('"\n\n')
                
                f.write('⏱️  TIEMPO DE ACTIVACIÓN:\n')
                f.write('  • Revisión: 24 horas hábiles\n')
                f.write('  • Importación: 2-4 horas\n')
                f.write('  • Envío bienvenida: Inmediato\n')
                f.write('  • Total: 24-48 horas\n\n')
                
                f.write('📞 SOPORTE:\n')
                f.write('  Email: soporte@eki.com\n')
                f.write('  Horario: Lunes a Viernes, 8am - 6pm\n\n')
                
                f.write('✅ CHECKLIST ANTES DE ENVIAR:\n')
                f.write('  [ ] Todas las filas tienen nombre\n')
                f.write('  [ ] Todas las filas tienen número de teléfono\n')
                f.write('  [ ] Los números incluyen código 57\n')
                f.write('  [ ] Los números NO tienen espacios\n')
                f.write('  [ ] No hay números duplicados\n')
                f.write('  [ ] Los números están activos en WhatsApp\n\n')
                
                f.write('═' * 70 + '\n')
                f.write('¡Gracias por elegir EKI! 🌱\n')
                f.write('www.eki.com | soporte@eki.com\n')
                f.write('═' * 70 + '\n')
            
            self.stdout.write(self.style.SUCCESS(f'\n📄 Instrucciones generadas: {instrucciones_file}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error al generar plantilla: {e}'))
