"""Enlace y QR de registro. No toca el webhook."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.lineas.registro_enlace import (
    enlace_whatsapp,
    frase_de_cliente,
    leer_frase,
    numero_registro,
    png_qr,
)
from core.models import Cliente


NUMERO = '573019018929'


class FraseRegistroTests(TestCase):
    def test_frase_usa_el_id(self):
        self.assertEqual(frase_de_cliente(12), 'EKI C12')

    def test_leer_cliente_y_general(self):
        self.assertEqual(leer_frase('eki c12'), ('cliente', 12))
        self.assertEqual(leer_frase('  Hola   eki '), ('general', None))
        self.assertIsNone(leer_frase('hola'))
        self.assertIsNone(leer_frase('EKI C'))

    @override_settings(EKI_LINEA_REGISTRO_E164='')
    def test_sin_numero_no_hay_enlace(self):
        self.assertEqual(numero_registro(), '')
        self.assertEqual(enlace_whatsapp('EKI C1'), '')

    @override_settings(EKI_LINEA_REGISTRO_E164='+57 301 901-8929')
    def test_enlace_lleva_el_numero_y_la_frase(self):
        self.assertEqual(numero_registro(), NUMERO)
        self.assertEqual(
            enlace_whatsapp('EKI C4'),
            f'https://wa.me/{NUMERO}?text=EKI%20C4',
        )

    @override_settings(EKI_LINEA_REGISTRO_E164=NUMERO)
    def test_png_es_una_imagen(self):
        png = png_qr(enlace_whatsapp('HOLA EKI'))
        self.assertTrue(png.startswith(b'\x89PNG'))


@override_settings(EKI_LINEA_REGISTRO_E164=NUMERO, SECURE_SSL_REDIRECT=False)
class AdminRegistroEnlaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('qr_cli', 'qr@test.com', 'pass12345')
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(
            nombre='Agricapital',
            contacto_principal='Ana',
            email='agri@test.com',
            telefono='573001112233',
            activo=True,
            fecha_fin_suscripcion=timezone.localdate() + timedelta(days=30),
        )

    def test_la_ficha_muestra_enlace_y_qr(self):
        url = reverse('admin:core_cliente_change', args=[self.cliente.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.content.decode()
        self.assertIn(f'https://wa.me/{NUMERO}?text=EKI%20C{self.cliente.pk}', cuerpo)
        self.assertIn(f'EKI C{self.cliente.pk}', cuerpo)
        self.assertIn(reverse('admin:core_cliente_registro_qr', args=[self.cliente.pk]), cuerpo)
        self.assertIn(f'https://wa.me/{NUMERO}?text=HOLA%20EKI', cuerpo)

    def test_descarga_png_del_cliente(self):
        url = reverse('admin:core_cliente_registro_qr', args=[self.cliente.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertTrue(resp.content.startswith(b'\x89PNG'))

    @override_settings(EKI_LINEA_REGISTRO_E164='')
    def test_sin_numero_el_qr_no_sale(self):
        url = reverse('admin:core_cliente_registro_qr', args=[self.cliente.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
        ficha = self.client.get(reverse('admin:core_cliente_change', args=[self.cliente.pk]))
        self.assertIn('EKI_LINEA_REGISTRO_E164', ficha.content.decode())
