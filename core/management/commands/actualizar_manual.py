from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica que el manual operativo unificado esté en templates/admin/instrucciones.html"

    def handle(self, *args, **options):
        from pathlib import Path

        from django.conf import settings

        manual = Path(settings.BASE_DIR) / 'templates' / 'admin' / 'instrucciones.html'
        legacy = Path(settings.BASE_DIR) / 'core' / 'templates' / 'admin' / 'instrucciones.html'

        if not manual.is_file():
            self.stderr.write(self.style.ERROR(f'No existe {manual}'))
            return

        if legacy.is_file():
            self.stderr.write(
                self.style.WARNING(
                    f'Existe copia legacy {legacy} — elimínela para evitar confusión (DIRS usa templates/ primero).'
                )
            )

        lines = len(manual.read_text(encoding='utf-8').splitlines())
        self.stdout.write(
            self.style.SUCCESS(
                f'Manual unificado OK — {manual} ({lines} líneas). URL: /admin/instrucciones/'
            )
        )
