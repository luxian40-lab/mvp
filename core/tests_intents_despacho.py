"""Intents movidos de get_response_for_intent: cada uno en su módulo y sin copia en la función."""
import ast
import inspect
from pathlib import Path

from django.test import SimpleTestCase

from core.conversacion.intents.despacho import INTENTS

RT = Path(__file__).resolve().parent / 'response_templates.py'


def _intents_que_quedan() -> set[str]:
    arbol = ast.parse(RT.read_text(encoding='utf-8'))
    func = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == 'get_response_for_intent')
    quedan = set()
    for nodo in ast.walk(func):
        if isinstance(nodo, ast.Compare) and isinstance(nodo.left, ast.Name) and nodo.left.id == 'intent':
            quedan |= {c.value for c in nodo.comparators if isinstance(c, ast.Constant)}
    return quedan


class DespachoIntentsTests(SimpleTestCase):
    def test_lo_despachado_no_tiene_bloque_en_la_funcion(self):
        self.assertFalse(set(INTENTS) & _intents_que_quedan())

    def test_cada_handler_es_su_modulo(self):
        for intent, responder in INTENTS.items():
            self.assertEqual(responder.__module__, f'core.conversacion.intents.{intent}')
            self.assertEqual(list(inspect.signature(responder).parameters), ['intent', 'nombre_usuario', 'kwargs'])

    def test_despacha_con_los_mismos_argumentos(self):
        from core.response_templates import get_response_for_intent

        self.assertIn('cambiar_nombre', set(INTENTS) | _intents_que_quedan())
        texto = get_response_for_intent('saludo', 'Ana')
        self.assertIn('Hola Ana', texto)
