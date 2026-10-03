"""Lista campañas no ejecutadas que aún tienen destinatarios. No envía."""
from django.core.management.base import BaseCommand

from core.reenganche_meta import campanas_pendientes


class Command(BaseCommand):
    help = 'Campana y CampanaMeta sin ejecutar, con destinatarios, fecha y proveedor.'

    def handle(self, *args, **options):
        filas = campanas_pendientes()
        if not filas:
            self.stdout.write('pendientes=0')
            return
        self.stdout.write(f'pendientes={len(filas)}')
        for fila in filas:
            fecha = fila['fecha'].isoformat() if fila['fecha'] else '(sin fecha)'
            self.stdout.write(
                f"{fila['modelo']} id={fila['id']} fecha={fecha} "
                f"destinatarios={fila['destinatarios']} proveedor={fila['proveedor']} "
                f"nombre={fila['nombre']}"
            )
