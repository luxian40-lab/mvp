"""Qué módulo responde cada intent de get_response_for_intent.

get_response_for_intent busca aquí después del preámbulo B2B. Cada handler
recibe (intent, nombre_usuario, kwargs) y siempre devuelve el texto.
"""
from core.conversacion.intents import saludo

INTENTS = {
    'saludo': saludo.responder,
}
