"""Experto en café: sexto agente, solo café, fuentes en orden."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.cafe_fuentes import consulta_cafe, enriquecer_contexto_cafe
from core.nati import buscar_en_web_colombia
from core.sandbox_agentes import _respuesta_si_falla, presentacion_agente, prompt_para
from core.sandbox_menu import TEXTO_AGENTES, clasificar_asesoria, resolver_ruta_sandbox


class CafeFuentesTests(SimpleTestCase):
    def test_consulta_lleva_cafe_colombia(self):
        self.assertEqual(consulta_cafe('broca'), 'café Colombia broca')
        self.assertEqual(consulta_cafe('roya en el café'), 'roya en el café')

    @patch('core.fao_connector.buscar_fao')
    @patch('core.nati.buscar_en_web_colombia')
    @patch('core.agrosavia_connector.enriquecer_contexto_con_agrosavia')
    def test_agrosavia_corta_el_resto(self, agro, web, fao):
        agro.return_value = (
            'FUENTE INSTITUCIONAL AGROSAVIA\nbroca',
            {'agrosavia_usada': True},
        )
        ctx, meta = enriquecer_contexto_cafe('broca')
        self.assertEqual(meta['fuente'], 'agrosavia')
        self.assertIn('AGROSAVIA', ctx)
        web.assert_not_called()
        fao.assert_not_called()
        self.assertIn('café', agro.call_args[0][0].lower())

    @patch('core.fao_connector.buscar_fao')
    @patch('core.nati.buscar_en_web_colombia', return_value='Según Cenicafé, recoja frutos brocados.')
    @patch('core.agrosavia_connector.enriquecer_contexto_con_agrosavia', return_value=('', {'agrosavia_usada': False}))
    def test_web_si_agrosavia_no_responde(self, _agro, web, fao):
        ctx, meta = enriquecer_contexto_cafe('broca')
        self.assertEqual(meta['fuente'], 'web')
        self.assertIn('FUENTES WEB CAFÉ COLOMBIA', ctx)
        self.assertIn('Cenicafé', ctx)
        fao.assert_not_called()
        web.assert_called_once_with('café Colombia broca', ambito='cafe')

    @patch('core.fao_connector.formatear_contexto_fao', return_value='FUENTE INSTITUCIONAL FAO\ncoffee')
    @patch('core.fao_connector.buscar_fao', return_value=[{'titulo': 'Coffee'}])
    @patch('core.nati.buscar_en_web_colombia', return_value='')
    @patch('core.agrosavia_connector.enriquecer_contexto_con_agrosavia', return_value=('', {'agrosavia_usada': False}))
    def test_fao_solo_si_agrosavia_y_web_vacias(self, _agro, _web, fao, _fmt):
        ctx, meta = enriquecer_contexto_cafe('broca')
        self.assertEqual(meta['fuente'], 'fao')
        self.assertIn('FAO', ctx)
        fao.assert_called_once()

    @patch('core.fao_connector.formatear_contexto_fao', return_value='')
    @patch('core.fao_connector.buscar_fao', return_value=[])
    @patch('core.nati.buscar_en_web_colombia', return_value='')
    @patch('core.agrosavia_connector.enriquecer_contexto_con_agrosavia', return_value=('', {'agrosavia_usada': False}))
    def test_sin_fuente_no_arma_bloque(self, _agro, _web, _fao, _fmt):
        ctx, meta = enriquecer_contexto_cafe('broca', 'conocimiento previo')
        self.assertEqual(meta['fuente'], '')
        self.assertEqual(ctx, 'conocimiento previo')


class CafePromptTests(SimpleTestCase):
    def test_prompt_de_usted_y_sin_inventar(self):
        prompt = prompt_para('cafe')
        self.assertIn('Trate SIEMPRE de "usted"', prompt)
        self.assertIn('Agrónomo', prompt)
        self.assertIn('café', prompt)
        self.assertIn('No invente dosis', prompt)
        self.assertIn('AGROSAVIA', prompt)
        self.assertIn('Cenicafé', prompt)
        saludo = presentacion_agente('cafe')
        self.assertIn('*Agrónomo*', saludo)
        self.assertIn('cafetal', saludo.lower())
        self.assertIn('cartilla', _respuesta_si_falla('cafe', 'broca'))

    def test_el_cafe_entra_por_el_agronomo(self):
        self.assertEqual(clasificar_asesoria('tengo broca en el cafetal'), 'nat')
        self.assertEqual(clasificar_asesoria('plaga en el platano'), 'nat')
        self.assertEqual(clasificar_asesoria('precio del café'), 'ventas')


@override_settings(
    OPENAI_API_KEY='sk-test',
    BOT_COMERCIAL_WEB_FALLBACK_ENABLED=True,
)
class CafeWebAmbitoTests(SimpleTestCase):
    @patch('core.eki_ia_kill_switch.eki_ia_llm_kill_activo', return_value=False)
    def test_ambito_cafe_no_pide_cenicana(self, _kill):
        falso = MagicMock()
        falso.responses.create.return_value = MagicMock(output_text='broca')
        with patch('openai.OpenAI', return_value=falso):
            buscar_en_web_colombia('broca', ambito='cafe')
        texto = falso.responses.create.call_args.kwargs['input']
        self.assertIn('Cenicafé', texto)
        self.assertIn('Federación Nacional de Cafeteros', texto)
        self.assertIn('ni de Cenicana', texto)
        self.assertNotIn('Cenicafe Cenicana', texto)

    @patch('core.eki_ia_kill_switch.eki_ia_llm_kill_activo', return_value=False)
    def test_ambito_general_sigue_igual(self, _kill):
        falso = MagicMock()
        falso.responses.create.return_value = MagicMock(output_text='suelo')
        with patch('openai.OpenAI', return_value=falso):
            buscar_en_web_colombia('suelo')
        texto = falso.responses.create.call_args.kwargs['input']
        self.assertIn('Cenicana', texto)


@override_settings(
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
)
class CafeMenuTests(TestCase):
    def test_seis_entra_al_agronomo(self):
        base = {
            'From': 'whatsapp:+573009990061',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        decision = resolver_ruta_sandbox({**base, 'Body': '6'})
        self.assertEqual(decision.action, 'nat')
        self.assertTrue(decision.saludo_entrada)
        self.assertIn('Experto en café', TEXTO_AGENTES)
        self.assertNotIn('*6*', TEXTO_AGENTES)
