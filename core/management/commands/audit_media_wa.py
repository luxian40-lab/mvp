# -*- coding: utf-8 -*-
"""Auditoría media WA (63019/63021) — todos los cursos, sin envío Twilio."""
import json

from django.core.management.base import BaseCommand

from core.media_wa_audit import auditar_media_cursos, filas_a_dict


class Command(BaseCommand):
    help = (
        'Audita pasos con media WA (apto + HEAD). '
        'Ideal: todos los cursos activos. No envía WhatsApp.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--curso-id', type=int, default=None)
        parser.add_argument(
            '--curso-nombre',
            type=str,
            default=None,
            help='Filtro parcial, ej. "Impulso Joven Rural"',
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Incluir cursos inactivos (default: solo activos)',
        )
        parser.add_argument('--sin-head', action='store_true', help='Omitir HEAD S3/URL')
        parser.add_argument('--solo-riesgo', action='store_true', help='Solo fail/warn')
        parser.add_argument('--json', action='store_true', help='Salida JSON')

    def handle(self, *args, **options):
        filas, resumen = auditar_media_cursos(
            curso_id=options['curso_id'],
            curso_nombre=options['curso_nombre'],
            solo_activos=not options['todos'],
            head_urls=not options['sin_head'],
            solo_riesgo=options['solo_riesgo'],
        )

        if options['json']:
            payload = {
                'resumen': {
                    'cursos': resumen.cursos,
                    'pasos_media': resumen.pasos_media,
                    'fail': resumen.fail,
                    'warn': resumen.warn,
                    'ok': resumen.ok,
                    'por_curso': resumen.por_curso,
                },
                'filas': filas_a_dict(filas),
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            f'\n=== AUDITORÍA MEDIA WA ===\n'
            f'Cursos: {resumen.cursos} | Pasos media: {resumen.pasos_media}\n'
            f'🔴 fail: {resumen.fail} | 🟡 warn: {resumen.warn} | 🟢 ok: {resumen.ok}\n'
        )
        for cur_key, counts in sorted(resumen.por_curso.items()):
            if counts['fail'] or counts['warn']:
                self.stdout.write(
                    f'  {cur_key} → fail={counts["fail"]} warn={counts["warn"]} ok={counts["ok"]}'
                )

        for row in filas:
            if row.nivel == 'ok' and options['solo_riesgo']:
                continue
            icon = {'fail': '🔴', 'warn': '🟡', 'ok': '🟢'}.get(row.nivel, '·')
            pub = 'PUB' if row.publicado_wa else 'borrador'
            self.stdout.write(
                f'{icon} [{row.curso_nombre}] M{row.modulo_numero} {pub} '
                f'paso#{row.paso_orden or row.paso_id} {row.paso_titulo[:40]!r}\n'
                f'    apto={row.media_wa_apto} head={row.head_ok} {row.motivo or ""}\n'
                f'    {(row.media_url[-72:])}'
            )

        if resumen.fail:
            self.stdout.write(self.style.ERROR(f'\n{resumen.fail} paso(s) en riesgo alto'))
        elif resumen.warn:
            self.stdout.write(self.style.WARNING(f'\n{resumen.warn} paso(s) a revisar'))
        else:
            self.stdout.write(self.style.SUCCESS('\nSin riesgo detectado en esta pasada'))
