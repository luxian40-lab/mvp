"""preToolUse: pide confirmación antes de editar el motor de curso.

El cuerpo de `_procesar_twilio_webhook_cuerpo` solo se envuelve desde afuera
hasta que la fase D del plan de modularidad autorice extraer un estado.
La autorización vive en `.cursor/refactor_motor.json` (`cuerpo_autorizado`).
"""
from __future__ import annotations

import json

from _comun import RAIZ, leer_entrada, responder, ruta_editada

PROTEGIDOS = {
    'core/views/webhook_twilio.py': 'el cuerpo de _procesar_twilio_webhook_cuerpo (motor de curso de las dos líneas)',
    'core/response_templates.py': 'los marcadores [SEP]/[DELAY]/[MEDIA] que parsea el transporte',
}
AUTORIZACION = RAIZ / '.cursor' / 'refactor_motor.json'


def autorizado() -> bool:
    try:
        return bool(json.loads(AUTORIZACION.read_text(encoding='utf-8')).get('cuerpo_autorizado'))
    except (OSError, ValueError):
        return False


def main() -> None:
    rel = ruta_editada(leer_entrada())
    if rel not in PROTEGIDOS or autorizado():
        responder({})
        return
    motivo = PROTEGIDOS[rel]
    responder({
        'permission': 'ask',
        'user_message': (
            f'Edición en {rel}: toca {motivo}. '
            'Regla eki: el cuerpo solo se envuelve desde afuera. ¿Confirmas este cambio?'
        ),
        'agent_message': (
            f'{rel} está protegido por la fase D de docs/PLAN_MODULARIDAD_EKI.md. '
            'Antes de editarlo: test de caracterización del estado, un commit solo de movimiento '
            'y .cursor/refactor_motor.json con cuerpo_autorizado=true y el estado en estados_autorizados. '
            'Si el cambio puede hacerse envolviendo desde afuera, hazlo así.'
        ),
    })


if __name__ == '__main__':
    main()
