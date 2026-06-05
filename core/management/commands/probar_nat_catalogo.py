"""
Muestra en consola el system prompt de Nat con catálogo (sin llamar OpenAI).

Uso:
  python manage.py probar_nat_catalogo --cliente "Agronexo Demo"
  python manage.py probar_nat_catalogo --cliente-id 12
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Cliente, ProductoCatalogo
from core.nati import armar_system_prompt, obtener_contexto_productos


class Command(BaseCommand):
    help = 'Imprime el system prompt de Nat con catálogo del cliente (prueba local)'

    def add_arguments(self, parser):
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument('--cliente', help='Nombre exacto del Cliente (organización)')
        g.add_argument('--cliente-id', type=int, help='ID del Cliente')

    def handle(self, *args, **options):
        if options.get('cliente_id'):
            cliente = Cliente.objects.filter(pk=options['cliente_id']).first()
        else:
            cliente = Cliente.objects.filter(nombre__iexact=options['cliente']).first()

        if not cliente:
            raise CommandError(
                'Cliente no encontrado. Disponibles: '
                f'{list(Cliente.objects.filter(activo=True).values_list("nombre", flat=True)[:20])}'
            )

        n = ProductoCatalogo.objects.filter(cliente=cliente, activo=True).count()
        ctx = obtener_contexto_productos(cliente)
        prompt = armar_system_prompt(cliente=cliente)

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Nat — {cliente.nombre} (id={cliente.id}) — {n} productos activos ===\n'
        ))
        if ctx:
            self.stdout.write('--- Bloque catálogo (extracto) ---\n')
            self.stdout.write(ctx[:2500])
            if len(ctx) > 2500:
                self.stdout.write('\n... [truncado]\n')
        else:
            self.stdout.write(self.style.WARNING('Sin catálogo cargado para este cliente.\n'))

        self.stdout.write('\n--- System prompt (últimos 2000 chars) ---\n')
        self.stdout.write(prompt[-2000:])
