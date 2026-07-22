"""Tests modo diagnóstico Nati — anamnesis clínica y sin bucles."""

from django.test import TestCase

from core.contexto_agro import extraer_campos_desde_mensaje, obtener_o_crear_contexto
from core.models import Cliente, SesionComercial
from core.nat_diagnostico import siguiente_pregunta_diagnostico


class NatDiagnosticoLoopTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Diag',
            contacto_principal='A',
            email='diag@test.co',
            telefono='573009990001',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009990001',
            cliente=self.cliente,
        )
        self.ctx = obtener_o_crear_contexto(self.sesion)
        self.ctx.cultivo = 'tomate'
        self.ctx.region = 'Boyaca'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

    def test_extrae_manchas_y_no_crece(self):
        self.assertIn('mancha', extraer_campos_desde_mensaje('Tiene manchas').get('problema', '').lower())
        prob = extraer_campos_desde_mensaje('No crece hay brote negro').get('problema', '').lower()
        self.assertTrue('no crece' in prob or 'brote' in prob)

    def test_extrae_guateque_desde_depto_municipio(self):
        campos = extraer_campos_desde_mensaje('Boyaca guateque')
        self.assertEqual(campos.get('municipio'), 'Guateque')
        self.assertEqual(campos.get('region'), 'Boyaca')

    def test_no_repite_pregunta_problema_con_texto_libre(self):
        """Regresión prod: usuario responde síntoma pero regex no lo capturaba → bucle."""
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Las plantas están muy débiles y el follaje se cae',
        )
        self.ctx.refresh_from_db()
        self.assertTrue((self.ctx.problema or '').strip())
        self.assertNotEqual(
            pregunta,
            '¿Puede describir con más detalle el problema que observa en las plantas?',
        )
        # Debe avanzar a anamnesis personalizada (extensión), no repetir síntoma
        self.assertIsNotNone(pregunta)
        self.assertIn('tomate', pregunta.lower())

    def test_preguntas_personalizadas_mencionan_cultivo(self):
        self.ctx.problema = 'manchas amarillas'
        self.ctx.municipio = 'Guateque'
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'manchas amarillas')
        self.assertIsNotNone(pregunta)
        low = pregunta.lower()
        self.assertTrue('tomate' in low or 'entendido' in low)
        self.assertIn('parte', low)

    def test_flujo_anamnesis_completa_hasta_foto(self):
        self.ctx.problema = 'manchas en hojas'
        self.ctx.municipio = 'Guateque'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

        p1 = siguiente_pregunta_diagnostico(self.ctx, 'manchas en hojas')
        self.assertIn('parte', (p1 or '').lower())

        p2 = siguiente_pregunta_diagnostico(self.ctx, 'En las hojas de abajo, como media parcela')
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('extension_afectada'))
        self.assertTrue(
            'cuánto' in (p2 or '').lower() or 'apareció' in (p2 or '').lower()
        )

        p3 = siguiente_pregunta_diagnostico(self.ctx, 'Hace como 8 días y va empeorando')
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('tiempo_problema'))
        self.assertIn('etapa', (p3 or '').lower())

        p4 = siguiente_pregunta_diagnostico(self.ctx, 'Floración')
        self.ctx.refresh_from_db()
        self.assertTrue((self.ctx.etapa or '').strip())
        self.assertIn('aplicado', (p4 or '').lower())

        p5 = siguiente_pregunta_diagnostico(self.ctx, 'Solo riego, no he fumigado')
        self.ctx.refresh_from_db()
        self.assertTrue(
            self.ctx.metadata.get('manejo_previo')
            or self.ctx.metadata.get('fertilizacion_reciente')
        )
        self.assertIn('foto', (p5 or '').lower())

        p6 = siguiente_pregunta_diagnostico(self.ctx, 'sin foto')
        self.assertIsNone(p6)

    def test_clima_con_ubicacion_salta_diagnostico(self):
        self.ctx.municipio = 'Guateque'
        self.ctx.metadata = {}  # sin anamnesis en curso
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Primero clima, ¿puedo fumigar mañana?',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_omitido'))

    def test_saltar_desactiva_diagnostico(self):
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'saltar')
        self.ctx.refresh_from_db()
        self.assertIsNone(pregunta)
        self.assertTrue(self.ctx.metadata.get('diagnostico_omitido'))

    def test_ack_sin_eco_de_pedido_largo(self):
        from core.nat_diagnostico import _ack, _sintoma_corto

        self.ctx.problema = (
            'es amarillamiento que podemos hacer en Boyaca. '
            'Con es amarillamiento que podemos hacer en tomate'
        )
        self.ctx.municipio = 'Guateque'
        self.ctx.save()
        corto = _sintoma_corto(self.ctx)
        self.assertNotIn('podemos hacer', corto.lower())
        self.assertIn('amarill', corto.lower())
        msg = _ack(
            self.ctx,
            '¿en qué parte de la planta empezó (hojas, tallo, fruto, raíz) '
            'y aproximadamente qué tanto del lote está afectado?',
        )
        self.assertNotIn('Entendido:', msg)
        self.assertNotIn('podemos hacer', msg.lower())
        self.assertIn('parte de la planta', msg.lower())
        self.assertTrue(msg.startswith('En tomate'))
