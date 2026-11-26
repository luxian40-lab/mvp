"""G4: wrapper LLM diferido; flag off no encola."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.conversacion.llm_diferido import (
    MARCA_RESPUESTA_DIFERIDA,
    completar_chat_o_diferir,
    es_respuesta_diferida,
)


class LlmDiferidoFlagOffTests(SimpleTestCase):
    @override_settings(EKI_LLM_RESPUESTA_DIFERIDA=False)
    @patch('core.openai_compat.completar_chat', return_value='hola')
    @patch('core.tasks.ejecutar_llm_turno_whatsapp_async.delay')
    def test_flag_apagado_llama_sync_y_no_encola(self, delay, completar):
        out = completar_chat_o_diferir(
            MagicMock(), 'gpt-5-mini', [{'role': 'user', 'content': 'x'}], 100,
            telefono='573001', agente='coach',
        )
        self.assertEqual(out, 'hola')
        completar.assert_called_once()
        delay.assert_not_called()
        self.assertFalse(es_respuesta_diferida(out))


class LlmDiferidoFlagOnTests(SimpleTestCase):
    @override_settings(EKI_LLM_RESPUESTA_DIFERIDA=True)
    @patch('core.openai_compat.completar_chat', return_value='hola')
    @patch('core.tasks.ejecutar_llm_turno_whatsapp_async.delay')
    def test_flag_prendido_encola_y_devuelve_marca(self, delay, completar):
        out = completar_chat_o_diferir(
            MagicMock(), 'gpt-5-mini', [{'role': 'user', 'content': 'x'}], 100,
            telefono='573001', agente='coach',
            from_number='57300999', post_asesor=True, body='cómo vendo',
            derivado=True, agente_secundario='ventas',
        )
        self.assertEqual(out, MARCA_RESPUESTA_DIFERIDA)
        completar.assert_not_called()
        delay.assert_called_once()
        kwargs = delay.call_args.kwargs
        self.assertTrue(kwargs['post_asesor'])
        self.assertEqual(kwargs['body'], 'cómo vendo')
        self.assertEqual(kwargs['from_number'], '57300999')
        self.assertTrue(kwargs['derivado'])
        self.assertEqual(kwargs['agente_secundario'], 'ventas')
        self.assertTrue(es_respuesta_diferida(out))


class LlmTurnoAsyncPostAsesorTests(SimpleTestCase):
    @override_settings(OPENAI_API_KEY='sk-test')
    @patch('core.lineas.principal.asesores.finalizar_turno_asesor_llm')
    @patch('core.openai_compat.completar_chat', return_value='Respuesta LLM')
    @patch('core.conversacion.locks.telefono_lock')
    def test_tarea_con_post_asesor_usa_finalizar(self, lock, completar, finalizar):
        from contextlib import nullcontext

        lock.return_value = nullcontext()
        finalizar.return_value = True
        from core.tasks import ejecutar_llm_turno_whatsapp_async

        ejecutar_llm_turno_whatsapp_async.run(
            modelo='gpt-5-mini',
            messages=[{'role': 'user', 'content': 'x'}],
            max_out=100,
            telefono='573001110001',
            agente='ventas',
            from_number='573009990001',
            post_asesor=True,
            body='cómo vendo',
            derivado=False,
            agente_secundario='',
        )
        completar.assert_called_once()
        finalizar.assert_called_once()
        kw = finalizar.call_args.kwargs
        self.assertEqual(kw['texto'], 'Respuesta LLM')
        self.assertEqual(kw['body'], 'cómo vendo')
        self.assertEqual(kw['agente'], 'ventas')