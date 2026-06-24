"""Audita envíos recientes de certificados y plantillas Twilio en WhatsappLog."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import WhatsappLog
from core.models_certificados import Certificado


class Command(BaseCommand):
    help = 'Lista certificados pendientes de WA y logs Twilio recientes (plantilla vs diploma).'

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=int, default=72)

    def handle(self, *args, **options):
        horas = options['horas']
        hace = timezone.now() - timedelta(hours=horas)

        self.stdout.write(f'=== Certificados emitidos sin WhatsApp (últimas {horas}h) ===')
        pend = (
            Certificado.objects.filter(emitido=True, enviado_whatsapp=False, fecha_emision__gte=hace)
            .select_related('estudiante', 'curso')
            .order_by('-fecha_emision')[:50]
        )
        if not pend:
            self.stdout.write('  (ninguno)')
        for c in pend:
            curso = c.curso.nombre if c.curso else '-'
            self.stdout.write(
                f'  {c.codigo_verificacion} | {c.estudiante.nombre} | {c.estudiante.telefono} '
                f'| {curso} | emitido {c.fecha_emision:%Y-%m-%d %H:%M}'
            )

        self.stdout.write('')
        self.stdout.write('=== Últimos envíos SENT (plantilla / certificado / media) ===')
        qs = (
            WhatsappLog.objects.filter(fecha__gte=hace, tipo='SENT')
            .filter(
                Q(mensaje__icontains='Template')
                | Q(mensaje__icontains='HX')
                | Q(mensaje__icontains='FELICIT')
                | Q(mensaje__icontains='certificado')
                | Q(mensaje__icontains='MEDIA')
                | Q(mensaje__icontains='🎓')
                | Q(estado__iexact='failed')
                | Q(estado__iexact='undelivered')
            )
            .order_by('-fecha')[:100]
        )
        for w in qs:
            msg = (w.mensaje or '').replace('\n', ' ')[:110]
            err = (w.error_detalle or '')[:90]
            self.stdout.write(
                f'{w.fecha:%m-%d %H:%M} ...{w.telefono[-6:]} | {w.estado:12} | {msg}'
                + (f' | ERR: {err}' if err else '')
            )

        self.stdout.write('')
        self.stdout.write('=== Fallos Twilio (failed / undelivered / error) ===')
        fallos = (
            WhatsappLog.objects.filter(fecha__gte=hace)
            .filter(Q(estado__iexact='failed') | Q(estado__iexact='undelivered') | Q(estado__iexact='error'))
            .order_by('-fecha')[:50]
        )
        if not fallos:
            self.stdout.write('  (ninguno registrado en WhatsappLog)')
        for w in fallos:
            self.stdout.write(
                f'{w.fecha:%m-%d %H:%M} ...{w.telefono[-6:]} | {w.estado} | '
                f'{(w.mensaje or "")[:70]} | {(w.error_detalle or "")[:80]}'
            )

        self.stdout.write('')
        self.stdout.write('=== Resumen por teléfono (plantilla + cert mismo día) ===')
        from collections import defaultdict

        por_tel: dict[str, list] = defaultdict(list)
        for w in WhatsappLog.objects.filter(fecha__gte=hace, tipo='SENT').order_by('telefono', 'fecha'):
            blob = (w.mensaje or '').lower()
            if 'template' in blob or 'felicit' in blob or '🎓' in blob or 'media' in blob:
                por_tel[w.telefono[-10:]].append((w.fecha, blob[:40], w.estado))

        solo_plantilla = 0
        con_diploma = 0
        for tel, msgs in por_tel.items():
            tiene_tpl = any('template' in m[1] for m in msgs)
            tiene_cert = any('felicit' in m[1] or '🎓' in m[1] or 'media' in m[1] for m in msgs)
            if tiene_tpl and not tiene_cert:
                solo_plantilla += 1
            if tiene_cert:
                con_diploma += 1
        self.stdout.write(f'  Teléfonos con plantilla sin diploma visible en log: {solo_plantilla}')
        self.stdout.write(f'  Teléfonos con diploma en log: {con_diploma}')
