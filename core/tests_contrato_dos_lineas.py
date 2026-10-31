"""Contrato A4: la misma persona en las dos líneas.

La sesión de menú va por línea (SandboxCanalSesion por phone_id). El resto vive
en el Estudiante y se comparte: estado_chat, habeas, estado_onboarding y
contexto_temporal (curso activo, reto). Estos tests fijan ese cruce tal como es
hoy; la fase E lo separa y entonces cambian a propósito.
"""
from datetime import date

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Estudiante, ProgresoEstudiante, SandboxCanalSesion
from core.planes_linea import PLAN_CURSO_ASESOR
from core.tests_support.contrato_linea import (
    LINEA_2,
    LINEA_PRINCIPAL,
    ContratoLineaTestCase,
    crear_curso,
    mensaje_boton_plantilla,
)

TEL = '573001110003'
CEDULA = '1077777777'
RESPUESTA_LLM = 'RESPUESTA_LLM_FIJA'


class ContratoDosLineasTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Dos Lineas',
            contacto_principal='Coord',
            email='dos@eki.test',
            telefono='573000000333',
            activo=True,
            fecha_fin_suscripcion=date(2099, 12, 31),
            plan_linea_meta=PLAN_CURSO_ASESOR,
        )
        self.general = crear_curso('General1', catalogo=True, orden=1)
        self.lineal = crear_curso('Lineal1', cliente=self.org, orden=1, modulos=3)
        self.est = Estudiante.objects.create(
            cedula=CEDULA, nombre='Caro Dos', telefono=TEL, cliente=self.org, activo=True,
        )

    def _identidad(self, linea, nombre):
        self.lanzar_campana([self.est], linea=linea, nombre=nombre)
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'), linea=linea)
        self.escribir(TEL, 'acepto', linea=linea)
        self.escribir(TEL, CEDULA, linea=linea)
        return self.escribir(TEL, 'si', linea=linea)

    def _principal_en_modulo_1(self):
        self._identidad(LINEA_PRINCIPAL, 'principal')
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.general.id}', 'Ver curso')
        self.tocar(TEL, f'si_curso_{self.general.id}', 'Sí, este')
        self.tocar(TEL, 'continuemos', 'Continuar')
        inscribir_estudiante_en_curso(self.est, self.lineal)

    def _sesion(self, linea):
        return SandboxCanalSesion.objects.get(telefono=TEL, phone_id=linea.phone_id)

    def _progreso(self, curso):
        return ProgresoEstudiante.objects.get(estudiante=self.est, curso=curso)

    def test_cada_linea_tiene_su_propia_sesion(self):
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        self.assertEqual(SandboxCanalSesion.objects.filter(telefono=TEL).count(), 2)
        self.assertEqual(self._sesion(LINEA_PRINCIPAL).modo, 'cursos')
        self.assertEqual(self._sesion(LINEA_2).modo, 'menu')
        self.escribir(TEL, 'menu')
        self.assertEqual(self._sesion(LINEA_PRINCIPAL).modo, 'menu')
        self.assertEqual(self._sesion(LINEA_2).modo, 'menu')

    def test_cada_respuesta_sale_por_la_linea_que_recibio(self):
        self._principal_en_modulo_1()
        de_la_2 = self._identidad(LINEA_2, 'linea2')
        self.assertEqual({e.phone_id for e in de_la_2}, {LINEA_2.phone_id})
        de_la_1 = self.escribir(TEL, 'menu')
        self.assertEqual({e.phone_id for e in de_la_1}, {LINEA_PRINCIPAL.phone_id})

    def test_hoy_la_campana_de_la_linea_2_vuelve_a_pedir_habeas_en_la_principal(self):
        self._principal_en_modulo_1()
        self.assertTrue(self._sesion(LINEA_PRINCIPAL).habeas_aceptado)
        self.lanzar_campana([self.est], linea=LINEA_2, nombre='linea2')
        envios = self.escribir(TEL, 'listo')
        self.assertEqual(envios[0].phone_id, LINEA_PRINCIPAL.phone_id)
        self.assertEqual(envios[0].ids, ['acepto', 'no_acepto'])
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')

    def test_hoy_continuar_en_la_linea_2_sigue_el_curso_de_la_principal(self):
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        envios = self.escribir(TEL, 'continuemos', linea=LINEA_2)
        self.assertEqual(envios[0].phone_id, LINEA_2.phone_id)
        self.assertIn('*Módulo 2: General1 M2*', envios[0].texto)
        self.assertEqual(self._progreso(self.general).modulo_actual.numero, 2)
        self.assertEqual(self._progreso(self.lineal).modulo_actual.numero, 1)

    def test_hoy_listo_en_la_linea_2_responde_el_reto_de_la_principal(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        self.escribir(TEL, 'listo')
        reto = self.escribir(TEL, 'listo')
        self.assertIn('reto final', reto[0].texto)
        envios = self.escribir(TEL, 'listo', linea=LINEA_2)
        self.assertEqual(envios[0].phone_id, LINEA_2.phone_id)
        self.assertIn(RESPUESTA_LLM, envios[0].texto)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertEqual(self.est.contexto_temporal['progreso_id'], self._progreso(self.general).id)
