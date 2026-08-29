# -*- coding: utf-8 -*-
"""Recodifica media WA de un curso (H.264 Main + AAC → S3 wa_safe) y actualiza PasoModulo."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.media_wa_audit import _head_url_ok
from core.models import Curso, Estudiante, PasoModulo, WhatsappLog
from core.module_steps import pasos_activos_qs
from core.twilio_media import (
    _descargar_bytes,
    _subir_bytes_s3,
    evaluar_mp4_listo_whatsapp,
    optimizar_mp4_bytes_whatsapp,
    probe_mp4_codecs,
)


def _es_video(url: str) -> bool:
    low = (url or '').lower().split('?')[0]
    return low.endswith(('.mp4', '.m4v', '.mov'))


def _es_imagen_pdf(url: str) -> bool:
    low = (url or '').lower().split('?')[0]
    return low.endswith(('.jpg', '.jpeg', '.png', '.webp', '.pdf'))


class Command(BaseCommand):
    help = (
        'Recodifica videos MP4 de un curso para WhatsApp (63021) y opcionalmente '
        'marca imágenes/PDF aptas. Sin reenvío WA automático.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--todos-videos',
            action='store_true',
            help='Re-encode todos los MP4 aunque el gate local diga apto',
        )
        parser.add_argument(
            '--solo-imagenes',
            action='store_true',
            help='Solo backfill PNG/PDF con HEAD OK (no toca videos)',
        )
        parser.add_argument(
            '--report-logs',
            action='store_true',
            help='Imprime fallos WA recientes de inscritos en el curso',
        )
        parser.add_argument('--log-dias', type=int, default=60)

    def handle(self, *args, **options):
        curso_id = options['curso_id']
        try:
            curso = Curso.objects.get(pk=curso_id)
        except Curso.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Curso {curso_id} no existe'))
            return

        self.stdout.write(f'=== REPAIR {curso.id} {curso.nombre} ===')

        if options['report_logs']:
            self._report_logs(curso_id, dias=options['log_dias'])

        if options['solo_imagenes']:
            stats = self._backfill_imagenes(curso, dry_run=options['dry_run'])
            self._resumen(stats)
            return

        stats = {'video_ok': 0, 'video_skip': 0, 'video_fail': 0, 'img_ok': 0}
        stats.update(self._repair_videos(curso, options))
        stats.update(self._backfill_imagenes(curso, dry_run=options['dry_run']))
        self._resumen(stats)

    def _report_logs(self, curso_id: int, *, dias: int) -> None:
        desde = timezone.now() - timedelta(days=dias)
        tels = list(
            Estudiante.objects.filter(progresos__curso_id=curso_id)
            .values_list('telefono', flat=True)
            .distinct()
        )
        if not tels:
            self.stdout.write('Sin inscritos / teléfonos.')
            return
        q_tel = Q()
        for t in tels:
            q_tel |= Q(telefono__endswith=str(t)[-10:])
        fallos = (
            WhatsappLog.objects.filter(q_tel, tipo='SENT', fecha__gte=desde)
            .filter(
                Q(estado__iexact='undelivered')
                | Q(estado__iexact='failed')
                | Q(error_detalle__icontains='63021')
                | Q(error_detalle__icontains='63019')
            )
            .order_by('-fecha')[:40]
        )
        self.stdout.write(f'\n--- Fallos WA inscritos curso {curso_id} ({dias}d) ---')
        if not fallos:
            self.stdout.write('  (ninguno en WhatsappLog con 63019/63021/failed)')
            return
        for log in fallos:
            tel = (log.telefono or '')[-10:]
            err = (log.error_detalle or '')[:80]
            msg = (log.mensaje or '')[:100].replace('\n', ' ')
            self.stdout.write(
                f'  {log.fecha:%Y-%m-%d %H:%M} {tel} {log.estado} {err} | {msg}'
            )

    def _repair_videos(self, curso: Curso, options) -> dict:
        stats = {'video_ok': 0, 'video_skip': 0, 'video_fail': 0}
        resultados = []
        dry = options['dry_run']
        todos = options['todos_videos']

        for mod in curso.modulos.all().order_by('numero', 'id'):
            for paso in pasos_activos_qs(mod):
                url = (paso.media_url or '').strip()
                if not url or not _es_video(url):
                    continue
                self.stdout.write(
                    f'\nP{paso.pk} M{mod.numero} apto={paso.media_wa_apto} '
                    f'{(url[-70:])}'
                )
                raw = _descargar_bytes(url)
                if not raw:
                    self.stdout.write(self.style.ERROR('  DOWNLOAD FAIL'))
                    stats['video_fail'] += 1
                    resultados.append({'paso_id': paso.pk, 'ok': False, 'razon': 'download'})
                    continue

                gate = evaluar_mp4_listo_whatsapp(raw)
                if gate.get('apto') and paso.media_wa_apto is True and not todos:
                    self.stdout.write(self.style.SUCCESS('  SKIP gate OK + apto=True'))
                    stats['video_skip'] += 1
                    continue

                self.stdout.write(
                    f'  before {probe_mp4_codecs(raw)} gate={gate.get("razon")} '
                    f'bytes={len(raw)}'
                )
                if dry:
                    self.stdout.write('  DRY-RUN would re-encode')
                    stats['video_skip'] += 1
                    continue

                fixed = optimizar_mp4_bytes_whatsapp(raw)
                gate2 = evaluar_mp4_listo_whatsapp(fixed or b'')
                self.stdout.write(
                    f'  after {probe_mp4_codecs(fixed or b"")} gate={gate2.get("razon")} '
                    f'bytes={len(fixed or b"")}'
                )
                if not fixed or not gate2.get('apto'):
                    stats['video_fail'] += 1
                    resultados.append(
                        {
                            'paso_id': paso.pk,
                            'ok': False,
                            'razon': gate2.get('razon'),
                        }
                    )
                    self.stdout.write(self.style.ERROR('  FAIL encode/gate'))
                    continue

                digest = hashlib.sha1(
                    f'repair-c{curso.pk}-p{paso.pk}-{len(fixed)}'.encode()
                ).hexdigest()[:12]
                key = (
                    f'modulos/pasos/wa_safe/2026/08/'
                    f'repair_paso_{paso.pk}_{digest}_h264_main_faststart.mp4'
                )
                new_url = _subir_bytes_s3(key, fixed, 'video/mp4')
                if not new_url:
                    stats['video_fail'] += 1
                    self.stdout.write(self.style.ERROR('  FAIL S3 upload'))
                    continue

                paso.media_url = new_url
                paso.media_wa_apto = True
                paso.save(update_fields=['media_url', 'media_wa_apto'])
                stats['video_ok'] += 1
                resultados.append({'paso_id': paso.pk, 'ok': True, 'url': new_url})
                self.stdout.write(self.style.SUCCESS(f'  UPDATED {new_url[-80:]}'))

        self.stdout.write('\n' + json.dumps(resultados, ensure_ascii=False, indent=2))
        return stats

    def _backfill_imagenes(self, curso: Curso, *, dry_run: bool) -> dict:
        stats = {'img_ok': 0, 'img_skip': 0}
        for mod in curso.modulos.all().order_by('numero', 'id'):
            for paso in pasos_activos_qs(mod):
                url = (paso.media_url or '').strip()
                if not url or not _es_imagen_pdf(url):
                    continue
                if paso.media_wa_apto is True:
                    stats['img_skip'] += 1
                    continue
                if _head_url_ok(url) is False:
                    self.stdout.write(
                        self.style.WARNING(f'P{paso.pk} imagen HEAD fail — skip')
                    )
                    stats['img_skip'] += 1
                    continue
                if dry_run:
                    self.stdout.write(f'P{paso.pk} DRY-RUN imagen → apto=True')
                    continue
                paso.media_wa_apto = True
                paso.save(update_fields=['media_wa_apto'])
                stats['img_ok'] += 1
                self.stdout.write(f'P{paso.pk} imagen apto=True')
        return stats

    def _resumen(self, stats: dict) -> None:
        self.stdout.write(
            f'\nRESUMEN video_ok={stats.get("video_ok", 0)} '
            f'video_skip={stats.get("video_skip", 0)} '
            f'video_fail={stats.get("video_fail", 0)} '
            f'img_ok={stats.get("img_ok", 0)}'
        )
        if stats.get('video_fail', 0):
            self.stdout.write(self.style.ERROR('REPAIR_FAIL'))
        else:
            self.stdout.write(self.style.SUCCESS('REPAIR_OK'))
