"""
Piloto one-shot: cliente + curso 1 módulo + estudiante + aliado geo Usaquén.

Uso (prod vía eb ssh / manage.py):
  python manage.py setup_piloto_usaquen --telefono 3026480629
  python manage.py setup_piloto_usaquen --telefono 3026480629 --simular-ubicacion
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.empleabilidad_prueba import (
    configurar_cliente_empleabilidad,
    preparar_estudiante_prueba,
    simular_ubicacion_whatsapp,
)
from core.models import AliadoEmpleabilidad, Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


# Punto geo público cerca de Av. 9 / Calle 140 (Usaquén / Belmira).
# NO usar marca comercial en nombre mostrado al usuario por WhatsApp (Meta + trademark).
LAT_USAQUEN = 4.7171843
LNG_USAQUEN = -74.0312394
CODIGO = 'EKI-USQ-01'
CLIENTE_NOMBRE = 'eki piloto empleabilidad Usaquén'
CURSO_NOMBRE = 'Piloto empleabilidad — prueba 1 módulo'


def _normalizar_tel(raw: str) -> str:
    digits = ''.join(c for c in (raw or '') if c.isdigit())
    if digits.startswith('57') and len(digits) >= 12:
        return digits
    if len(digits) == 10 and digits.startswith('3'):
        return '57' + digits
    return digits


class Command(BaseCommand):
    help = 'Crea cliente/curso/módulo/estudiante y aliado demo en Usaquén (sin marca comercial en WA).'

    def add_arguments(self, parser):
        parser.add_argument('--telefono', type=str, default='3026480629')
        parser.add_argument(
            '--simular-ubicacion',
            action='store_true',
            help='Ejecuta lógica de pin WhatsApp en servidor (sin Twilio outbound de campaña).',
        )
        parser.add_argument(
            '--reemplazar-aliado',
            action='store_true',
            help='Recrea el aliado EKI-USQ-01 si ya existe.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tel = _normalizar_tel(options['telefono'])
        if len(tel) < 12:
            raise CommandError(f'Teléfono inválido: {options["telefono"]!r} → {tel!r}')

        cliente, created_c = Cliente.objects.get_or_create(
            nombre=CLIENTE_NOMBRE,
            defaults={
                'nit': '900000PILOTO',
                'contacto_principal': 'Piloto eki',
                'email': 'piloto.empleabilidad@eki.technology',
                'telefono': tel,
                'activo': True,
                'portal_productos': 'cursos,empleabilidad',
                'empleabilidad_exploracion_activa': True,
                'empleabilidad_radio_metros': 2000,
            },
        )
        cambios = configurar_cliente_empleabilidad(
            cliente, radio_metros=2000, activar_portal=True
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Cliente id={cliente.id} {'creado' if created_c else 'reusado'} · {cambios or 'flags OK'}"
            )
        )

        curso, created_curso = Curso.objects.get_or_create(
            cliente=cliente,
            nombre=CURSO_NOMBRE,
            defaults={
                'descripcion': 'Curso mínimo para probar radar de empleabilidad por WhatsApp.',
                'activo': True,
                'orden': 1,
            },
        )
        if not created_curso and not curso.activo:
            curso.activo = True
            curso.save(update_fields=['activo'])

        modulo, created_mod = Modulo.objects.get_or_create(
            curso=curso,
            numero=1,
            defaults={
                'titulo': 'Módulo prueba — exploración territorial',
                'descripcion': 'Un solo módulo para validar el flujo de ubicación.',
                'contenido': (
                    'Este módulo es solo de prueba. '
                    'Envía tu ubicación por WhatsApp para descubrir el punto demo cercano '
                    'y valida con el código que te indiquemos en la prueba interna.'
                ),
            },
        )
        self.stdout.write(
            f"Curso id={curso.id} {'creado' if created_curso else 'reusado'} · "
            f"Módulo id={modulo.id} {'creado' if created_mod else 'reusado'}"
        )

        if options['reemplazar_aliado']:
            AliadoEmpleabilidad.objects.filter(
                cliente=cliente, codigo_secreto=CODIGO
            ).delete()

        aliado, created_a = AliadoEmpleabilidad.objects.update_or_create(
            cliente=cliente,
            codigo_secreto=CODIGO,
            defaults={
                # Nombre genérico: no citar marcas ajenas en mensajes a usuarios.
                'nombre_empresa': 'Punto demo Usaquén (Av. 9 con 140)',
                'latitud': LAT_USAQUEN,
                'longitud': LNG_USAQUEN,
                'vacantes_activas': True,
                'cupos_disponibles': 5,
                'prioridad': 5,
                'indicacion_sector': 'esquina Av. 9 con Calle 140, Belmira / Usaquén',
                'vigencia_desde': timezone.localdate(),
                'vigencia_hasta': None,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Aliado id={aliado.id} {'creado' if created_a else 'actualizado'} · "
                f"{aliado.nombre_empresa} · {aliado.latitud},{aliado.longitud} · código {CODIGO}"
            )
        )

        est = Estudiante.objects.filter(telefono=tel).first()
        if est:
            est.cliente = cliente
            est.activo = True
            est.nombre = est.nombre or 'Piloto Usaquén'
            est.municipio = est.municipio or 'Bogotá'
            est.departamento = est.departamento or 'Bogotá, D.C.'
            est.save()
            self.stdout.write(f'Estudiante reusado id={est.id} tel={tel}')
        else:
            est = Estudiante.objects.create(
                cliente=cliente,
                nombre='Piloto Usaquén',
                telefono=tel,
                municipio='Bogotá',
                departamento='Bogotá, D.C.',
                activo=True,
                estado_chat='ACTIVO',
                estado_onboarding='completado',
            )
            self.stdout.write(self.style.SUCCESS(f'Estudiante creado id={est.id} tel={tel}'))

        preparar_estudiante_prueba(est)
        ProgresoEstudiante.objects.get_or_create(
            estudiante=est,
            curso=curso,
            defaults={'modulo_actual': modulo},
        )

        self.stdout.write('')
        self.stdout.write(self.style.WARNING('=== Cumplimiento WhatsApp / marca ==='))
        self.stdout.write(
            '- NO enviamos campaña en frío ni plantilla con marca de terceros.\n'
            '- El aliado se llama «Punto demo…» (coords de referencia pública; sin trademark en el chat).\n'
            '- Para iniciar el radar: TÚ envías el pin de ubicación al WhatsApp de eki '
            '(mensaje iniciado por el usuario = ventana abierta, compliant).\n'
            '- Campaña habeas solo haría falta si el número no existiera y quisieras abrir curso '
            'con plantilla aprobada; para ESTE piloto de ubicación NO es necesaria.'
        )
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Cómo probar ==='))
        self.stdout.write(
            f'1. Desde el celular {tel} abre el chat de eki (el número Twilio educativo).\n'
            f'2. Envía tu *ubicación* (pin) estando cerca de Av. 9 / Calle 140, o desde donde estés '
            f'(si estás lejos verás la distancia al punto demo).\n'
            f'3. Cuando diga que estás cerca, responde el código: *{CODIGO}*\n'
            f'4. Portal (si hay usuario portal del cliente): /portal/empleabilidad/\n'
            f'5. Admin aliado: /admin/learning/aliadoempleabilidad/{aliado.id}/change/'
        )

        if options['simular_ubicacion']:
            texto = simular_ubicacion_whatsapp(est, LAT_USAQUEN, LNG_USAQUEN)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('--- Simulación pin en el punto ---'))
            self.stdout.write(texto)
