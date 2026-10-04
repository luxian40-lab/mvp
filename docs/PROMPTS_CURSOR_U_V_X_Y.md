# Prompts para Cursor: W3, U, V, X, Y

Lee este archivo y ejecuta en este orden: W3, U, V, X, Y. Un commit por letra, informe tras cada una, push al final.

## Reglas para todo este archivo

- No despliegues. Rama `slice/escalabilidad-base`.
- No imprimas tokens, secretos ni teléfonos completos en logs, tests ni informes.
- No modifiques el cuerpo de `_procesar_twilio_webhook_cuerpo`.
- Todo umbral o código de Meta va a settings y se documenta con la fecha en que lo verificaste contra la documentación oficial de WhatsApp Cloud API. Si no puedes verificar un dato, dilo en el informe en vez de asumirlo.
- Migraciones: expand/contract. Índices en tablas grandes con `AddIndexConcurrently` y `atomic = False` en migración separada.
- Cada informe incluye: commits, archivos tocados, archivos nuevos y su estado en git, migraciones, resultado de `check`, `makemigrations --check` y tests, y riesgos.

---

## W3) test(ventana): el canal se marca también en el flujo Meta real

Contexto: la línea Meta reutiliza el código de lecciones mediante `canal_sandbox_meta()` y `inbound_desde_meta_message`, que emula un POST de Twilio. Hay que asegurar que el log del mensaje entrante de Meta quede con `canal='meta'` aunque lo cree código del camino educativo.

1. Test de extremo a extremo con un payload real de Meta (firmado, con un mensaje de texto): después de procesarlo, el `WhatsappLog` entrante tiene `canal='meta'` y `ventana_abierta(estudiante)` es verdadera.
2. Test inverso: un POST de Twilio crea `canal='twilio'` y NO abre la ventana de Meta.
3. Si algún camino crea el log sin canal, corrígelo sin tocar el cuerpo de `_procesar_twilio_webhook_cuerpo` (por ejemplo, marcando el canal en el punto de entrada mediante un contexto o contextvar). Dime qué caminos encontraste.
4. Los logs salientes también deben llevar `canal`. Revisa `enviar_meta` y los envíos por Twilio.

---

## U) fix(meta): errores de Graph, token y versión

1. Migración expand en `WhatsappLog`: `error_codigo` (CharField 16, null) y `error_detalle` (TextField, blank). Antes, verifica si ya existe un campo equivalente (el informe S decía que `error_detalle` no se escribía: si ya existe, solo úsalo).
2. `_post_graph` en `core/sandbox_canal.py` rellena ambos campos con `code`, `type` y `message` (message truncado a 500).
3. Error OAuth 190, o `OAuthException` por token inválido o caducado:
   - `logger.critical("meta_token_invalido")` sin imprimir el token.
   - Pon en Redis la clave `eki:meta:token_invalido` con TTL de 15 min.
   - Las tareas de campaña y de reenganche consultan esa clave y no envían mientras exista (cuentan los omitidos).
   - Muestra la alerta en `/admin/infra/` y en las alertas del Inicio del admin.
4. Versión de Graph: unifica en un solo setting, `WHATSAPP_API_VERSION`, usado por `core/meta_waba.py` (`_version()`), `core/sandbox_canal.py`, `core/audio_processor.py` (hoy fija `v19.0`) y `core/meta_templates.py`. NO cambies el valor por defecto. En el informe dime: (a) qué versiones estables lista hoy la documentación oficial de Graph API y hasta cuándo se da soporte a `v19.0`; (b) cuál recomiendas. El cambio de valor lo pruebo yo aparte.
5. Tests: error 190 activa la bandera y el reenganche no envía; error distinto no la activa; los campos de error se guardan; el token nunca aparece en los logs capturados.

---

## V) feat(meta): procesar los `statuses` del webhook

1. Módulo `core/meta_estados.py`. Por cada status (`id`, `status`, `timestamp`, `errors[].code`, `errors[].title`, `biz_opaque_callback_data`) actualiza el `WhatsappLog` saliente cuyo `mensaje_id` coincida.
2. Estados monótonos: `sent` < `delivered` < `read`. `failed` puede sobrescribir `sent`. Un evento fuera de orden o repetido no retrocede el estado. Un status de un mensaje desconocido se ignora con log de nivel debug.
3. Procesamiento ligero y fuera del camino crítico: el webhook responde 200 de inmediato y encola una tarea corta en la cola `conversacion`. No debe bloquear ni retrasar el procesamiento de mensajes entrantes. No deduplicar los statuses (llegan varios por mensaje, como ya quedó en P1).
4. Verifica el índice sobre `WhatsappLog.mensaje_id`. Si falta, créalo con `AddIndexConcurrently` en migración separada (`atomic = False`) y muestra antes el `EXPLAIN` de la consulta.
5. Tabla de acciones por código de error de Meta, en settings, con fecha de verificación contra la documentación oficial. Punto de partida (verifícalo y corrígelo):
   - `130429`, `131056`: límite de velocidad o por par de usuarios → contar y marcar reintentable con backoff.
   - `131047`: fuera de la ventana de 24 h → marcar "ventana cerrada".
   - `131026`, `131048`, `131049`: no entregable / limitación por spam o ecosistema → no reintentar, contar.
   - `131052`, `131053`: media (descarga o subida) → marcar media fallida.
   - `190`: token → activar la bandera de U.
6. Alertas: en el panel de Inicio y en los playbooks, reemplaza los códigos 63019/63021 por un contador de fallos de Meta por código en las últimas 24 h, para la línea Meta. Mantén los de Twilio solo para su canal.
7. Tests: orden de estados, evento duplicado, status sin mensaje conocido, firma inválida (no procesa), `failed` con código guardado, y que el webhook con solo `statuses` responde 200 sin ejecutar lógica de curso.

---

## X) INSPECCIÓN, sin cambios de código

Lee `core/meta_waba.py` (`CampanaMeta`, `ejecutar_campana_meta`) y responde, pegando las líneas relevantes:

1. Qué hace de punta a punta: plantillas, variables, destinatarios, estados que guarda, reintentos, idempotencia, límite de velocidad.
2. Qué cobertura de tests tiene.
3. Qué le falta para ser la base de `MetaSender`: claim atómico por destinatario, estado `INCIERTO` ante timeout, token bucket global, uso de `biz_opaque_callback_data`.
4. Por qué `enviar_campanas_programadas` no la usa.
5. En `core/admin`: cómo elige hoy el operador entre Twilio y Meta al crear una campaña. ¿Hay forma de lanzar una `CampanaMeta` desde el admin?
6. Si hoy se podría enviar una campaña de ~150 destinatarios por Meta con este código sin cambios, y qué riesgos concretos tendría.

---

## Y) Mantenimiento menor

a) `countdown` máximo de 540 s en los tres sitios que hoy llegan a 900: `core/tasks.py` (indexación del ZIP RAG), `core/admin/commercial.py` (subida masiva) y `core/biblioteca_nat_service.py` (`_stagger_segundos`). Con `visibility_timeout=600` un `countdown` mayor provoca reentregas.

b) Cola `course_engine`: `generar_video_course_engine_async` la declara y ningún worker la consume. Averigua si Course Engine corre en producción. Si NO corre en prod, añade una excepción explícita y comentada en el test de colas. Si SÍ corre, añade la cola al default de `run_worker.sh` y a `task_routes`.

c) Límites duros en el admin para media de WhatsApp: audio 16 MB e imagen 5 MB (el video ya tiene 16 MB). Verifica los límites vigentes en la documentación de Meta y ponlos en settings con fecha. Los avisos de 3G se mantienen.

d) Actualiza el diseño P4 en `docs/PLAN_ESCALABILIDAD_EKI.md` para que `MetaSender` parta de lo que reporte X (reutilizar `CampanaMeta` en vez de reescribir).
