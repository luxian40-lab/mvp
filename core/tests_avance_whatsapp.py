from django.test import TestCase

from core.avance_whatsapp import (
    MODO_AVANCE_BOTON,
    MODO_AVANCE_TEXTO,
    CTX_FIN_ENTREGA_MODULO,
    adaptar_mensaje_drip_bloqueo,
    cliente_usa_boton_listo,
    es_mensaje_drip_bloqueo,
    resolver_cta_listo,
    texto_bloqueo_drip_cierre,
)
from core.models import Cliente, Curso, Estudiante


class AvanceWhatsappTests(TestCase):
    def setUp(self):
        self.cliente_texto = Cliente.objects.create(
            nombre='Org Texto',
            contacto_principal='A',
            email='t@test.com',
            telefono='573001111111',
            activo=True,
            modo_avance_modulo=MODO_AVANCE_TEXTO,
        )
        self.cliente_boton = Cliente.objects.create(
            nombre='Org Botón',
            contacto_principal='B',
            email='b@test.com',
            telefono='573002222222',
            activo=True,
            modo_avance_modulo=MODO_AVANCE_BOTON,
        )
        self.curso = Curso.objects.create(
            cliente=self.cliente_boton,
            nombre='Curso prueba',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cliente=self.cliente_boton,
            nombre='Est Test',
            cedula='900001',
            telefono='573003333333',
            activo=True,
        )

    def test_default_es_solo_texto(self):
        self.assertFalse(cliente_usa_boton_listo(self.cliente_texto))
        curso_texto = Curso.objects.create(
            cliente=self.cliente_texto,
            nombre='Curso texto',
            activo=True,
        )
        est_texto = Estudiante.objects.create(
            cliente=self.cliente_texto,
            nombre='Est Texto',
            cedula='900002',
            telefono='573004444444',
            activo=True,
        )
        cta = resolver_cta_listo(est_texto, curso_texto, CTX_FIN_ENTREGA_MODULO)
        self.assertIn('listo', cta.lower())
        self.assertNotIn('[SEND_TEMPLATE:', cta)

    def test_modo_boton_usa_plantilla(self):
        self.assertTrue(cliente_usa_boton_listo(self.cliente_boton))
        cta = resolver_cta_listo(self.est, self.curso, CTX_FIN_ENTREGA_MODULO)
        self.assertTrue(cta.startswith('[SEND_TEMPLATE:HX'))

    def test_drip_bloqueo_sin_boton(self):
        msg = (
            'Estamos preparando tu siguiente sesión\n'
            'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.'
        )
        self.assertTrue(es_mensaje_drip_bloqueo(msg))
        adaptado = adaptar_mensaje_drip_bloqueo(msg, self.est)
        self.assertNotIn('responde *listo*', adaptado.lower())
        self.assertIn('no hace falta', adaptado.lower())

    def test_drip_cierre_texto_vs_boton(self):
        self.assertIn('listo', texto_bloqueo_drip_cierre(self.cliente_texto).lower())
        self.assertNotIn('listo', texto_bloqueo_drip_cierre(self.cliente_boton).lower())
