"""Crea la fila de estado por línea de quien ya tiene sesión en esa línea.

Fase E del plan de modularidad. Antes de prender EKI_ESTADO_LINEA_LECTURA cada
persona necesita su fila en las líneas que ya usó; si no, la primera vez la fila
nace del estado compartido, que puede ser el de la otra línea.

Solo crea filas que faltan, copiando estado_chat, estado_onboarding y
contexto_temporal del estudiante. No toca filas que ya existen.

    python manage.py backfill_estado_linea            # cuenta, no escribe
    python manage.py backfill_estado_linea --aplicar
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crea EstadoLinea desde las sesiones por línea (por defecto solo cuenta).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Escribe las filas que faltan.')

    def handle(self, *args, **options):
        from core.conversacion.estado_linea import CAMPOS, EstadoLinea
        from core.models import SandboxCanalSesion
        from core.sandbox_canal import sandbox_phone_id
        from core.utils_telefono import estudiante_por_telefono

        aplicar = options['aplicar']
        principal = sandbox_phone_id()
        sesiones = sin_ficha = existentes = nuevas = 0
        vistas = set()
        for telefono, phone_id in SandboxCanalSesion.objects.values_list('telefono', 'phone_id').iterator():
            sesiones += 1
            est = estudiante_por_telefono(telefono)
            if est is None:
                sin_ficha += 1
                continue
            linea = (phone_id or '').strip() or principal
            if not linea or (est.pk, linea) in vistas:
                continue
            vistas.add((est.pk, linea))
            if EstadoLinea.objects.filter(estudiante_id=est.pk, phone_id=linea).exists():
                existentes += 1
                continue
            nuevas += 1
            if aplicar:
                datos = {c: getattr(est, c) for c in CAMPOS}
                datos['estado_chat'] = datos['estado_chat'] or ''
                datos['estado_onboarding'] = datos['estado_onboarding'] or ''
                EstadoLinea.objects.get_or_create(estudiante_id=est.pk, phone_id=linea, defaults=datos)
        verbo = 'creadas' if aplicar else 'por crear (use --aplicar)'
        self.stdout.write(f'sesiones: {sesiones}')
        self.stdout.write(f'sin ficha de estudiante: {sin_ficha}')
        self.stdout.write(f'filas que ya estaban: {existentes}')
        self.stdout.write(f'filas {verbo}: {nuevas}')
