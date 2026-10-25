"""Un handler por estado del motor de curso: `manejar(ctx) -> Respuesta`.

El código de cada estado viene del cuerpo de `_procesar_twilio_webhook_cuerpo`
sin cambios de comportamiento. Usa el logger del webhook para que los logs no
cambien de canal.
"""
