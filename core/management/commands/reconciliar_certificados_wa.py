"""C4 dry-run + C5 backfill guardado de enviado_whatsapp vs WhatsappLog.

Dry-run por defecto. --aplicar exige EKI_RECONCILIA_CERT_WA_APLICAR=true,
--cliente-id y --limite (cap 50).
Uso:
  python manage.py reconciliar_certificados_wa --dias 30 --cliente-id 27
  python manage.py reconciliar_certificados_wa --aplicar --cliente-id 27 --limite 20
"""
from __future__ import annotations

import csv
import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from core.lineas.diploma_entrega import _MARCAS_DIPLOMA

_CODIGO_EN_MSG = re.compile(r'certificado_(eki-[A-Za-z0-9-]+)\.(?:png|jpe?g|webp)', re.I)
_CODIGO_PLANO = re.compile(r'\b(eki-[A-Za-z0-9-]{4,})\b', re.I)
_ESTADOS_OK = frozenset({'delivered', 'read', 'sent', 'SENT', 'DELIVERED', 'READ', 'success'})
_ESTADOS_MAL = frozenset({'failed', 'undelivered', 'FAILED', 'UNDELIVERED', 'error'})
_APLICAR_LIMITE_MAX = 50


def _digitos(valor: str) -> str:
    return ''.join(c for c in str(valor or '') if c.isdigit())


def _texto_log(log) -> str:
    return (log.mensaje or '').lower()


def _es_log_diploma(log) -> bool:
    texto = _texto_log(log)
    if any(m in texto for m in _MARCAS_DIPLOMA):
        return True
    agente = (getattr(log, 'agente_usado', '') or '').lower()
    return 'diploma' in agente or agente == 'diploma_meta'


def _log_rechazado(log) -> bool:
    estado = (log.estado or '').strip()
    if estado in _ESTADOS_MAL:
        return True
    texto = _texto_log(log)
    return '131047' in texto or '132001' in texto


def _match_estricto(cert, log, *, aceptar_sent: bool) -> tuple[bool, str]:
    """(ok, motivo). Exige diploma + (código o agente) + estado sano + tel no ambiguo."""
    if not _es_log_diploma(log):
        return False, 'sin_marca_diploma'
    if _log_rechazado(log):
        return False, 'estado_o_error_meta'

    texto = log.mensaje or ''
    codigo = (cert.codigo_verificacion or '').strip()
    m_url = _CODIGO_EN_MSG.search(texto)
    tiene_codigo = bool(codigo) and (
        codigo.lower() in texto.lower()
        or (m_url is not None and m_url.group(1).lower() == codigo.lower())
    )
    agente = (getattr(log, 'agente_usado', '') or '').lower()
    tiene_agente = 'diploma' in agente or agente == 'diploma_meta'
    if not tiene_codigo and not tiene_agente:
        return False, 'sin_codigo_ni_agente'

    estado_l = (log.estado or '').strip().lower()
    if estado_l in {'delivered', 'read'}:
        pass
    elif estado_l in {'sent', 'pending', 'success', ''}:
        if not aceptar_sent and not tiene_codigo:
            return False, 'solo_sent_sin_codigo'
    else:
        return False, f'estado_desconocido:{log.estado}'

    if log.estudiante_id and log.estudiante_id != cert.estudiante_id:
        return False, 'log_otro_estudiante'

    return True, 'ok'


class Command(BaseCommand):
    help = 'Reconciliación enviado_whatsapp vs log diploma (dry-run; --aplicar con flag).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30, help='Ventana hacia atrás (default 30)')
        parser.add_argument('--limite', type=int, default=200, help='Máximo a revisar/aplicar')
        parser.add_argument('--cliente-id', type=int, default=0, help='Cliente.id (obligatorio con --aplicar)')
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Escribe enviado_whatsapp=True (requiere flag env + cliente-id)',
        )
        parser.add_argument(
            '--aceptar-sent',
            action='store_true',
            help='Permite match con estado SENT sin delivered/read si hay código en el mensaje',
        )
        parser.add_argument(
            '--csv',
            default='',
            help='Ruta CSV de auditoría (cert_id,log_id,antes,despues,motivo)',
        )

    def handle(self, *args, **options):
        from core.models import Estudiante, WhatsappLog
        from core.models_certificados import Certificado

        aplicar = bool(options['aplicar'])
        dias = max(1, int(options['dias'] or 30))
        limite = max(1, int(options['limite'] or 200))
        cliente_id = int(options.get('cliente_id') or 0)
        aceptar_sent = bool(options['aceptar_sent'])
        csv_path = (options.get('csv') or '').strip()

        if aplicar:
            if not getattr(settings, 'EKI_RECONCILIA_CERT_WA_APLICAR', False):
                raise CommandError(
                    'C5 bloqueado: ponga EKI_RECONCILIA_CERT_WA_APLICAR=true en el entorno'
                )
            if not cliente_id:
                raise CommandError('--aplicar exige --cliente-id')
            if limite > _APLICAR_LIMITE_MAX:
                raise CommandError(f'--aplicar: --limite máximo {_APLICAR_LIMITE_MAX}')

        desde = timezone.now() - timedelta(days=dias)
        qs = (
            Certificado.objects.filter(emitido=True, enviado_whatsapp=False)
            .filter(Q(fecha_emision__gte=desde) | Q(creado_en__gte=desde))
            .select_related('estudiante', 'curso')
            .order_by('-id')
        )
        if cliente_id:
            qs = qs.filter(estudiante__cliente_id=cliente_id)

        total = qs.count()
        self.stdout.write(
            f"dry_run={0 if aplicar else 1} aplicar={int(aplicar)} "
            f"dias={dias} cliente_id={cliente_id or '-'} "
            f"emitidos_sin_flag={total} limite={limite} aceptar_sent={int(aceptar_sent)}"
        )

        filas_csv = []
        candidatos = 0
        aplicados = 0
        skipped = {'ambiguo': 0, 'sin_match': 0, 'rechazado': 0}

        for cert in qs[:limite]:
            est = cert.estudiante
            tel = _digitos(getattr(est, 'telefono', ''))
            if len(tel) < 10:
                skipped['sin_match'] += 1
                continue
            n_est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).count()
            if n_est != 1:
                skipped['ambiguo'] += 1
                self.stdout.write(f'skip cert_id={cert.id} motivo=tel_ambiguo n={n_est}')
                continue

            logs = WhatsappLog.objects.filter(
                telefono__endswith=tel[-10:],
                tipo='SENT',
                fecha__gte=desde,
            ).order_by('-fecha')[:50]

            hit = None
            motivo_hit = ''
            for log in logs:
                ok, motivo = _match_estricto(cert, log, aceptar_sent=aceptar_sent)
                if ok:
                    hit = log
                    motivo_hit = motivo
                    break
                if motivo.startswith('estado') or motivo == 'log_otro_estudiante':
                    skipped['rechazado'] += 1

            if hit is None:
                skipped['sin_match'] += 1
                continue

            candidatos += 1
            self.stdout.write(
                f'cert_id={cert.id} codigo={cert.codigo_verificacion} '
                f'tel=…{tel[-4:]} curso_id={cert.curso_id} '
                f'log_id={hit.id} estado={hit.estado} motivo={motivo_hit} '
                f'msg_id={hit.mensaje_id or "-"}'
            )
            filas_csv.append({
                'cert_id': cert.id,
                'log_id': hit.id,
                'antes': False,
                'despues': False,
                'motivo': motivo_hit,
            })

            if aplicar:
                cert.enviado_whatsapp = True
                cert.fecha_envio = hit.fecha or timezone.now()
                cert.save(update_fields=['enviado_whatsapp', 'fecha_envio'])
                aplicados += 1
                filas_csv[-1]['despues'] = True
                self.stdout.write(self.style.SUCCESS(f'aplicado cert_id={cert.id}'))

        if csv_path and filas_csv:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', newline='', encoding='utf-8') as fh:
                w = csv.DictWriter(fh, fieldnames=['cert_id', 'log_id', 'antes', 'despues', 'motivo'])
                w.writeheader()
                w.writerows(filas_csv)
            self.stdout.write(f'csv={path}')

        self.stdout.write(
            self.style.WARNING(
                f'resumen: candidatos={candidatos} aplicados={aplicados} '
                f'skip_ambiguo={skipped["ambiguo"]} skip_sin_match={skipped["sin_match"]} '
                f'skip_rechazado={skipped["rechazado"]}'
            )
        )
