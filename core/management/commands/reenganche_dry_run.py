"""Lista a quién le tocaría el reenganche drip, sin enviar."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.reenganche_meta import previsualizar, reenganche_habilitado


class Command(BaseCommand):
    help = 'Cuenta y enmascara a quién le tocaría el reenganche de hoy y los próximos N días.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=1)

    def handle(self, *args, **options):
        plantilla = (getattr(settings, 'META_TEMPLATE_DRIP_REENGANCHE', '') or '').strip()
        self.stdout.write(f"habilitado={'si' if reenganche_habilitado() else 'no'}")
        self.stdout.write(f"plantilla={plantilla or '(vacia)'}")
        for dia in previsualizar(options['dias']):
            self.stdout.write(
                f"{dia['fecha']} candidatos={dia['candidatos']} "
                f"texto={dia['texto']} plantilla={dia['plantilla']} "
                f"omitidos_sin_ventana={dia['omitidos_sin_ventana']}"
            )
            for fila in dia['filas'][:20]:
                self.stdout.write(f"  {fila['telefono']} {fila['modo']} {fila['curso']}")
            resto = dia['candidatos'] - min(dia['candidatos'], 20)
            if resto > 0:
                self.stdout.write(f"  ... {resto} mas")
