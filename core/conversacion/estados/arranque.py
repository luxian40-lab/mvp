"""Estado de chat al empezar: migra el estado vacío del sistema viejo y autocorrige el habeas que el admin dejó pendiente. Devuelve el estado. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.conversacion.contexto import Contexto

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> str:
    estudiante = contexto.estudiante
    estado_chat = getattr(estudiante, 'estado_chat', None)
    logger.info(f"📍 Estado estudiante {estudiante.nombre}: estado_chat={estado_chat}, onboarding={estudiante.estado_onboarding}, acepto={estudiante.acepto_terminos}")
    
    # Migrar estudiantes legacy al nuevo sistema
    if not estado_chat or estado_chat in ('', None):
        if estudiante.acepto_terminos and estudiante.estado_onboarding == 'completado':
            estudiante.estado_chat = 'ACTIVO'
        elif estudiante.acepto_terminos:
            estudiante.estado_chat = 'ESPERANDO_CEDULA'
        else:
            estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
        estudiante.save()
        estado_chat = estudiante.estado_chat
        logger.info(f"📍 Legacy migration: estado_chat → {estado_chat}")
    
    # Auto-corregir: admin creó estudiante con acepto_terminos=True pero estado_chat quedó en ESPERANDO_HABEAS_DATA
    if estado_chat == 'ESPERANDO_HABEAS_DATA' and estudiante.acepto_terminos:
        if estudiante.estado_onboarding == 'completado':
            estudiante.estado_chat = 'ACTIVO'
        else:
            estudiante.estado_chat = 'ESPERANDO_CEDULA'
        estudiante.save()
        estado_chat = estudiante.estado_chat
        logger.info(f"📍 Auto-corrección admin: estado_chat → {estado_chat}")
    return estado_chat
