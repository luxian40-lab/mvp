"""P1a/P1b: respuestas cortas al reto sin nota; post-reto sin «No entendí»."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.avance_whatsapp import (
    CLAVE_ESPERA_CONTINUAR_POST_RETO,
    TEXTO_NO_ENTENDI,
    texto_cuando_no_es_listo,
)
from core.lineas.agricapital_experiencia import es_mensaje_no_calificable_reto


class RespuestaCortaRetoTests(SimpleTestCase):
    def test_no_si_ok_no_califican(self):
        for frase in ('No', 'Sí', 'si', 'ok', 'vale', 'gracias'):
            self.assertTrue(es_mensaje_no_calificable_reto(frase), frase)

    def test_plan_serio_si_califica(self):
        self.assertFalse(
            es_mensaje_no_calificable_reto(
                'Mañana hago una lista de tareas e identifico lo urgente e importante.'
            )
        )

    def test_no_en_reto_lhaura_no_llama_evaluador(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import reto as reto_mod

        estudiante = SimpleNamespace(
            cliente_id=27,
            contexto_temporal={
                'modulos_reto_ids': [],
                'reto_texto': 'Cuéntanos su plan',
                'progreso_id': None,
            },
            nombre='Carolina',
            id=2278,
            cliente=None,
        )
        contexto = Contexto(
            estudiante=estudiante,
            msg_body='No',
            msg_from='573227530407',
            telefono_limpio='573227530407',
            msg_sid='wamid.x',
            texto_respuesta='',
        )
        with patch('core.tutor_ia_modulo.evaluar_reto_facilitador') as mock_eval:
            resp = reto_mod.manejar(contexto)
        mock_eval.assert_not_called()
        self.assertIn('no cuenta como respuesta', (resp.texto or '').lower())
        self.assertIn('cuando pueda', (resp.texto or '').lower())
        self.assertNotIn('/10', resp.texto or '')


class PostRetoSinNoEntendiTests(SimpleTestCase):
    def test_post_reto_pide_continuar_sin_no_entendi(self):
        est = SimpleNamespace(
            cliente_id=27,
            contexto_temporal={
                CLAVE_ESPERA_CONTINUAR_POST_RETO: True,
                'post_reto_entregar_modulo_id': 99,
            },
        )
        out = texto_cuando_no_es_listo(est)
        self.assertIn('Ya revisamos su reto', out)
        self.assertNotIn('No entendí', out)

    def test_sin_post_reto_sigue_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={})
        out = texto_cuando_no_es_listo(est)
        self.assertEqual(out, TEXTO_NO_ENTENDI)
