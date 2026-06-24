"""Configura cliente, aliados demo y guía para probar empleabilidad por WhatsApp + portal."""

from django.core.management.base import BaseCommand, CommandError

from core.empleabilidad_prueba import (
    completar_mision_con_codigo,
    setup_prueba_empleabilidad,
    simular_ubicacion_whatsapp,
)
from core.models import Cliente, Estudiante


class Command(BaseCommand):
    help = (
        'Activa empleabilidad en un cliente, crea 3 aliados demo con códigos EKI-DEMO-0x '
        'e imprime el checklist para probar por WhatsApp y ver KPIs en el portal.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True, help='ID del Cliente (organización)')
        parser.add_argument(
            '--telefono',
            type=str,
            default='',
            help='Teléfono del estudiante de prueba (573…)',
        )
        parser.add_argument('--lat', type=float, default=4.926, help='Latitud base (default Subachoque)')
        parser.add_argument('--lng', type=float, default=-74.173, help='Longitud base')
        parser.add_argument('--radio', type=int, default=1500, help='Radio de búsqueda en metros')
        parser.add_argument(
            '--base-url',
            type=str,
            default='http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com',
        )
        parser.add_argument(
            '--reemplazar-aliados',
            action='store_true',
            help='Borra aliados EKI-DEMO-* previos del cliente antes de recrearlos',
        )
        parser.add_argument(
            '--sin-portal',
            action='store_true',
            help='No agrega empleabilidad a portal_productos',
        )
        parser.add_argument(
            '--simular-ubicacion',
            action='store_true',
            help='Ejecuta la lógica de ubicación WhatsApp (requiere --telefono)',
        )
        parser.add_argument(
            '--completar-codigo',
            type=str,
            default='',
            help='Simula envío del código secreto en chat (ej. EKI-DEMO-01)',
        )

    def handle(self, *args, **options):
        try:
            cliente = Cliente.objects.get(pk=options['cliente_id'], activo=True)
        except Cliente.DoesNotExist as exc:
            raise CommandError(f'Cliente id={options["cliente_id"]} no encontrado o inactivo.') from exc

        telefono = (options['telefono'] or '').strip()
        resultado = setup_prueba_empleabilidad(
            cliente,
            lat_base=options['lat'],
            lng_base=options['lng'],
            radio_metros=options['radio'],
            telefono=telefono or None,
            activar_portal=not options['sin_portal'],
            reemplazar_aliados=options['reemplazar_aliados'],
            base_url=options['base_url'],
        )

        self.stdout.write(self.style.SUCCESS(f'\n✅ Cliente «{cliente.nombre}» listo para prueba empleabilidad\n'))
        self.stdout.write(f'  exploración activa: {cliente.empleabilidad_exploracion_activa}')
        self.stdout.write(f'  radio: {cliente.empleabilidad_radio_metros} m')
        self.stdout.write(f'  portal_productos: {cliente.portal_productos or "(vacío)"}\n')

        self.stdout.write('Aliados demo:')
        for a in resultado.aliados:
            self.stdout.write(
                f'  • {a.nombre_empresa} | código {a.codigo_secreto} | '
                f'lat={a.latitud}, lng={a.longitud}'
            )

        if telefono:
            est = resultado.estudiante
            if not est:
                self.stdout.write(self.style.WARNING(f'\n⚠️ No hay estudiante activo con teléfono {telefono}'))
            else:
                self.stdout.write(f'\nEstudiante: {est.nombre} (id={est.id}, cliente={est.cliente_id})')
                if est.cliente_id and est.cliente_id != cliente.id:
                    self.stdout.write(self.style.WARNING(
                        '  ⚠️ El estudiante pertenece a otro cliente; la ubicación filtra aliados por su cliente.'
                    ))

                if options['simular_ubicacion']:
                    msg = simular_ubicacion_whatsapp(est, options['lat'], options['lng'])
                    est.refresh_from_db()
                    self.stdout.write(self.style.HTTP_INFO(f'\n📍 Respuesta simulada WhatsApp:\n{msg}\n'))
                    self.stdout.write(f'  estado_onboarding: {est.estado_onboarding}')
                    ctx = est.contexto_temporal or {}
                    self.stdout.write(f'  mision_id: {ctx.get("mision_empleabilidad_id")}')

                codigo = (options['completar_codigo'] or '').strip()
                if codigo:
                    ok, detalle = completar_mision_con_codigo(est, codigo)
                    if ok:
                        self.stdout.write(self.style.SUCCESS(f'\n🏆 {detalle}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'\n❌ {detalle}'))

        self._imprimir_checklist(resultado, telefono, options)

    def _imprimir_checklist(self, resultado, telefono, options):
        base = options['base_url'].rstrip('/')
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('CHECKLIST — prueba real por WhatsApp')
        self.stdout.write('=' * 60)
        self.stdout.write('1. Admin eki → Cliente ya tiene empleabilidad_exploracion_activa ✓')
        self.stdout.write(f'2. Aliados: {resultado.admin_aliados_url}')
        self.stdout.write('3. Desde el celular del estudiante de prueba:')
        if telefono:
            self.stdout.write(f'   • Número: {telefono}')
        else:
            self.stdout.write('   • Use un estudiante inscrito en este cliente (pase --telefono)')
        self.stdout.write('   • Abrir chat con el bot eki')
        self.stdout.write('   • Adjuntar → Ubicación → pin en el punto demo:')
        self.stdout.write(f'     lat={options["lat"]}, lng={options["lng"]}')
        self.stdout.write('     (o ir físicamente cerca del aliado «Parque central»)')
        self.stdout.write('   • El bot debe pedir el código secreto → enviar: EKI-DEMO-01')
        self.stdout.write('4. Verificar misión en admin:')
        self.stdout.write(f'   {resultado.admin_misiones_url}')
        self.stdout.write('5. Portal B2B (usuario con acceso a la org):')
        self.stdout.write(f'   {resultado.portal_url}')
        self.stdout.write('   → deben subir «Misiones completadas» y aparecer en actividad reciente')
        self.stdout.write('\nAPI alternativa (sin WhatsApp):')
        self.stdout.write(
            f'  GET {base}/api/empleabilidad/oportunidades/?telefono=TEL&latitud={options["lat"]}&longitud={options["lng"]}'
        )
        self.stdout.write('\nSimulación local en este servidor:')
        self.stdout.write(
            f'  python manage.py setup_prueba_empleabilidad --cliente-id {options["cliente_id"]} '
            f'--telefono TEL --simular-ubicacion --completar-codigo EKI-DEMO-01'
        )
        self.stdout.write('=' * 60 + '\n')
