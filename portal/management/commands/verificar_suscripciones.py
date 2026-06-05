from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Cliente


class Command(BaseCommand):
    help = 'Desactiva organizaciones con suscripción vencida'

    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        vencidas = Cliente.objects.filter(
            fecha_fin_suscripcion__lt=hoy,
            activo=True,
        )
        count = vencidas.count()
        vencidas.update(activo=False)
        self.stdout.write(
            self.style.SUCCESS(f'{count} organizaciones desactivadas por vencimiento')
        )
