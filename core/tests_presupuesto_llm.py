"""70 % baja a mini. Presupuesto 0 degrada y *listo* sigue."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings

from core.intent_detector import detect_intent
from core.presupuesto_llm import dia_bogota, modelo_segun_presupuesto
from core.sandbox_agentes import responder_agente_sandbox


class _Redis:
    def __init__(self, datos=None, caido=False):
        self.datos = dict(datos or {})
        self.caido = caido

    def get(self, clave):
        if self.caido:
            raise ConnectionError('redis')
        return self.datos.get(clave)

    def incrbyfloat(self, clave, monto):
        self.datos[clave] = float(self.datos.get(clave) or 0) + float(monto)
        return self.datos[clave]

    def expire(self, clave, segundos):
        return True


class PresupuestoLlmTests(TestCase):
    def test_el_dia_cambia_en_bogota(self):
        zona = ZoneInfo('America/Bogota')
        antes = datetime(2026, 10, 4, 23, 30, tzinfo=zona)
        despues = datetime(2026, 10, 5, 0, 10, tzinfo=zona)
        self.assertEqual(dia_bogota(antes), '20261004')
        self.assertEqual(dia_bogota(despues), '20261005')

    @override_settings(
        LLM_PRESUPUESTO_DIARIO_USD=Decimal('10'),
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
    )
    def test_setenta_por_ciento_baja_a_mini(self):
        clave = f'eki:llm:gasto:{dia_bogota()}'
        falso = _Redis({clave: b'7'})
        with patch('core.presupuesto_llm._cliente', return_value=falso):
            self.assertEqual(modelo_segun_presupuesto('gpt-5'), 'gpt-5-mini')

    @override_settings(LLM_PRESUPUESTO_DIARIO_USD=Decimal('0'), OPENAI_API_KEY='sk-test')
    def test_presupuesto_cero_degrada_y_listo_sigue(self):
        falso = _Redis()
        with patch('core.presupuesto_llm._cliente', return_value=falso):
            with patch('openai.OpenAI') as openai:
                texto = responder_agente_sandbox('coach', 'estoy estancado como lider')
            openai.assert_not_called()
        self.assertIn('estanc', texto.lower())
        self.assertEqual(detect_intent('listo'), 'continuar_leccion')

    def test_redis_caido_no_cambia_el_modelo(self):
        with patch('core.presupuesto_llm._cliente', side_effect=ConnectionError('redis')):
            self.assertEqual(modelo_segun_presupuesto('gpt-5'), 'gpt-5')
