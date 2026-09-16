"""Evalúa precisión del clasificador territorial v0 (ejemplos etiquetados)."""

from django.core.management.base import BaseCommand

from core.clasificador_senales import precision_ejemplos_etiquetados


class Command(BaseCommand):
    help = 'Precision del clasificador rules_v0 sobre EJEMPLOS_ETIQUETADOS.'

    def handle(self, *args, **options):
        rep = precision_ejemplos_etiquetados()
        self.stdout.write(
            self.style.SUCCESS(
                f"precision={rep['precision']:.1%} ok={rep['ok']}/{rep['total']}"
            )
        )
        for f in rep['fallos']:
            self.stdout.write(
                self.style.WARNING(
                    f"  FAIL «{f['texto']}» esperado={f['esperado']} obtuvo={f['obtenido']}"
                )
            )
