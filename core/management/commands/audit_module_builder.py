# -*- coding: utf-8 -*-
"""Auditoría Module Builder WA — solo lectura, sin envío Twilio/WhatsApp."""
from django.core.management.base import BaseCommand

from core.models import Curso, Modulo, PasoModulo
from core.module_steps import pasos_activos_qs
from core.module_structure import modulo_tiene_secciones_intercaladas


class Command(BaseCommand):
    help = (
        'Audita estructura de módulos (intercalado + media_wa_apto). '
        'No envía mensajes WhatsApp.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--curso-id', type=int, default=None)
        parser.add_argument('--solo-activos', action='store_true', default=False)

    def handle(self, *args, **options):
        qs = Curso.objects.all().order_by('id')
        if options['curso_id']:
            qs = qs.filter(id=options['curso_id'])
        if options['solo_activos']:
            qs = qs.filter(activo=True)

        total_inter = 0
        total_video = 0
        total_apto = 0
        total_desconocido = 0
        for curso in qs:
            self.stdout.write(f'\n=== CURSO {curso.id} {curso.nombre} ===')
            for mod in Modulo.objects.filter(curso=curso).order_by('numero', 'id'):
                pasos = list(pasos_activos_qs(mod))
                hall = modulo_tiene_secciones_intercaladas(mod)
                flag = 'INTERCALADO' if hall else 'ok'
                if hall:
                    total_inter += 1
                self.stdout.write(
                    f'  mod {mod.numero} id={mod.id} pasos={len(pasos)} estructura={flag}'
                )
                for h in hall:
                    self.stdout.write(
                        f'    ! sec={h["seccion_id"]} orden={h["orden"]} paso={h["paso_id"]}'
                    )
                for p in pasos:
                    url = (p.media_url or '').strip()
                    if not url:
                        continue
                    if not url.lower().split('?')[0].endswith(('.mp4', '.m4v', '.mov')):
                        continue
                    total_video += 1
                    apto = p.media_wa_apto
                    if apto is True:
                        total_apto += 1
                        tag = 'apto'
                    elif apto is False:
                        tag = 'NO_apto'
                    else:
                        total_desconocido += 1
                        tag = 'desconocido'
                        if 'wa_safe' in url:
                            tag = 'desconocido(wa_safe_url)'
                    self.stdout.write(
                        f'    video paso={p.id} {tag} {(url[-60:])}'
                    )

        self.stdout.write(
            f'\nRESUMEN cursos={qs.count()} mods_intercalados={total_inter} '
            f'videos={total_video} apto={total_apto} desconocido={total_desconocido}'
        )
        self.stdout.write(self.style.SUCCESS('QA lectura OK (sin envíos WA)'))
