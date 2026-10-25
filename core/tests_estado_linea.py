"""Fase E: estado del curso por persona y línea."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from core import tests_contrato_dos_lineas as dos_lineas
from core import tests_contrato_estados_motor as estados_motor
from core import tests_contrato_linea_2 as linea_2
from core import tests_contrato_linea_principal as principal
from core.conversacion.estado_linea import EstadoLinea
from core.models import Cliente, Estudiante
from core.planes_linea import PLAN_CURSO_ASESOR
from core.tests_support.contrato_linea import (
    LINEA_2,
    LINEA_PRINCIPAL,
    ContratoLineaTestCase,
    crear_curso,
    mensaje_boton_plantilla,
)

TEL = '573001110021'
CEDULA = '1077700021'


class EstadoLineaModeloTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(cedula='CC5550021', nombre='Eva', telefono=TEL)

    def test_una_fila_por_estudiante_y_linea(self):
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_PRINCIPAL.phone_id)
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_2.phone_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_PRINCIPAL.phone_id)

    def test_se_borra_con_el_estudiante(self):
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_PRINCIPAL.phone_id, estado_chat='ACTIVO')
        self.est.delete()
        self.assertFalse(EstadoLinea.objects.exists())


def _fila(est, linea):
    return EstadoLinea.objects.filter(estudiante=est, phone_id=linea.phone_id).first()


@override_settings(EKI_ESTADO_LINEA_ESCRITURA=True)
class EstadoLineaEscrituraTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Estado Linea',
            contacto_principal='Coord',
            email='estado@eki.test',
            telefono='573000000421',
            activo=True,
            fecha_fin_suscripcion=date(2099, 12, 31),
            plan_linea_meta=PLAN_CURSO_ASESOR,
        )
        crear_curso('General E', catalogo=True, orden=1)
        self.est = Estudiante.objects.create(
            cedula=CEDULA, nombre='Eva Linea', telefono=TEL, cliente=self.org, activo=True,
        )

    def _identidad(self, linea):
        self.lanzar_campana([self.est], linea=linea, nombre=f'e{linea.phone_id[-1]}')
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'), linea=linea)
        self.escribir(TEL, 'acepto', linea=linea)
        self.escribir(TEL, CEDULA, linea=linea)
        self.escribir(TEL, 'si', linea=linea)

    @override_settings(EKI_ESTADO_LINEA_ESCRITURA=False)
    def test_apagado_no_escribe_filas(self):
        self._identidad(LINEA_PRINCIPAL)
        self.assertFalse(EstadoLinea.objects.exists())

    def test_turno_deja_la_fila_de_su_linea_igual_al_estudiante(self):
        self._identidad(LINEA_PRINCIPAL)
        self.est.refresh_from_db()
        fila = _fila(self.est, LINEA_PRINCIPAL)
        self.assertEqual(
            (fila.estado_chat, fila.estado_onboarding, fila.contexto_temporal),
            (self.est.estado_chat, self.est.estado_onboarding, self.est.contexto_temporal),
        )
        self.assertEqual(fila.estado_chat, 'ACTIVO')
        self.assertIsNone(_fila(self.est, LINEA_2))

    def test_turno_de_la_linea_2_escribe_su_propia_fila(self):
        self._identidad(LINEA_PRINCIPAL)
        self._identidad(LINEA_2)
        self.est.refresh_from_db()
        fila_2 = _fila(self.est, LINEA_2)
        self.assertEqual(
            (fila_2.estado_chat, fila_2.estado_onboarding, fila_2.contexto_temporal),
            (self.est.estado_chat, self.est.estado_onboarding, self.est.contexto_temporal),
        )
        self.assertEqual(EstadoLinea.objects.filter(estudiante=self.est).count(), 2)

    def test_campana_de_la_linea_2_escribe_solo_su_fila(self):
        self._identidad(LINEA_PRINCIPAL)
        antes = _fila(self.est, LINEA_PRINCIPAL)
        self.lanzar_campana([self.est], linea=LINEA_2, nombre='e2b')
        fila_2 = _fila(self.est, LINEA_2)
        self.assertEqual((fila_2.estado_chat, fila_2.estado_onboarding), ('ESPERANDO_HABEAS_DATA', 'nuevo'))
        despues = _fila(self.est, LINEA_PRINCIPAL)
        self.assertEqual(
            (despues.estado_chat, despues.estado_onboarding, despues.contexto_temporal),
            (antes.estado_chat, antes.estado_onboarding, antes.contexto_temporal),
        )
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')

    def test_cambio_fuera_de_un_turno_pasa_a_todas_las_filas_solo_en_lo_que_cambia(self):
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_PRINCIPAL.phone_id, estado_chat='ACTIVO',
            estado_onboarding='completado', contexto_temporal={'curso_activo_id': 1},
        )
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_2.phone_id, estado_chat='ACTIVO',
            estado_onboarding='completado', contexto_temporal={'curso_activo_id': 2},
        )
        self.est.estado_onboarding = 'esperando_respuesta_modulo'
        self.est.save(update_fields=['estado_onboarding'])
        self.assertEqual(_fila(self.est, LINEA_PRINCIPAL).estado_onboarding, 'esperando_respuesta_modulo')
        self.assertEqual(_fila(self.est, LINEA_2).estado_onboarding, 'esperando_respuesta_modulo')
        self.assertEqual(_fila(self.est, LINEA_PRINCIPAL).contexto_temporal, {'curso_activo_id': 1})
        self.assertEqual(_fila(self.est, LINEA_2).contexto_temporal, {'curso_activo_id': 2})

    def test_guardar_sin_cambios_no_pisa_las_filas(self):
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_2.phone_id, estado_chat='CONFIRMANDO_DATOS',
            estado_onboarding='nuevo', contexto_temporal={'x': 1},
        )
        self.est.refresh_from_db()
        self.est.save()
        fila = _fila(self.est, LINEA_2)
        self.assertEqual((fila.estado_chat, fila.contexto_temporal), ('CONFIRMANDO_DATOS', {'x': 1}))

    def test_guardar_otro_campo_no_consulta_el_estado(self):
        self.est.nombre = 'Eva Otra'
        with self.assertNumQueries(1):
            self.est.save(update_fields=['nombre'])


@override_settings(SANDBOX_WHATSAPP_PHONE_ID=LINEA_PRINCIPAL.phone_id)
class BackfillEstadoLineaTests(TestCase):
    def setUp(self):
        from core.models import SandboxCanalSesion

        self.est = Estudiante.objects.create(
            cedula='CC5550022', nombre='Eva', telefono=TEL, estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_modulo', contexto_temporal={'curso_activo_id': 7},
        )
        SandboxCanalSesion.objects.create(telefono=TEL, phone_id='', modo='cursos')
        SandboxCanalSesion.objects.create(telefono=TEL, phone_id=LINEA_2.phone_id, modo='menu')
        SandboxCanalSesion.objects.create(telefono='573009999123', phone_id='', modo='menu')

    def _correr(self, *args):
        from io import StringIO

        from django.core.management import call_command

        salida = StringIO()
        call_command('backfill_estado_linea', *args, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_solo_cuenta(self):
        salida = self._correr()
        self.assertIn('sin ficha de estudiante: 1', salida)
        self.assertIn('filas por crear (use --aplicar): 2', salida)
        self.assertFalse(EstadoLinea.objects.exists())

    def test_aplicar_crea_una_fila_por_linea_usada_con_el_estado_del_estudiante(self):
        self._correr('--aplicar')
        for linea in (LINEA_PRINCIPAL, LINEA_2):
            fila = _fila(self.est, linea)
            self.assertEqual(
                (fila.estado_chat, fila.estado_onboarding, fila.contexto_temporal),
                ('ACTIVO', 'esperando_respuesta_modulo', {'curso_activo_id': 7}),
            )

    def test_no_pisa_filas_y_se_puede_repetir(self):
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_2.phone_id, estado_chat='CONFIRMANDO_DATOS',
        )
        self.assertIn('filas creadas: 1', self._correr('--aplicar'))
        self.assertEqual(_fila(self.est, LINEA_2).estado_chat, 'CONFIRMANDO_DATOS')
        self.assertIn('filas creadas: 0', self._correr('--aplicar'))
        self.assertEqual(EstadoLinea.objects.count(), 2)


@override_settings(EKI_ESTADO_LINEA_ESCRITURA=True)
class PrincipalConEscrituraTests(principal.ContratoLineaPrincipalTests):
    """Con la escritura doble prendida la línea principal responde igual."""


@override_settings(EKI_ESTADO_LINEA_ESCRITURA=True)
class Linea2ConEscrituraTests(linea_2.ContratoLinea2Tests):
    """Con la escritura doble prendida la línea 2 responde igual."""


@override_settings(EKI_ESTADO_LINEA_ESCRITURA=True)
class DosLineasConEscrituraTests(dos_lineas.ContratoDosLineasTests):
    """La escritura sola no separa nada: el cruce de hoy sigue igual."""


@override_settings(EKI_ESTADO_LINEA_ESCRITURA=True)
class EstadosMotorConEscrituraTests(estados_motor.ContratoEstadosMotorTests):
    """Los 10 estados del motor responden igual con la escritura doble."""
