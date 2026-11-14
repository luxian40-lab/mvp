"""C4: reporte read-only de drift emitido vs enviado_whatsapp vs WhatsappLog.

No escribe. C5 (backfill) es otro comando/flag; no mezclar.
Uso:
  python manage.py reconciliar_certificados_wa --dias 30
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.lineas.diploma_entrega import _MARCAS_DIPLOMA


class Command(BaseCommand):
    help = 'Lista certificados emitidos sin flag WA que sí tienen mensaje de diploma en el log (dry-run).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30, help='Ventana hacia atrás (default 30)')
        parser.add_argument('--limite', type=int, default=200, help='Máximo de filas a listar')
        parser.add_argument(
            '--cliente-id',
            type=int,
            default=0,
            help='Filtrar por Cliente.id (0 = todos)',
        )

    def handle(self, *args, **options):
        from core.models import WhatsappLog
        from core.models_certificados import Certificado

        dias = max(1, int(options['dias'] or 30))
        limite = max(1, int(options['limite'] or 200))
        desde = timezone.now() - timedelta(days=dias)
        qs = (
            Certificado.objects.filter(emitido=True, enviado_whatsapp=False)
            .filter(Q(fecha_emision__gte=desde) | Q(creado_en__gte=desde))
            .select_related('estudiante', 'curso')
            .order_by('-id')
        )
        cliente_id = int(options.get('cliente_id') or 0)
        if cliente_id:
            qs = qs.filter(estudiante__cliente_id=cliente_id)

        total = qs.count()
        self.stdout.write(
            f'dry_run=1 dias={dias} emitidos_sin_flag={total} limite={limite}'
        )
        mostrados = 0
        con_log = 0
        for cert in qs[:limite]:
            est = cert.estudiante
            tel = ''.join(c for c in str(getattr(est, 'telefono', '') or '') if c.isdigit())
            if len(tel) < 10:
                continue
            logs = WhatsappLog.objects.filter(
                telefono__endswith=tel[-10:],
                tipo='SENT',
                fecha__gte=desde,
            ).order_by('-fecha')[:40]
            hit = None
            for log in logs:
                texto = (log.mensaje or '').lower()
                if any(m in texto for m in _MARCAS_DIPLOMA):
                    hit = log
                    break
            if hit is None:
                continue
            con_log += 1
            mostrados += 1
            self.stdout.write(
                f'cert_id={cert.id} codigo={cert.codigo_verificacion} '
                f'tel=…{tel[-4:]} curso_id={cert.curso_id} '
                f'log_id={hit.id} log_fecha={hit.fecha.isoformat()} '
                f'msg_id={hit.mensaje_id or "-"}'
            )
        self.stdout.write(
            self.style.WARNING(
                f'resumen: candidatos_con_log_diploma={con_log} '
                f'mostrados={mostrados} (sin escribir; C5 = backfill aparte)'
            )
        )
