"""Tests kill switch LLM eki.ia (Capa 0)."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.bot_comercial.vision import diagnosticar_imagen_cultivo
from core.bot_comercial.webhook import _bot_comercial_respuesta_catalogo
from core.eki_ia_kill_switch import eki_ia_llm_kill_activo, motivo_kill_switch
from core.models import Cliente, EventoIA
from core.nati import buscar_en_web_colombia


class EkiIaKillSwitchTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org Kill',
            contacto_principal='A',
            email='kill@test.co',
            telefono='573001110001',
        )

    def test_env_global_activa_kill(self):
        with override_settings(EKI_IA_LLM_DISABLED=True):
            self.assertTrue(eki_ia_llm_kill_activo())
            self.assertEqual(motivo_kill_switch(), 'llm_disabled_global')

    def test_flag_org_activa_kill(self):
        self.org.desactivar_llm_comercial = True
        self.org.save(update_fields=['desactivar_llm_comercial'])
        with override_settings(EKI_IA_LLM_DISABLED=False):
            self.assertTrue(eki_ia_llm_kill_activo(cliente=self.org))
            self.assertEqual(motivo_kill_switch(cliente=self.org), 'llm_disabled_org')
            self.assertFalse(eki_ia_llm_kill_activo(cliente=None))

    @override_settings(EKI_IA_LLM_DISABLED=True, OPENAI_API_KEY='sk-test')
    @patch('openai.OpenAI')
    def test_respuesta_catalogo_no_llama_openai(self, mock_openai):
        texto = _bot_comercial_respuesta_catalogo(
            'precio fertilizante cafe',
            contexto_rag='Fertilizante Café 50kg — $120.000',
            cliente=self.org,
        )
        mock_openai.assert_not_called()
        self.assertIn('Fertilizante Café', texto)
        self.assertIn('información oficial', texto.lower())
        ev = EventoIA.objects.filter(agente='eki.ia').order_by('-id').first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.regla_aplicada, 'llm_disabled_global')
        self.assertTrue(ev.metadata.get('kill_switch'))
        self.assertFalse(ev.metadata.get('llm_llamado'))

    @override_settings(EKI_IA_LLM_DISABLED=True, OPENAI_API_KEY='sk-test')
    @patch('openai.OpenAI')
    def test_vision_no_llama_openai(self, mock_openai):
        out = diagnosticar_imagen_cultivo(
            'https://api.twilio.com/media/ME1',
            'image/jpeg',
            cliente=self.org,
        )
        mock_openai.assert_not_called()
        self.assertIn('modo seguro', out.lower())

    @override_settings(EKI_IA_LLM_DISABLED=True, OPENAI_API_KEY='sk-test')
    @patch('openai.OpenAI')
    def test_web_search_no_llama_openai(self, mock_openai):
        self.assertEqual(buscar_en_web_colombia('roya cafe'), '')
        mock_openai.assert_not_called()
