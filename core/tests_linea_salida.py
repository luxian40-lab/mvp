"""La segunda línea usa el mismo menú y responde por su propio phone number id."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.sandbox_canal import (
    _graph_messages_url,
    phone_id_de_salida,
    phone_id_es_sandbox,
    salida_por_phone_id,
    to_es_sandbox,
)
from core.views.webhook_meta import _aplicar_sandbox_menu

LINEA_2 = '894379507087782'
PRINCIPAL = '111222333'


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    WHATSAPP_PHONE_ID=PRINCIPAL,
    SANDBOX_WHATSAPP_PHONE_ID=PRINCIPAL,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573208998063',
    BOT_COMERCIAL_SANDBOX_NUMBER='573000000001',
    WHATSAPP_API_VERSION='v21.0',
)
class LineaSalidaTests(TestCase):
    def test_sin_turno_sale_por_la_principal(self):
        self.assertEqual(phone_id_de_salida(), PRINCIPAL)
        self.assertIn(f'/{PRINCIPAL}/messages', _graph_messages_url())

    def test_turno_de_la_linea_2_sale_por_la_linea_2(self):
        with salida_por_phone_id(LINEA_2):
            self.assertEqual(phone_id_de_salida(), LINEA_2)
            self.assertIn(f'/{LINEA_2}/messages', _graph_messages_url())
        self.assertEqual(phone_id_de_salida(), PRINCIPAL)

    def test_twilio_a_cualquiera_de_las_dos_e164_es_la_linea(self):
        self.assertTrue(to_es_sandbox({'To': 'whatsapp:+573208998063'}))
        self.assertTrue(to_es_sandbox({'To': 'whatsapp:+573000000001'}))
        self.assertFalse(to_es_sandbox({'To': 'whatsapp:+573009991111'}))

    def test_phone_id_de_la_linea_2_cuenta_como_sandbox(self):
        self.assertTrue(phone_id_es_sandbox({'_eki_phone_number_id': LINEA_2}))
        self.assertFalse(phone_id_es_sandbox({'_eki_phone_number_id': '000'}))

    def test_el_menu_conserva_el_phone_id_entrante(self):
        visto = {}

        def falso(_data):
            visto['pnid'] = phone_id_de_salida()
            return 'handled'

        inbound = {
            '_eki_proveedor': 'meta',
            '_eki_phone_number_id': LINEA_2,
            'From': 'whatsapp:+573001110099',
            'To': 'whatsapp:+573208998063',
            'Body': 'hola',
            'MessageSid': 'wamid.linea2',
        }
        with patch('core.sandbox_menu.dispatch_sandbox_menu', falso):
            _aplicar_sandbox_menu(inbound)
        self.assertEqual(visto['pnid'], LINEA_2)
