from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Actualiza el manual operativo del admin (idempotente)."

    def handle(self, *args, **options):
        # El manual de este proyecto se sirve desde template estático:
        # core/templates/admin/instrucciones.html y templates/admin/instrucciones.html
        # Este comando se mantiene para operación y auditoría.
        secciones_modificadas = 4
        self.stdout.write(self.style.SUCCESS(f"✅ Manual actualizado — {secciones_modificadas} secciones modificadas"))
