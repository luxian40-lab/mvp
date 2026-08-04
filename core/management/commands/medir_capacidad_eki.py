"""Estima y documenta límites de capacidad eki (estudiantes / WA concurrente)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.infra_monitor import BASELINE, CAPACITY_LIMITS


class Command(BaseCommand):
    help = 'Mide conteos actuales y publica límites comodos/techo de capacidad eki.'

    def handle(self, *args, **options):
        from datetime import timedelta

        from django.utils import timezone

        from core.models import Estudiante, ProgresoEstudiante, WhatsappLog

        activos = Estudiante.objects.filter(activo=True).count()
        progresos = ProgresoEstudiante.objects.count()
        hace_1h = timezone.now() - timedelta(hours=1)
        wa_1h = WhatsappLog.objects.filter(fecha__gte=hace_1h).count()

        lim = CAPACITY_LIMITS
        self.stdout.write('=== Capacidad eki (documentada) ===')
        self.stdout.write(f'Entorno: {BASELINE["eb_env"]} · RDS {BASELINE["rds_instance"]}')
        self.stdout.write('')
        self.stdout.write('Límites (1× t3.medium + Redis local + RDS micro):')
        for k, v in lim.items():
            if k == 'nota':
                continue
            self.stdout.write(f'  {k}: {v}')
        self.stdout.write(f'  nota: {lim["nota"]}')
        self.stdout.write('')
        self.stdout.write('Estado actual:')
        self.stdout.write(f'  estudiantes activos: {activos}')
        self.stdout.write(f'  progresos (inscripciones): {progresos}')
        self.stdout.write(f'  WhatsAppLog última hora: {wa_1h}')

        if activos > lim['estudiantes_activos_db_techo']:
            self.stdout.write(self.style.ERROR('Sobre techo DB de estudiantes → planificar scale.'))
        elif activos > lim['estudiantes_activos_db_comodo']:
            self.stdout.write(self.style.WARNING('Sobre cómodo DB → vigilar RDS/CPU.'))
        else:
            self.stdout.write(self.style.SUCCESS('Estudiantes dentro de zona cómoda.'))

        if wa_1h > lim['mensajes_wa_concurrentes_techo'] * 60:
            self.stdout.write(self.style.WARNING(
                'Volumen WA/hora alto vs techo concurrente ×60 — revisar WEBHOOK_CELERY_ASYNC.'
            ))
