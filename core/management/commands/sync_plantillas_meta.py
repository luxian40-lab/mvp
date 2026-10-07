"""Trae de Meta el estado de cada plantilla (aprobada, pendiente o rechazada)."""
from django.core.management.base import BaseCommand, CommandError

from core.meta_waba import sincronizar_catalogo_meta


class Command(BaseCommand):
    help = 'Sincroniza el catálogo de plantillas del WABA y muestra si Meta las aprobó.'

    def handle(self, *args, **options):
        resultado = sincronizar_catalogo_meta()
        if not resultado.get('ok'):
            raise CommandError(resultado.get('message') or 'No se pudo leer Meta.')
        filas = resultado.get('filas') or []
        if not filas:
            self.stdout.write('Meta no devolvió plantillas.')
            return
        for fila in filas:
            extra = f" motivo={fila['motivo']}" if fila.get('motivo') else ''
            marca = 'nueva' if fila.get('creada') else 'actualizada'
            self.stdout.write(f"{fila['nombre']} [{fila['idioma']}] {fila['estado']} ({marca}){extra}")
        self.stdout.write(self.style.SUCCESS(f'{len(filas)} plantilla(s).'))
