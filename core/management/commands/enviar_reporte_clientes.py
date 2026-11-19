from django.core.management.base import BaseCommand

from core.reporte_clientes import enviar_reporte_clientes


class Command(BaseCommand):
    help = (
        'Envía el pulso de clientes por correo. '
        'Sin EKI_REPORTE_CLIENTES_EMAIL no sale nada.'
    )

    def handle(self, *args, **options):
        resultado = enviar_reporte_clientes()
        self.stdout.write(str(resultado))
        if not resultado.get('enviado'):
            raise SystemExit(1)
