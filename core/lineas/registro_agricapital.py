"""Bienvenida del enlace de Agricapital en la línea 3.

Solo el cliente 26. El enlace manda la bienvenida con un botón. El
mensaje siguiente manda las dudas y abre el registro. Las explicaciones
y las preguntas de esa copia son el Formador y el Compañero: todavía
no salen con *listo*.
"""
from __future__ import annotations

from core.lineas.registro_enlace import leer_frase

AGRICAPITAL_ID = 26
BOTON_CONTINUAR = 'registro_continuar'
TITULO_CONTINUAR = 'Cómo continuar'

BIENVENIDA = (
    'Bienvenida\n'
    '¡Hola! 👋 Bienvenido a tu curso de Agricapital con eki. '
    'Aprenderás directamente por WhatsApp, desde tu celular y a tu ritmo.\n'
    'Paso 2. Resolvamos tus dudas\n'
    '¿Tienes alguna pregunta antes de empezar? Podemos explicarte cómo funciona '
    'el curso, qué necesitas y cómo participar.\n'
    'Paso 3. Inscripción\n'
    '¿Estás listo para comenzar? Te haremos unas preguntas sencillas para '
    'registrarte aquí mismo.'
)
DUDAS_PRIMERO = (
    '¿Dónde voy a ver el curso?\n'
    'Todo el curso lo recibirás directamente en este chat de WhatsApp. '
    'No necesitas entrar a ninguna otra página.\n'
    '¿Tengo que descargar alguna aplicación?\n'
    'No. Solo necesitas tener WhatsApp en tu celular.\n'
    '¿Tengo que estudiar a una hora específica?\n'
    'No. Puedes revisar los contenidos cuando tengas tiempo, desde tu celular.\n'
    '¿Qué necesito para empezar el curso?\n'
    'Solo tu celular con WhatsApp, conexión a internet y ganas de aprender.'
)
DUDAS_DESPUES = (
    '¿Cómo hago para inscribirme?\n'
    'Muy fácil. Aquí mismo, por WhatsApp, te pediremos unos datos básicos. '
    'No necesitas llenar formularios en otras páginas.\n'
    '¿Qué pasa si no tengo señal o me quedo sin internet?\n'
    'No te preocupes. Cuando vuelvas a tener conexión, podrás revisar los '
    'mensajes que hayas recibido.\n'
    '¿Cómo hago las actividades del curso?\n'
    'Te enviaremos explicaciones y preguntas por este mismo chat. Solo tendrás '
    'que seguir las instrucciones y responder.\n'
    '¿Qué hago si no entiendo algo o necesito ayuda?\n'
    'Puedes escribir tu pregunta por este chat. eki cuenta con herramientas de '
    'apoyo para resolver tus dudas.'
)


def es_enlace_agricapital(cliente_id: int | None, body: str) -> bool:
    """True solo en el mensaje que trae la frase EKI C26."""
    if cliente_id != AGRICAPITAL_ID:
        return False
    destino = leer_frase(body)
    return bool(destino and destino[0] == 'cliente' and destino[1] == AGRICAPITAL_ID)


def enviar_bienvenida(telefono: str) -> None:
    from core.lineas.envio import enviar_meta_botones

    enviar_meta_botones(
        telefono,
        BIENVENIDA,
        [(BOTON_CONTINUAR, TITULO_CONTINUAR)],
        agente_evento='registro_flow',
    )
