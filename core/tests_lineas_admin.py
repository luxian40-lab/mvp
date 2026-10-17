"""Pantalla admin de líneas. Solo lectura, staff."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ConfiguracionGlobal

PHONE = '495439026995771'
LINEA_2 = '894379507087782'
WABA = '111222333'
WABA_2 = '999888777'


@override_settings(
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_PHONE_ID=PHONE,
    SANDBOX_WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_BUSINESS_ACCOUNT_ID_2=WABA_2,
    META_LINEAS='',
)
class LineasAdminTests(TestCase):
    def setUp(self):
        User.objects.create_superuser('lineas_admin', 'lineas@t.com', 'pass12345')
        self.client.login(username='lineas_admin', password='pass12345')

    def test_la_pantalla_dice_quien_inicia_y_como_sigue_cada_linea(self):
        pagina = self.client.get(reverse('admin_lineas_meta'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Versión Meta')
        self.assertContains(pagina, 'Curso lineal')
        self.assertContains(pagina, 'planes mensuales')
        self.assertContains(pagina, 'acabar el curso')
        self.assertContains(pagina, 'eki siempre inicia')
        self.assertContains(pagina, WABA)
        self.assertContains(pagina, WABA_2)

    def test_configuracion_global_ya_no_elige_catalogo_de_linea_2(self):
        cfg = ConfiguracionGlobal.get_solo()
        pagina = self.client.get(
            reverse('admin:core_configuracionglobal_change', args=[cfg.pk]),
        )
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, 'name="cursos_linea_2"')
        self.assertContains(pagina, '/admin/lineas/')
