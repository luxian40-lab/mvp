# 04 — Preguntas abiertas

Lo que el código no permite cerrar. Hace falta respuesta de quien opera producción.

1. En el entorno Elastic Beanstalk, ¿`WEBHOOK_CELERY_ASYNC`, `NAT_WEBHOOK_CELERY_ASYNC` y `SANDBOX_CELERY_ASYNC` están en el default de `settings_production.py` (activos) o alguien los apagó? El archivo de settings no dice el valor desplegado.

2. ¿`TWILIO_STATUS_CALLBACK_URL` está definido y apunta al mismo webhook? Sin eso, `messages.create` no pide callback (`core/utils.py:310`). ¿`TWILIO_STATUS_CALLBACK` (otro nombre, `core/whatsapp_service.py:386`) está definido o es una variable muerta?

3. ¿`TWILIO_VALIDATE_SIGNATURE` y `WHATSAPP_REQUIRE_SIGNATURE` / `WHATSAPP_APP_SECRET` están puestos en producción? El default de desarrollo deja la firma Meta en modo permisivo si el secreto va vacío (`core/webhook_evento.py:112-114`).

4. ¿Cuál es el número From real de cursos, el de Nat y el phone number id de Meta? En código hay un fallback fijo (redactado en `02a`) además de `TWILIO_PHONE_NUMBER`. No se puede saber cuál gana en runtime sin el env.

5. ¿Los campos `Cliente.twilio_account_sid`, `twilio_auth_token`, `twilio_whatsapp_from` y `whatsapp_numero` tienen filas cargadas? El transporte no los lee. Si el negocio ya los usa a mano, el código no lo refleja.

6. ¿`Campana.linea_origen` se completa en el admin con intención de elegir línea? El envío la ignora.

7. ¿`TWILIO_TEMPLATE_DRIP_REENGANCHE` está cargado? Si no, el reenganche de las 08:00 manda texto de sesión (`core/tasks.py:69-75`) y fuera de 24 h WhatsApp lo rechaza.

8. ¿Beat está corriendo (`scripts/run_beat.sh` / proceso EB)? Sin Beat no hay reenganche ni campañas programadas ni poll de plantillas Meta. El repo no demuestra que el proceso esté vivo.

9. ¿Alguien llama `enviar_notificacion_async` o `ejecutar_seguimiento_proactivo` desde un cron externo al repo? Dentro del repo, la primera importa una función que no existe (`core/tasks.py:376`) y la segunda no está en `mvp_project/celery.py`.

10. ¿El megáfono del admin se usa? La consulta de ventana usa campos `tipo_mensaje` y `timestamp` que `WhatsappLog` no tiene (`core/admin/estudiantes.py:626-629`). Si esa pantalla se abre, debería fallar. No hay traza de runtime en el repo.

11. ¿Los `statuses` de Cloud API (delivered/read/failed) llegan al webhook y se espera guardarlos? El código los deja pasar el filtro de idempotencia (`core/webhook_evento.py:146`) y `_procesar_meta_webhook` no los aplica a un log (`core/views/webhook_meta.py:103`).

12. ¿La ventana de 24 h se considera responsabilidad de Twilio (error 63016) o se esperaba un chequeo propio antes de enviar? No hay chequeo previo en el transporte.

13. ¿`SANDBOX_PROVEEDOR` en producción es `meta` (default, `settings.py:539`) o `twilio`? Cambia si el menú demo sale por Graph o por Twilio y si el número sandbox entra al set de Nat (`core/bot_comercial_routing.py:36-40`).

14. ¿Cuántos phone number id hay hoy en el WABA y cuál es el de “solo IA”, “solo cursos” y “mixto”? El código solo distingue comercial vs educativo vs sandbox.

15. ¿Las campañas Twilio se lanzan solo por Celery o a veces caen al hilo daemon (`core/services.py:170-176`)? Si Celery no está, un recycle de Gunicorn corta el lote y Beat puede reenviarlo porque no hay dedupe por destinatario.

16. ¿El `MessageSid` de los status callbacks es el mismo SID guardado en `WhatsappLog.mensaje_id`? El callback busca `tipo='SENT'` (`core/views/twilio_transporte.py:108-111`). Los envíos que no escriben ese log (plantilla de `enviar_plantillas.py`, portal) no se actualizan. Hace falta confirmar si operaciones mira ese admin.

17. ¿Se purgan `WebhookEventoProcesado` a los 10 días en un entorno donde Twilio reintenta más tarde? `purgar_eventos_procesados` (`core/webhook_evento.py:83`) lo hace desde `limpiar_logs_antiguos`. Un reintento posterior a la purga volvería a procesar el mensaje.
