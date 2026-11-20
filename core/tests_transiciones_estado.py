"""G6: aplicar() equivale a assign directo; validar solo advierte."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.conversacion.estados.transiciones import aplicar


class TransicionesAplicarTests(SimpleTestCase):
    def test_aplicar_igual_que_assign(self):
        est = SimpleNamespace(estado_chat='ESPERANDO_CEDULA', estado_onboarding='completado')
        aplicar(est, estado_chat='CONFIRMANDO_DATOS', fuente='test')
        self.assertEqual(est.estado_chat, 'CONFIRMANDO_DATOS')
        self.assertEqual(est.estado_onboarding, 'completado')

    @override_settings(EKI_VALIDAR_TRANSICIONES=True)
    @patch('core.conversacion.estados.transiciones.logger.warning')
    def test_validar_on_advierte_sin_bloquear(self, warning):
        est = SimpleNamespace(estado_chat='ACTIVO', estado_onboarding='completado')
        aplicar(est, estado_chat='ESPERANDO_HABEAS_DATA', fuente='test_ilegal')
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        warning.assert_called_once()
