"""Pruebas adversariales: intentar romper anamnesis Nati mid-conversation."""

from django.test import TestCase

from core.contexto_agro import obtener_o_crear_contexto
from core.models import Cliente, SesionComercial
from core.nat_diagnostico import reiniciar_diagnostico, siguiente_pregunta_diagnostico


class NatDiagnosticoAdversarialTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Adv',
            contacto_principal='A',
            email='adv@test.co',
            telefono='573009990099',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009990099',
            cliente=self.cliente,
        )
        self.ctx = obtener_o_crear_contexto(self.sesion)
        self.ctx.cultivo = 'tomate'
        self.ctx.region = 'Boyaca'
        self.ctx.municipio = 'Guateque'
        self.ctx.problema = 'manchas en hojas'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

    def test_riego_en_paso_temprano_no_aborta(self):
        """Antes el clima FP mataba anamnesis en pasos 1–3 sin _pregunto_*."""
        # Sin extensión aún → paso temprano
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'Solo riego en las mañanas')
        self.ctx.refresh_from_db()
        self.assertFalse(
            self.ctx.metadata.get('diagnostico_omitido'),
            'riego mid-interview no debe omitir diagnóstico',
        )
        self.assertIsNotNone(pregunta)
        self.assertIn('parte', (pregunta or '').lower())

    def test_aplicar_fertilizante_no_aborta_en_curso(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Apliqué fertilizante la semana pasada',
        )
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))
        self.assertIsNotNone(pregunta)

    def test_manejo_riego_fumigar_guarda_y_sigue(self):
        self.ctx.metadata = {
            'diagnostico_activo': True,
            'extension_afectada': 'hojas inferiores, media parcela',
            'tiempo_problema': 'hace 8 días empeorando',
            '_pregunto_etapa': True,
            'etapa_consultada': True,
        }
        self.ctx.etapa = 'Floración'
        self.ctx.save()
        # Dispara pregunta de manejo
        p_manejo = siguiente_pregunta_diagnostico(self.ctx, 'Floración')
        self.assertIn('aplicado', (p_manejo or '').lower())

        p_foto = siguiente_pregunta_diagnostico(self.ctx, 'Solo riego, no he fumigado')
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))
        self.assertTrue(
            self.ctx.metadata.get('manejo_previo')
            or self.ctx.metadata.get('fertilizacion_reciente')
        )
        self.assertIn('foto', (p_foto or '').lower())

    def test_clima_explicito_si_aborta_aunque_activo(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Primero clima, ¿puedo fumigar mañana?',
        )
        self.ctx.refresh_from_db()
        self.assertIsNone(pregunta)
        self.assertTrue(self.ctx.metadata.get('diagnostico_omitido'))

    def test_reiniciar_limpia_omit_sticky(self):
        self.ctx.metadata = {
            'diagnostico_omitido': True,
            'diagnostico_activo': True,
            'extension_afectada': 'x',
        }
        self.ctx.save()
        reiniciar_diagnostico(self.ctx)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))
        self.assertFalse(self.ctx.metadata.get('diagnostico_activo'))
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))

        # Tras reinicio, un síntoma nuevo puede reactivar anamnesis
        self.ctx.problema = ''
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Otra vez manchas negras en las hojas',
        )
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_activo'))
        self.assertIsNotNone(pregunta)

    def test_keywords_cursos_variantes_no_escapan(self):
        for kw in ('listo.', 'Listo✅', 'siguiente', 'continuar curso', 'ok', 'dale'):
            self.ctx.metadata = {'diagnostico_activo': True}
            self.ctx.problema = 'manchas'
            self.ctx.save()
            pregunta = siguiente_pregunta_diagnostico(self.ctx, kw)
            self.ctx.refresh_from_db()
            self.assertFalse(
                self.ctx.metadata.get('diagnostico_omitido'),
                f'{kw!r} no debe omitir',
            )
            self.assertIsNotNone(pregunta, f'{kw!r} debe re-preguntar / seguir')

    def test_sin_foto_tras_pedir_foto_no_marca_omit_global(self):
        self.ctx.metadata = {
            'diagnostico_activo': True,
            'extension_afectada': 'hojas',
            'tiempo_problema': '1 semana',
            'manejo_previo': 'nada',
            'anamnesis_completa': True,
            'pidio_foto': True,
        }
        self.ctx.etapa = 'crecimiento'
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'sin foto')
        self.ctx.refresh_from_db()
        self.assertIsNone(pregunta)
        self.assertTrue(self.ctx.metadata.get('foto_omitida'))
        self.assertFalse(
            self.ctx.metadata.get('diagnostico_omitido'),
            'omitir foto no debe bloquear futuras consultas',
        )
