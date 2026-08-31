# -*- coding: utf-8 -*-
"""Certificación QA de un módulo antes de publicar en WhatsApp (CLI)."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from core.models import Modulo
from core.modulo_publicacion import (
    evaluar_checklist_publicacion_detalle,
    listar_problemas_media_modulo,
    validar_modulo_qa,
)


class Command(BaseCommand):
    help = (
        'Certifica un módulo para publicación WA: checklist, media apta y HEAD opcional. '
        'Exit 0 = PASS, 1 = FAIL. Sin envío Twilio.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--modulo-id', type=int, required=True)
        parser.add_argument(
            '--sin-head',
            action='store_true',
            help='Omitir HEAD a URLs S3 (solo checklist local)',
        )
        parser.add_argument('--json', action='store_true', help='Salida JSON')

    def handle(self, *args, **options):
        modulo_id = options['modulo_id']
        modulo = (
            Modulo.objects.select_related('curso')
            .filter(pk=modulo_id)
            .first()
        )
        if not modulo:
            raise CommandError(f'Módulo id={modulo_id} no encontrado.')

        head = not options['sin_head']
        checklist = evaluar_checklist_publicacion_detalle(modulo)
        qa = validar_modulo_qa(modulo, head_urls=head)
        media_problemas = listar_problemas_media_modulo(modulo)

        payload = {
            'modulo_id': modulo.pk,
            'curso': getattr(modulo.curso, 'nombre', ''),
            'numero': modulo.numero,
            'titulo': modulo.titulo,
            'publicado_wa': bool(modulo.publicado_wa),
            'head_urls': head,
            'ok': qa.ok,
            'errores': qa.errores,
            'avisos': qa.avisos,
            'media_problemas': media_problemas,
            'n_media_problemas': len(media_problemas),
        }

        if options['json']:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            curso = payload['curso']
            self.stdout.write(
                f'\n=== CERTIFICAR MÓDULO {modulo.numero} (id={modulo.pk}) ===\n'
                f'Curso: {curso}\n'
                f'Título: {modulo.titulo}\n'
                f'Estado WA: {"publicado" if modulo.publicado_wa else "borrador"}\n'
            )
            if media_problemas:
                self.stdout.write(f'\nMedia ({len(media_problemas)} problema(s)):')
                for prob in media_problemas:
                    icon = '🔴' if prob.get('codigo') == 'fail' else '🟡'
                    self.stdout.write(
                        f'  {icon} #{prob.get("orden")} {prob.get("titulo")}: '
                        f'{prob.get("detalle", "")[:120]}'
                    )
            if qa.errores:
                self.stdout.write('\nErrores:')
                for err in qa.errores:
                    self.stdout.write(f'  🔴 {err}')
            if qa.avisos:
                self.stdout.write('\nAvisos:')
                for av in qa.avisos:
                    self.stdout.write(f'  🟡 {av}')
            if not checklist.ok and not qa.errores:
                for err in checklist.errores:
                    self.stdout.write(f'  🔴 {err}')

        if qa.ok:
            self.stdout.write(self.style.SUCCESS('\nQA_PASS — módulo certificado para publicar.'))
            return

        self.stdout.write(self.style.ERROR('\nQA_FAIL — corrige los errores antes de publicar.'))
        raise SystemExit(1)
