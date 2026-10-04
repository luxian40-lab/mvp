"""El ledger guarda el costo del modelo y no el teléfono."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from core.models_uso_llm import UsoLLM
from core.openai_compat import completar_chat, contexto_uso_llm


def _cliente():
    resp = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            completion_tokens_details=None,
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content='hola'))],
    )

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return resp

    return Client()


class UsoLlmTests(TestCase):
    def test_gpt5_mini_cuesta_entrada_mas_salida(self):
        contexto_uso_llm(telefono='573001112233', agente='nat')
        texto = completar_chat(_cliente(), 'gpt-5-mini', [], 100)
        self.assertEqual(texto, 'hola')
        fila = UsoLLM.objects.get()
        self.assertEqual(fila.costo_usd_est, Decimal('2.250000'))
        self.assertFalse(fila.estimado)
        self.assertEqual(fila.agente, 'nat')
        self.assertNotIn('573001112233', fila.telefono_hash)
        self.assertTrue(fila.telefono_hash)
