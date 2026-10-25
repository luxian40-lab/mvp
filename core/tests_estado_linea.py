"""Fase E: estado del curso por persona y línea."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from core import tests_contrato_dos_lineas as dos_lineas
from core import tests_contrato_estados_motor as estados_motor
from core import tests_contrato_linea_2 as linea_2
from core import tests_contrato_linea_principal as principal
from core import tests_seleccion_curso_cadena as seleccion
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


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class EnLineaLecturaTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(
            cedula='CC5550023', nombre='Eva', telefono=TEL, estado_chat='ACTIVO',
            estado_onboarding='completado', contexto_temporal={'curso_activo_id': 1},
        )
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_PRINCIPAL.phone_id, estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_reto', contexto_temporal={'curso_activo_id': 1},
        )
        EstadoLinea.objects.create(
            estudiante=self.est, phone_id=LINEA_2.phone_id, estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_modulo', contexto_temporal={'curso_activo_id': 2},
        )

    def _columna(self):
        return Estudiante.objects.filter(pk=self.est.pk).values(
            'estado_chat', 'estado_onboarding', 'contexto_temporal',
        ).first()

    def test_la_lectura_prende_la_escritura(self):
        from core.conversacion.estado_linea import escritura_activa

        self.assertTrue(escritura_activa())

    def test_el_turno_entra_con_el_estado_de_su_linea_y_lo_deja_en_su_fila(self):
        from core.conversacion.estado_linea import en_linea

        with en_linea(LINEA_2.phone_id, lambda: Estudiante.objects.get(pk=self.est.pk)):
            dentro = self._columna()
            est = Estudiante.objects.get(pk=self.est.pk)
            est.estado_onboarding = 'esperando_respuesta_asistente'
            est.save(update_fields=['estado_onboarding'])
        self.assertEqual(dentro['estado_onboarding'], 'esperando_respuesta_modulo')
        self.assertEqual(dentro['contexto_temporal'], {'curso_activo_id': 2})
        self.assertEqual(_fila(self.est, LINEA_2).estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual(_fila(self.est, LINEA_PRINCIPAL).estado_onboarding, 'esperando_respuesta_reto')
        self.assertEqual(_fila(self.est, LINEA_PRINCIPAL).contexto_temporal, {'curso_activo_id': 1})

    def test_linea_sin_fila_sigue_con_el_compartido_y_la_crea_al_salir(self):
        from core.conversacion.estado_linea import en_linea

        otra = '100000000000003'
        with en_linea(otra, lambda: Estudiante.objects.get(pk=self.est.pk)):
            dentro = self._columna()
        self.assertEqual(dentro['estado_onboarding'], 'completado')
        fila = EstadoLinea.objects.get(estudiante=self.est, phone_id=otra)
        self.assertEqual((fila.estado_onboarding, fila.contexto_temporal), ('completado', {'curso_activo_id': 1}))

    def test_sin_cargar_no_toca_la_columna(self):
        from core.conversacion.estado_linea import en_linea

        with en_linea(LINEA_2.phone_id, lambda: self.est, cargar=False, copiar_al_salir=False):
            dentro = self._columna()
        self.assertEqual(dentro['estado_onboarding'], 'completado')
        self.assertEqual(_fila(self.est, LINEA_2).estado_onboarding, 'esperando_respuesta_modulo')

    def test_campana_nueva_en_una_linea_nace_sin_el_contexto_de_otra(self):
        from core.campana_audiencia import poner_en_inicio_de_flujo

        otra = '100000000000003'
        poner_en_inicio_de_flujo(self.est, otra)
        fila = EstadoLinea.objects.get(estudiante=self.est, phone_id=otra)
        self.assertEqual(
            (fila.estado_chat, fila.estado_onboarding, fila.contexto_temporal),
            ('ESPERANDO_HABEAS_DATA', 'nuevo', None),
        )
        self.assertEqual(_fila(self.est, LINEA_PRINCIPAL).estado_onboarding, 'esperando_respuesta_reto')


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class DosLineasConLecturaTests(dos_lineas.ContratoDosLineasTests):
    """Contrato A4 con la lectura prendida: cada línea sigue su propio estado.

    El habeas sigue siendo de la persona (decisión del 25 de octubre de 2026): una
    campaña de cualquier línea lo vuelve a pedir en todas. Lo que no se cruza es el
    estado del curso. Hueco que queda: el avance (ProgresoEstudiante) no tiene línea,
    así que sin curso activo en su contexto la línea 2 ofrece todos los cursos abiertos.
    """

    def test_hoy_la_campana_de_la_linea_2_vuelve_a_pedir_habeas_en_la_principal(self):
        self._principal_en_modulo_1()
        self.lanzar_campana([self.est], linea=LINEA_2, nombre='linea2')
        envios = self.escribir(dos_lineas.TEL, 'listo')
        self.assertEqual(envios[0].phone_id, LINEA_PRINCIPAL.phone_id)
        self.assertEqual(envios[0].ids, ['acepto', 'no_acepto'])
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ACTIVO')
        self.assertEqual(_fila(self.est, LINEA_2).estado_chat, 'ESPERANDO_HABEAS_DATA')

    def test_hoy_continuar_en_la_linea_2_sigue_el_curso_de_la_principal(self):
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        envios = self.escribir(dos_lineas.TEL, 'continuemos', linea=LINEA_2)
        self.assertEqual(envios[0].phone_id, LINEA_2.phone_id)
        self.assertNotIn('General1 M2', envios[0].texto)
        self.assertEqual(self._progreso(self.general).modulo_actual.numero, 1)
        principal = self.tocar(dos_lineas.TEL, 'continuemos', 'Continuar')
        self.assertIn('*Módulo 2: General1 M2*', principal[0].texto)

    def test_hoy_listo_en_la_linea_2_responde_el_reto_de_la_principal(self):
        self.salida.llm_responde(dos_lineas.RESPUESTA_LLM)
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        self.escribir(dos_lineas.TEL, 'listo')
        reto = self.escribir(dos_lineas.TEL, 'listo')
        self.assertIn('reto final', reto[0].texto)
        antes = _fila(self.est, LINEA_PRINCIPAL)
        envios = self.escribir(dos_lineas.TEL, 'listo', linea=LINEA_2)
        self.assertEqual(envios[0].phone_id, LINEA_2.phone_id)
        self.assertNotIn(dos_lineas.RESPUESTA_LLM, envios[0].texto)
        despues = _fila(self.est, LINEA_PRINCIPAL)
        self.assertEqual(
            (despues.estado_onboarding, despues.contexto_temporal),
            (antes.estado_onboarding, antes.contexto_temporal),
        )
        self.assertEqual(despues.contexto_temporal['progreso_id'], self._progreso(self.general).id)


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class PrincipalConLecturaTests(principal.ContratoLineaPrincipalTests):
    """Quien usa una sola línea no nota la lectura por línea."""


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class Linea2ConLecturaTests(linea_2.ContratoLinea2Tests):
    """Quien usa una sola línea no nota la lectura por línea."""


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class EstadosMotorConLecturaTests(estados_motor.ContratoEstadosMotorTests):
    """Los 10 estados del motor responden igual con la lectura por línea."""


@override_settings(EKI_ESTADO_LINEA_LECTURA=True)
class SeleccionCursoConLecturaTests(seleccion.SeleccionCursoDosCopiasTests):
    """Las dos copias de la selección de curso siguen atendiendo lo mismo."""


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
