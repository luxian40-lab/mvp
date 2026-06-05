"""
Crea organizaciones y productos de demo para probar Nat + catálogo (sin Excel).

Uso:
  python manage.py migrate
  python manage.py sembrar_catalogo_nat_demo
  python manage.py probar_nat_catalogo --cliente "Agronexo Demo"

No usa workers ni Celery; es instantáneo en consola/SSH.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cliente, ProductoCatalogo

DEMO_ORGS = (
    {
        'nombre': 'Agronexo Demo',
        'nit': '900100001-0',
        'contacto_principal': 'Demo Agronexo',
        'email': 'demo@agronexo.test',
        'telefono': '573001000001',
        'nombre_bot': 'Nat',
        'productos': (
            {
                'nombre': 'Fungicida Café Plus',
                'descripcion': 'Fungicida sistémico para control de roya en café.',
                'problema_que_resuelve': (
                    'roya del café, manchas amarillas en hoja, anillos naranjas, '
                    'humedad alta, pérdida de hoja'
                ),
                'categoria': 'fungicida',
                'cultivos_objetivo': 'café',
                'dosis': '300-500 g por 200 L de agua',
                'precio_cop': 125000,
                'unidad': '500 g',
                'url_producto': 'https://ejemplo.local/agronexo/fungicida-cafe',
            },
            {
                'nombre': 'Bioestimulante Foliar',
                'descripcion': 'Recuperación vegetal tras estrés hídrico o daño foliar.',
                'problema_que_resuelve': (
                    'amarilleo foliar, estrés hídrico, baja vigor, caída de hojas jóvenes'
                ),
                'categoria': 'bioestimulante',
                'cultivos_objetivo': 'café, aguacate',
                'dosis': '2 L por ha en aplicación foliar',
                'precio_cop': 89000,
                'unidad': '1 L',
                'url_producto': 'https://ejemplo.local/agronexo/bioestimulante',
            },
        ),
    },
    {
        'nombre': 'Nitrofert Demo',
        'nit': '900100002-0',
        'contacto_principal': 'Demo Nitrofert',
        'email': 'demo@nitrofert.test',
        'telefono': '573001000002',
        'nombre_bot': 'Nat',
        'productos': (
            {
                'nombre': 'Urea 46% Granular',
                'descripcion': 'Fuente de nitrógeno para corrección de deficiencia.',
                'problema_que_resuelve': (
                    'deficiencia de nitrógeno, amarilleo general, bajo crecimiento vegetativo'
                ),
                'categoria': 'fertilizante',
                'cultivos_objetivo': 'maíz, caña, café',
                'dosis': '1-2 bultos por ha según análisis',
                'precio_cop': 185000,
                'unidad': 'bulto 50 kg',
                'url_producto': 'https://ejemplo.local/nitrofert/urea-46',
            },
            {
                'nombre': 'Herbicida Selectivo',
                'descripcion': 'Control de malezas en post-emergencia.',
                'problema_que_resuelve': (
                    'malezas en surco, competencia por nutrientes, barbecho sucio'
                ),
                'categoria': 'herbicida',
                'cultivos_objetivo': 'maíz',
                'dosis': '1.5 L por ha con boquilla adecuada',
                'precio_cop': 210000,
                'unidad': '1 L',
                'url_producto': 'https://ejemplo.local/nitrofert/herbicida',
            },
        ),
    },
)


class Command(BaseCommand):
    help = 'Crea clientes demo y catálogo Nat para pruebas (sin Excel)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina productos demo y vuelve a crearlos',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = bool(options.get('reset'))
        total_prod = 0

        for spec in DEMO_ORGS:
            cliente, _created = Cliente.objects.update_or_create(
                nombre=spec['nombre'],
                defaults={
                    'nit': spec['nit'],
                    'contacto_principal': spec['contacto_principal'],
                    'email': spec['email'],
                    'telefono': spec['telefono'],
                    'nombre_bot': spec['nombre_bot'],
                    'activo': True,
                },
            )
            if reset:
                ProductoCatalogo.objects.filter(cliente=cliente).delete()

            for p in spec['productos']:
                ProductoCatalogo.objects.update_or_create(
                    cliente=cliente,
                    nombre=p['nombre'],
                    defaults={**p},
                )
                total_prod += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ {cliente.nombre} (id={cliente.id}) — '
                    f'{ProductoCatalogo.objects.filter(cliente=cliente, activo=True).count()} productos'
                )
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {len(DEMO_ORGS)} organizaciones, {total_prod} productos upsert.\n'
            'Configure BOT_COMERCIAL_CLIENTE_ID al id del cliente en Admin.\n'
            'Ver prompt: python manage.py probar_nat_catalogo --cliente "Agronexo Demo"'
        ))
