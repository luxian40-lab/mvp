"""Por qué un teléfono no recibió respuesta en la línea Meta."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import Estudiante, SandboxCanalSesion, WhatsappLog
from core.models_meta_webhook import MetaWebhookEvento
from core.planes_linea import cursos_iniciados_en_el_mes, explicar_plan, preguntas_usadas_mes
from core.utils_telefono import normalizar_e164_co


class Command(BaseCommand):
    help = 'Explica el estado de la línea Meta para un teléfono (sufijo o número).'

    def add_arguments(self, parser):
        parser.add_argument('sufijo', help='Sufijo o número, por ejemplo 7958')
        parser.add_argument(
            '--reset-estado',
            action='store_true',
            help='Pone estado_chat en ACTIVO. No toca el habeas de la línea.',
        )

    def handle(self, *args, **options):
        bruto = (options['sufijo'] or '').strip()
        digitos = normalizar_e164_co(bruto)
        qs = Estudiante.objects.all()
        if len(digitos) >= 10:
            from core.utils_telefono import variantes_telefono

            qs = qs.filter(telefono__in=variantes_telefono(digitos))
        else:
            qs = qs.filter(telefono__endswith=bruto)
        estudiantes = list(qs.order_by('-id')[:20])
        if len(estudiantes) > 1:
            self.stdout.write(self.style.WARNING(
                f'{len(estudiantes)} fichas coinciden. El inbound puede estar usando otra.'
            ))
        if not estudiantes:
            self.stdout.write('Ningún estudiante coincide. Si escribió, el webhook no lo asoció.')
        for est in estudiantes:
            self._ficha(est, reset=bool(options['reset_estado']))
        self._eventos(digitos or bruto)

    def _ficha(self, est, *, reset: bool) -> None:
        tel = est.telefono or ''
        plan = explicar_plan(tel)
        sesion = SandboxCanalSesion.objects.filter(telefono=plan['telefono'] or tel).first()
        cursos = cursos_iniciados_en_el_mes(tel).count()
        preguntas = preguntas_usadas_mes(plan['telefono'] or tel)
        self.stdout.write('---')
        self.stdout.write(
            f'id={est.id} telefono={tel} estado_chat={est.estado_chat} '
            f'opt_out={est.wa_optout_fecha}'
        )
        self.stdout.write(
            f"plan={plan['clave'] or 'vacio'} origen={plan['origen']} causa={plan['causa'] or '-'}"
        )
        self.stdout.write(
            f"cupo_cursos={cursos}/{plan['cursos_mes']} preguntas={preguntas}/{plan['preguntas_mes']}"
        )
        if sesion is None:
            self.stdout.write('sesion=no')
        else:
            self.stdout.write(
                f'sesion modo={sesion.modo} plan_override={sesion.plan or "-"} '
                f'habeas={sesion.habeas_aceptado}'
            )
        if reset and est.estado_chat != 'ACTIVO':
            est.estado_chat = 'ACTIVO'
            est.save(update_fields=['estado_chat'])
            self.stdout.write(self.style.WARNING('estado_chat quedó en ACTIVO'))

    def _eventos(self, clave: str) -> None:
        filtro = clave[-10:] if len(clave) > 10 else clave
        eventos = (
            MetaWebhookEvento.objects.filter(telefono__endswith=filtro)
            .order_by('-id')[:20]
        )
        self.stdout.write('eventos:')
        if not eventos:
            self.stdout.write('  (ninguno: el webhook no vio este teléfono)')
        for ev in eventos:
            self.stdout.write(
                f'  {ev.recibido_en:%Y-%m-%d %H:%M} tipo={ev.tipo} '
                f'resultado={ev.resultado or "-"} error={ev.error or "-"} '
                f'plan={ev.plan_efectivo or "-"} chat={ev.estado_chat_antes or "-"}'
            )
        envios = (
            WhatsappLog.objects.filter(telefono__endswith=filtro, tipo='SENT')
            .order_by('-id')[:20]
        )
        self.stdout.write('envios:')
        if not envios:
            self.stdout.write('  (ninguno)')
        for log in envios:
            self.stdout.write(
                f'  id={log.id} estado={log.estado} error={log.error_codigo or "-"} '
                f'detalle={(log.error_detalle or "")[:80]}'
            )
