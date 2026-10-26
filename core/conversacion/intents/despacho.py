"""Qué módulo responde cada intent de get_response_for_intent.

get_response_for_intent busca aquí después del preámbulo B2B. Cada handler
recibe (intent, nombre_usuario, kwargs) y siempre devuelve el texto.
"""
from core.conversacion.intents import cambiar_nombre, confirmar_cambio_nombre, saludo

INTENTS = {
    'cambiar_nombre': cambiar_nombre.responder,
    'confirmar_cambio_nombre': confirmar_cambio_nombre.responder,
    'saludo': saludo.responder,
}
