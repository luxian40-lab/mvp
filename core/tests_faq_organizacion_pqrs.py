"""FAQ organización + derivación de contacto en PQRS."""
from django.test import TestCase

from core.faq_organizacion import (
    buscar_faq_organizacion,
    parece_consulta_organizacion,
    texto_contacto_organizacion,
)
from core.models import Cliente, Estudiante, FaqOrganizacion, SolicitudSoporte
from core.pqrs_agent import aplicar_resultado_pqrs, procesar_pqrs_automatico


class TestFaqOrganizacionPqrs(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Org FAQ',
            contacto_principal='Ana Coord',
            email='ana@orgfaq.test',
            telefono='573001110000',
            whatsapp_numero='573001110099',
        )
        self.otro = Cliente.objects.create(
            nombre='Otra Org',
            contacto_principal='Otro',
            email='otro@x.test',
            telefono='573001110001',
        )
        self.est = Estudiante.objects.create(
            cedula='9001',
            nombre='Est FAQ',
            telefono='573009990901',
            cliente=self.cli,
        )
        FaqOrganizacion.objects.create(
            cliente=self.cli,
            pregunta='¿Cuándo pagan el bono de transporte?',
            respuesta='El bono se paga el último viernes de cada mes.',
            palabras_clave='bono, transporte, pago',
        )
        FaqOrganizacion.objects.create(
            cliente=self.otro,
            pregunta='¿Cuándo pagan el bono de transporte?',
            respuesta='NO DEBE VERSE EN LA OTRA ORG',
            palabras_clave='bono, transporte',
        )

    def test_match_faq_solo_cliente_del_estudiante(self):
        faq, score = buscar_faq_organizacion(self.cli, 'hola, cuando pagan el bono de transporte')
        self.assertIsNotNone(faq)
        self.assertEqual(faq.cliente_id, self.cli.pk)
        self.assertIn('último viernes', faq.respuesta)
        self.assertGreaterEqual(score, 0.28)

        faq_otro, _ = buscar_faq_organizacion(self.otro, 'cuando pagan el bono')
        self.assertIsNotNone(faq_otro)
        self.assertEqual(faq_otro.cliente_id, self.otro.pk)

    def test_agente_responde_faq_sin_escalar(self):
        sol = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='necesito saber cuando pagan el bono de transporte',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(sol)
        self.assertEqual(resultado['categoria'], 'organizacion')
        self.assertFalse(resultado['escalar'])
        self.assertIn('último viernes', resultado['respuesta_whatsapp'])
        aplicar_resultado_pqrs(sol, resultado)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'resuelta')
        self.assertTrue(sol.resuelto_por_agente)

    def test_sin_faq_deriva_contacto_y_escala(self):
        self.assertTrue(parece_consulta_organizacion('quiero saber de mi nómina y el convenio'))
        sol = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='quiero saber de mi nómina y el convenio con la empresa',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(sol)
        self.assertEqual(resultado['categoria'], 'organizacion')
        self.assertTrue(resultado['escalar'])
        self.assertIn('Ana Coord', resultado['respuesta_whatsapp'])
        self.assertIn('ana@orgfaq.test', resultado['respuesta_whatsapp'])
        aplicar_resultado_pqrs(sol, resultado)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'pendiente')

    def test_texto_contacto(self):
        t = texto_contacto_organizacion(self.cli)
        self.assertIn('Org FAQ', t)
        self.assertIn('Ana Coord', t)
