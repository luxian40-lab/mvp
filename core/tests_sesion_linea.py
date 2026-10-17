"""La sesión y el log van con la línea. eki inicia; la persona no mezcla las dos."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Cliente, Estudiante, SandboxCanalSesion, WhatsappLog
from core.sandbox_canal import salida_por_phone_id
from core.sandbox_menu import _get_or_create_sesion

PHONE = '495439026995771'
LINEA_2 = '894379507087782'
TEL = '573001110040'


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    WHATSAPP_PHONE_ID=PHONE,
    SANDBOX_WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    WHATSAPP_TOKEN='tok',
    WHATSAPP_API_VERSION='v21.0',
    META_LINEAS='',
    ADMIN_CLIENTES_V2=True,
    SECURE_SSL_REDIRECT=False,
)
class SesionPorLineaTests(TestCase):
    def test_el_modo_de_la_principal_no_se_lleva_a_la_linea_2(self):
        principal = _get_or_create_sesion(TEL)
        principal.modo = 'nat'
        principal.habeas_aceptado = True
        principal.save()
        with salida_por_phone_id(LINEA_2):
            otra = _get_or_create_sesion(TEL)
        self.assertNotEqual(principal.pk, otra.pk)
        self.assertEqual(otra.modo, 'menu')
        self.assertFalse(otra.habeas_aceptado)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono=TEL, phone_id=PHONE).modo,
            'nat',
        )

    def test_la_campana_de_la_linea_2_abre_sesion_en_esa_linea(self):
        from core.campana_audiencia import poner_en_inicio_de_flujo

        org = Cliente.objects.create(
            nombre='Org sesion',
            contacto_principal='A',
            email='sesion@test.com',
            telefono='573001110041',
        )
        est = Estudiante.objects.create(
            cedula='sesion1',
            nombre='Ana',
            telefono=TEL,
            cliente=org,
        )
        poner_en_inicio_de_flujo(est, phone_id=LINEA_2)
        ses = SandboxCanalSesion.objects.get(telefono=TEL, phone_id=LINEA_2)
        self.assertEqual(ses.modo, 'menu')
        self.assertFalse(ses.habeas_aceptado)
        self.assertFalse(
            SandboxCanalSesion.objects.filter(telefono=TEL, phone_id=PHONE).exists()
        )

    @patch('core.lineas.envio.requests.post')
    def test_el_envio_anota_la_linea_por_la_que_salio(self, post):
        from core.lineas.envio import enviar_meta

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'messages': [{'id': 'wamid.linea2'}]}
        post.return_value = resp
        with salida_por_phone_id(LINEA_2):
            resultado = enviar_meta(TEL, 'Hola desde la linea 2')
        self.assertTrue(resultado['success'])
        log = WhatsappLog.objects.get(tipo='SENT', mensaje_id='wamid.linea2')
        self.assertEqual(log.phone_id, LINEA_2)
        self.assertEqual(log.canal, 'meta')
