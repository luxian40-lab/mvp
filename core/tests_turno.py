"""C1: el wrapper arma el Turno una vez y lo deja visible mientras dura el mensaje."""
import threading
from unittest.mock import patch

from django.test import SimpleTestCase

from core.conversacion.turno import Turno, turno_activo, turno_actual
from core.lineas.perfil import PERFIL_COMPLETA, PERFIL_SOLO_CURSOS
from core.sandbox_canal import PROVEEDOR_META
from core.tests_support.contrato_linea import LINEA_2, LINEA_PRINCIPAL, ContratoLineaTestCase

WRAPPER = 'core.views.webhook_twilio'


def _turno(linea='x'):
    return Turno(telefono='573001', phone_id='PN', linea=linea, perfil=PERFIL_COMPLETA, canal='meta')


class TurnoContextoTests(SimpleTestCase):
    def test_fuera_de_un_turno_no_hay_turno(self):
        self.assertIsNone(turno_actual())

    def test_activo_y_anidado_se_restauran(self):
        a, b = _turno('a'), _turno('b')
        with turno_activo(a):
            self.assertIs(turno_actual(), a)
            with turno_activo(b):
                self.assertIs(turno_actual(), b)
            self.assertIs(turno_actual(), a)
        self.assertIsNone(turno_actual())

    def test_cada_hilo_ve_su_turno(self):
        vistos = {}
        barrera = threading.Barrier(2)

        def correr(nombre):
            with turno_activo(_turno(nombre)):
                barrera.wait(timeout=5)
                vistos[nombre] = turno_actual().linea

        hilos = [threading.Thread(target=correr, args=(n,)) for n in ('uno', 'dos')]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=5)
        self.assertEqual(vistos, {'uno': 'uno', 'dos': 'dos'})


class TurnoEnElWrapperTests(ContratoLineaTestCase):
    def _procesar(self, post_data):
        from core.views.webhook_twilio import _procesar_twilio_webhook

        capturados = []
        with (
            patch(f'{WRAPPER}._procesar_twilio_webhook_cuerpo', side_effect=lambda _p: capturados.append(turno_actual())),
            patch(f'{WRAPPER}._cortar_certificado_meta', return_value=False),
            patch(f'{WRAPPER}._cortar_habeas_meta', return_value=False),
            patch(f'{WRAPPER}._menu_tras_confirmar_datos_meta', return_value=False),
            patch(f'{WRAPPER}._intentar_aula_twilio_fuera_de_activo', return_value=False),
        ):
            _procesar_twilio_webhook(post_data)
        self.assertEqual(len(capturados), 1)
        self.assertIsNone(turno_actual())
        return capturados[0]

    def _meta(self, linea):
        return {
            '_eki_proveedor': PROVEEDOR_META,
            '_eki_phone_number_id': linea.phone_id,
            'From': 'whatsapp:+573001110071',
            'Body': 'hola',
        }

    def test_meta_linea_2_lleva_su_perfil(self):
        turno = self._procesar(self._meta(LINEA_2))
        self.assertEqual(turno.canal, 'meta')
        self.assertEqual(turno.phone_id, LINEA_2.phone_id)
        self.assertEqual(turno.linea, LINEA_2.nombre)
        self.assertIs(turno.perfil, PERFIL_SOLO_CURSOS)
        self.assertEqual(turno.telefono, '+573001110071')

    def test_meta_principal_lleva_el_perfil_completo(self):
        turno = self._procesar(self._meta(LINEA_PRINCIPAL))
        self.assertEqual(turno.linea, LINEA_PRINCIPAL.nombre)
        self.assertIs(turno.perfil, PERFIL_COMPLETA)

    def test_twilio_no_es_una_linea_meta(self):
        turno = self._procesar({'From': 'whatsapp:+573001110072', 'Body': 'hola'})
        self.assertEqual((turno.canal, turno.phone_id, turno.linea), ('twilio', '', 'twilio'))
        self.assertIs(turno.perfil, PERFIL_COMPLETA)
