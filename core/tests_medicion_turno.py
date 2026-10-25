"""A6: el wrapper anota la duración de cada turno por estado y línea."""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Estudiante, SandboxCanalSesion
from core.tests_support.contrato_linea import LINEA_2, ContratoLineaTestCase, crear_curso

TEL = '573001110070'


class MedicionTurnoTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        org = Cliente.objects.create(
            nombre='Org Medida', contacto_principal='C', email='medida@eki.test', telefono='573000000777',
            activo=True, fecha_fin_suscripcion=date(2099, 12, 31),
        )
        self.est = Estudiante.objects.create(
            cedula='1088888888', nombre='Eva', telefono=TEL, cliente=org, activo=True,
            estado_chat='ACTIVO', acepto_terminos=True, estado_onboarding='completado',
        )
        inscribir_estudiante_en_curso(self.est, crear_curso('Medida1', cliente=org))
        SandboxCanalSesion.objects.create(
            telefono=TEL, phone_id=LINEA_2.phone_id, modo='cursos', habeas_aceptado=True,
        )

    def test_turno_del_motor_anota_estado_linea_y_duracion(self):
        with self.assertLogs('eki.motor.turno', level='INFO') as logs:
            self.escribir(TEL, 'listo', linea=LINEA_2)
        datos = logs.records[-1].motor_turno
        self.assertEqual(datos['estado'], 'completado')
        self.assertEqual(datos['chat'], 'ACTIVO')
        self.assertEqual(datos['linea'], 'Línea 2')
        self.assertEqual(datos['canal'], 'meta')
        self.assertGreaterEqual(datos['ms'], 0)

    @override_settings(EKI_MEDIR_TURNO=False)
    def test_apagado_no_anota(self):
        with self.assertNoLogs('eki.motor.turno', level='INFO'):
            self.escribir(TEL, 'listo', linea=LINEA_2)

    def test_conteo_de_estados_lista_los_de_legado(self):
        salida = StringIO()
        call_command('contar_estados_motor', stdout=salida)
        texto = salida.getvalue()
        self.assertIn('completado: 1', texto)
        self.assertIn('esperando_respuesta_tutor_ia: 0', texto)
        self.assertIn('ACTIVO: 1', texto)
