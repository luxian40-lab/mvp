# 03 — Hallazgos (hechos, sin arreglos)

Evidencia por archivo:línea. Los volcados literales están en `02a*` … `02g*`.

## 1. Duplicación Twilio / Meta

⚠️ parcial. No hay una interfaz común de proveedor.

- Tres clientes Twilio de sesión/plantilla con la misma idea: `core/utils.py:82`, `core/whatsapp_service.py:35`, `core/enviar_plantillas.py:11`.
- Texto Meta de sesión: `core/utils.py:387` (`enviar_whatsapp`).
- Graph del sandbox: `core/sandbox_canal.py:222` (`_post_graph`) y `enviar_meta` en `:419`.
- Campaña Meta (template): `core/meta_waba.py:589`.
- El puente es un `if sandbox_meta_activo()` dentro de las funciones Twilio (`core/utils.py:207-217`, `core/whatsapp_service.py:47-51`, `core/views/twilio_transporte.py:218-225`) más un monkeypatch de `twilio.rest.Client` (`core/sandbox_canal.py:84-99`).
- `enviar_plantilla_twilio` (`core/enviar_plantillas.py:11`) no entra a ese puente.
- El webhook Meta legado (`core/views/webhook_meta.py:158`) llama `enviar_whatsapp`, no el sandbox.

## 2. Idempotencia

⚠️ parcial.

- Inbound Twilio: `reclamar_twilio` inserta `(canal, MessageSid)` único (`core/webhook_evento.py:177-186`). Si ya existe, el HTTP responde OK y no procesa (`core/views/entrada.py:236-241` y `:264-269`).
- Segunda barrera: `WhatsappLog` INCOMING del mismo SID (`core/views/webhook_twilio.py:79-82`). El log se crea en la línea 143, antes de la mayor parte de los `messages.create`. Si el worker muere después de esa fila y Celery reentrega, el cuerpo retorna y no completa envíos a medias.
- Status callbacks no se reclaman (`core/webhook_evento.py:178-180`). Reprocesarlos actualiza el mismo log (`twilio_transporte.py:108-127`).
- Meta mensajes: `preparar_payload_meta` (`webhook_evento.py:121`). Sandbox además usa cache `sandbox_in:{sid}` 6 h (`webhook_meta.py:13-27`). Si la cache falla, el `except` devuelve False y no deduplica (`:23-24`).
- *listo* duplicado en el mismo proceso: `select_for_update` sobre `Estudiante` (`core/response_templates.py:1266-1268`). No hay `select_for_update` de `ProgresoEstudiante` en `webhook_twilio.py` (grep `select_for_update` en ese archivo: NO ENCONTRADO).
- Campaña Twilio: `EnvioLog` no es único. `ejecutar_campana_servicio` no salta destinatarios ya enviados (`core/services.py:72-128`). `ejecutada=True` se pone al final (`:134`). Dos workers antes de ese save envían dos veces.
- Campaña Meta: salta si ya hay fila ENVIADO (`core/meta_waba.py:572-575`). El `exists` no está en una transacción con el `create` de después (`:593`). Dos workers paralelos pueden pasar el `exists` a la vez.
- Reenganche drip: no guarda “ya notifiqué hoy” (`core/tasks.py:61-75`). Otro run el mismo día vuelve a enviar.
- Push: cada llamada crea otro `EnvioMensajePush` (`mensajes_push.py:57`). Sin dedupe.

## 3. Reintentos, timeouts, 429, plantilla rechazada

⚠️ parcial.

- Twilio SDK: los `messages.create` revisados no pasan timeout propio. El timeout es el del cliente Twilio por defecto. **NO ENCONTRADO** un `timeout=` en `messages.create`.
- Graph sesión sandbox: `timeout=15` (`sandbox_canal.py:252`). Reacción: `timeout=5` (`:296`). `enviar_whatsapp`: `timeout=10` (`utils.py:428`). Campaña Meta `_post`: `timeout=30` (`meta_waba.py:157`).
- 429/5xx Graph: `_post_graph` guarda ERROR y devuelve el cuerpo (`sandbox_canal.py:266-270`). No reintenta. Campaña Meta sí reconoce códigos 4, 80008, 613, 130429 (`meta_waba.py:31` y `:95-99`) y corta el lote (`:610-612`) dejando `ejecutada=False` para poder seguir (`:626-627`).
- Twilio 63019/63021: reintento sin media en `utils.py:330-341` y `twilio_transporte.py:291-302`. El callback puede llamar `reintentar_media_desde_log` (`twilio_transporte.py:128-129`).
- Plantilla con variables inválidas: un segundo `messages.create` sin variables (`utils.py:155-161`, `whatsapp_service.py:85-91`).
- Plantilla Meta rechazada: `ejecutar_campana_meta` exige `estado == 'APPROVED'` (`meta_waba.py:556-560`). Beat consulta PENDING/IN_APPEAL (`tasks.py:908`, `celery.py:34-36`). No hay fallback automático de un envío de sesión fallido hacia una plantilla.
- Diploma: hasta N reintentos con `sleep(2 * intento)` si el texto del error contiene 63016, window, rate o media (`certificado_service.py:675-687`). Reintentar un 63016 con el mismo mensaje de sesión no abre la ventana.
- Celery webhook: `max_retries=8`, soft 45 s, hard 60 s, `acks_late`, `reject_on_worker_lost` (`tasks.py:237-244`). `LockError` reintenta con backoff (`:220-221`). A la 3.ª entrega se corta y se guarda `WebhookFallido` (`:186-203`).

## 4. Ventana de 24 h de Meta / WhatsApp

⚠️ parcial. `core/views/ventana_drip.py` no es esa ventana: evalúa fechas de features del cliente (`:7-22`).

- No hay una función que, antes de un texto de sesión, consulte si el usuario escribió en las últimas 24 h y cambie a template. Grep `24h|63016` en el transporte: el código 63016 está documentado como “fuera de ventana” en `core/twilio_media.py:19` y `core/copiloto_ops.py:55`, no como un branch de envío.
- Reenganche: si `TWILIO_TEMPLATE_DRIP_REENGANCHE` tiene valor, manda plantilla; si no, texto libre (`tasks.py:62-75`).
- Certificados: el docstring de `enviar_certificado_whatsapp` dice que la imagen de sesión solo sirve con ventana abierta (`certificado_service.py:761-763`). La prioridad 0 es plantilla con media.
- Megáfono admin: intenta clasificar activos/inactivos 24 h (`admin/estudiantes.py:618-646`) filtrando `tipo_mensaje='recibido'` y `timestamp`. Esos campos no existen en `WhatsappLog` (`models.py:1186-1191` usa `tipo` y `fecha`). Esa consulta no puede funcionar contra el modelo actual.
- El mismo megáfono envía con `enviar_whatsapp` (Graph global), no con Twilio (`admin/estudiantes.py:574`).
- Sandbox: `enviar_sandbox_template_fallback` no manda un template de Meta; convierte el Content SID de Twilio a botones de habeas o a texto (`sandbox_canal.py:681-699`).

## 5. Timeout de Twilio (~15 s) y background

✅ el diseño de producción saca el trabajo del request, con matices.

- En `settings_production.py:448-456` el default de `WEBHOOK_CELERY_ASYNC`, `NAT_WEBHOOK_CELERY_ASYNC` y `SANDBOX_CELERY_ASYNC` es True. El POST reclama el id, hace `.delay()` y puede responder 200 (`entrada.py`, `twilio_transporte.py:23-46`, `webhook_comercial.py:18-42`, `webhook_meta.py:29-40`).
- En `settings.py:1008-1012` (no producción) el default es False: el cuerpo corre dentro del request, incluidos `time.sleep` entre burbujas (`webhook_twilio.py:3513-3515` y `:3581`).
- Nat, si Redis no acepta la tarea, cae a síncrono (`webhook_comercial.py:31-36`). El sandbox Meta, si Redis falla, responde 500 y no procesa en el request (`webhook_meta.py:32-34`, `entrada.py:102-103`).
- El background del webhook es Celery, no `threading.Thread`. Los hilos daemon están en campañas: `services.py:161-176` y `meta_waba.py:649-655`. `daemon=True`: si el proceso Gunicorn muere, el hilo se corta a mitad del lote. `ejecutada` puede quedar False (Twilio lo marca solo al terminar, `services.py:134`) y Beat puede volver a encolar (`tasks.py:415-436`, cada 300 s en `celery.py:29-31`).
- Si el worker Celery muere: `reject_on_worker_lost=True` reentrega. La 3.ª entrega no corre el cuerpo (`tasks.py:186-203`) y deja `WebhookFallido`. Si ya se creó el INCOMING, una reentrega anterior sale en `webhook_twilio.py:79` sin terminar envíos parciales.
- `SoftTimeLimitExceeded`: siempre se relanza (`tasks.py:211-217`). El log dice `no_reintenta` si ya hubo salida, pero la excepción no se convierte en éxito. Con `acks_late`, un fallo puede reentregar.
- `_eki_reply_from` se escribe al encolar (`twilio_transporte.py:41-44`) y la tarea `procesar_twilio_webhook_async` no lo lee (`tasks.py:294-309`). El `from` del cierre del webhook es `TWILIO_PHONE_NUMBER` con fallback fijo (`webhook_twilio.py:3466`).

## 6. Drip y PasoModulo

⚠️ parcial.

- Siguiente módulo: `siguiente_modulo_publicado_wa` vía `drip_schedule.py:52-57`. Bloqueo por días o por `habilitado_desde`: `mensaje_bloqueo_avance_siguiente_modulo` (`:160-196`).
- Modo de entrega: campo en el módulo (`models.py:2588`). Quién arma el texto del paso: `entregar_bloque_secciones_desde_paso` / `entregar_paso_indice` (`module_steps.py:749` y `:915`). El índice vive en `ProgresoEstudiante.paso_actual_modulo` (`models.py:2926`). El webhook lo persiste (por ejemplo `webhook_twilio.py:1554-1558`).
- Carrera de *listo*: lock de fila del estudiante y marca de tiempo en `contexto_temporal` (`response_templates.py:1250-1268`), más candado Redis por teléfono solo cuando la tarea Celery corre (`tasks.py:307`). Dos procesos sync (flag async apagado) no toman ese candado Redis.
- Reenganche diario no usa `select_for_update` ni transacción por progreso (`tasks.py:50-75`). Compara `fecha_desbloqueo.date() == ahora.date()` (`:61`), distinto de `fecha_desbloqueo_drip` que normaliza a fecha local (`drip_schedule.py:42-49`).
- `ventana_drip.py` solo cubre la pregunta abierta final y flags de fechas del cliente.

## 7. Aislamiento multi-cliente

❌ no cumple para el transporte. El enrutado de entrada sí mira números por cliente.

- Credenciales de envío Twilio salen de settings globales (`utils.py:225-232`, `whatsapp_service.py:56-58`, `enviar_plantillas.py:31-38`).
- `Cliente.twilio_account_sid`, `twilio_auth_token` y `twilio_whatsapp_from` existen (`models.py:410-427`). Grep de `twilio_whatsapp_from` y `cliente.twilio_account_sid` en código de envío: solo el modelo, el admin y la migración `0100`. El transporte no los lee.
- `Campana.linea_origen` no se lee al enviar (sección de modelos en `01_mapa.md`).
- Número de origen fijo en código (redactado en `02a`): `utils.py:109`, `whatsapp_service.py:58`, fallback `utils.py:232`, `enviar_plantillas.py:37` y `:46`, `webhook_twilio.py:3466`. `enviar_plantillas.py:45-46` sustituye el sandbox público de Twilio por ese mismo número fijo.
- Content SID de habeas/menú/cursos fijos en `whatsapp_service.py:22-32`, con override por cliente solo para habeas (`:113-131`).
- Nat: el `To` se compara con `BOT_COMERCIAL_WHATSAPP_NUMBER`, el sandbox y `Cliente.numero_whatsapp_nat` (`bot_comercial_routing.py:27-53`). La respuesta de Nat sí pasa `from_number` (`bot_comercial/webhook.py:1247-1250`).
- Campaña Meta: `phone_number_id` por campaña o `WHATSAPP_PHONE_ID` (`meta_waba.py:561`). Un solo token `WHATSAPP_TOKEN`.
- `PORTAL_WHATSAPP_SOPORTE` tiene default numérico en `settings.py:833` (redactado; no es el From de los cursos).

## 8. Logging y callbacks

⚠️ parcial.

- Sesión Twilio de `enviar_whatsapp_twilio`: PENDING → SENT o ERROR, guarda SID (`utils.py:277-355`).
- El cierre del webhook crea otro `WhatsappLog` tipo SENT con el SID y no asigna `estado` (`webhook_twilio.py:3571-3576` y `:3604-3609`). El default del modelo es PENDING (`models.py:1189`) hasta que llegue el callback.
- Status callback: `webhook_twilio.py:38-41` → `_registrar_estado_twilio_callback` (`twilio_transporte.py:77`). Actualiza estado al valor de Twilio (QUEUED, SENT, DELIVERED, UNDELIVERED, FAILED, READ).
- El callback solo se adjunta si `TWILIO_STATUS_CALLBACK_URL` está puesto (`utils.py:310-322`, `twilio_transporte.py:269-283`). `enviar_archivo_modulo_whatsapp` usa otro nombre, `TWILIO_STATUS_CALLBACK` (`whatsapp_service.py:386`).
- `enviar_plantilla_twilio` y `enviar_template_twilio` no pasan `status_callback`. El segundo solo loguea si el create tuvo éxito (`whatsapp_service.py:96-103`).
- Meta sandbox: `WhatsappLog` SENT/ERROR (`sandbox_canal.py:243-268`). **NO ENCONTRADO** un actualizador de delivered/read para wamid de sesión. `preparar_payload_meta` deja pasar `statuses` (`webhook_evento.py:146-147`) pero `_procesar_meta_webhook` solo itera `messages` (`webhook_meta.py:103-104`).
- Campaña Meta guarda wamid en `EnvioCampanaMeta` (`meta_waba.py:593-598`) y no muestra en ese método un cruce posterior con statuses.
- `portal/utils.py:71-78` no escribe log.
- Estados no unificados: `ENVIADO` / `ERROR` / `FALLIDO` / `SENT` / `PENDING` según el modelo.

## 9. Seguridad

⚠️ parcial.

- Twilio: body crudo y `RequestValidator` (el SDK usa `hmac.compare_digest`) en `twilio_webhook_security.py:63-110`, llamado antes de procesar (`entrada.py:174-184`, `webhook_comercial.py:50-54`). Se puede apagar con `TWILIO_VALIDATE_SIGNATURE` (`twilio_webhook_security.py:20-21`). En producción el default del flag es True salvo env explícito (`settings_production.py:58-62`).
- Meta: `firma_meta_ok` compara con `hmac.compare_digest` (`meta_waba.py:67-77`). `firma_meta_invalida`: si `WHATSAPP_APP_SECRET` está vacío y `WHATSAPP_REQUIRE_SIGNATURE` es False (default en `settings.py:309`), no rechaza (`webhook_evento.py:106-114`).
- Verify token GET: comparación con `==` (`entrada.py:165`), no con `compare_digest`.
- PII en logs: el webhook imprime el JSON completo (`entrada.py:193-194`) y `Body`, `From` y `To` (`webhook_twilio.py:87`). Nat en fallo definitivo hashea el teléfono (`tasks.py:143-148`). El camino feliz no.
- `Cliente.twilio_auth_token` está en el admin (`core/admin/clientes.py` fieldset). No se escribe en los logs de envío revisados. El token de Graph va en header, no en el log de `_post_graph`; el log de error sí puede incluir el JSON de error de Meta (`sandbox_canal.py:269`).

## 10. Rendimiento

❌ no cumple en los envíos masivos.

- Campaña Twilio: un `messages.create` por persona, `time.sleep(0.5)`, sin lote (`services.py:72-131`).
- Campaña Meta: igual con `sleep(0.35)` (`meta_waba.py:570-621`).
- Push: bucle sin pausa (`mensajes_push.py:74-75`).
- Reenganche: un query de todos los progresos abiertos y, dentro del loop, `dias_espera_efectivos` hace otra query por estudiante (`tasks.py:43-51` y `drip_schedule.py:28-35`).
- Webhook: varios `messages.create` seguidos con `sleep(0.5)` y `sleep` de `[DELAY:N]` dentro de la misma tarea (`webhook_twilio.py:3508-3581`). Cabe en el soft limit de 45 s solo si hay pocos segmentos.
- `WHATSAPP_RATE_LIMIT` / `WHATSAPP_RATE_PERIOD` (`settings.py:835-836`) no se usan en los `create` revisados.
- Listas de cursos: una query de cursos y una de progresos (`whatsapp_service.py:185-205`), no N+1 ahí.

## 11. Excepciones y mensaje al usuario

⚠️ parcial.

- No hay `except Exception: pass` literal en los transportes. Sí hay `except Exception: pass` en telemetría (`utils.py:374-375`) y en el reenganche (`tasks.py:93-94`).
- Los envíos Twilio/Graph devuelven dict de error y no propagan (`utils.py:379-384`, `utils.py:449-453`, `sandbox_canal.py:271-275`). El usuario no ve ese dict.
- El webhook educativo, ante excepción no capturada, manda un texto genérico de problema técnico (`webhook_twilio.py:3622-3642`). Si ese create también falla, solo `print` (`:3644-3645`).
- Errores intermedios del webhook suelen ser `print` / `logger.error` y `continue` (plantillas, `webhook_twilio.py:3492-3493`).
- `enviar_notificacion_async` importa un símbolo que no existe (`tasks.py:376`). Cualquier caller recibe el error de import y Celery reintenta 3 veces.

## 12. Tests

⚠️ parcial. Cubren firma, idempotencia, sandbox Graph (mockeado) y algunos fallbacks. No cubren el cuerpo de 3600 líneas ni un envío real.

| Área | Archivo | Qué mockea |
|---|---|---|
| Firma Twilio | `core/tests_twilio_webhook_security.py` | Request HTTP, settings de token de prueba |
| Reclamo de id | `core/tests_webhook_idempotencia.py` | `patch('core.utils.enviar_whatsapp_twilio')` en `:230` |
| Graph sandbox | `core/tests_sandbox_canal_meta.py` | `core.sandbox_canal.requests.post`, `_post_graph`, `enviar_whatsapp_twilio` |
| Menú sandbox | `core/tests_planes_linea.py`, `core/tests_sandbox_menu_event_engine.py` | `_post_graph`, `requests.post`, `enviar_sandbox_habeas` |
| From vacío | `core/tests_twilio_from_fallback.py` | settings |
| Campaña Meta | `core/tests_campana_meta.py` | HTTP de prueba |
| Campaña sin destinatarios | `core/tests_campana_servicio.py` | servicio |
| Candado | `core/tests_telefono_lock.py` | hilos / Redis si está |
| Celery Nat | `core/tests_smoke_nat_celery.py` | delay de tareas |
| Reenganche usa plantilla | `core/tests.py:368` | la tarea, con settings de template |
| Certificados | `core/tests_envio_certificados.py` | servicio de envío |
| Media sin caption | `core/tests_caption_media_sin_titulo.py` | cliente Twilio falso |

NO ENCONTRADO un test que recorra `_procesar_twilio_webhook_cuerpo` de punta a punta contra los `messages.create` internos (hay tests de ramas concretas de pasos en `core/tests_module_steps.py`, que arman texto y a veces el webhook con `Client` mockeado). NO ENCONTRADO test de `enviar_notificacion_async` contra la función inexistente. NO ENCONTRADO test de que `_eki_reply_from` cambie el From.

## 13. Código muerto, duplicado y tamaño

Funciones más largas del alcance (AST, líneas inclusive):

| Líneas | Ubicación | Nombre |
|---:|---|---|
| 3617 | `core/views/webhook_twilio.py:32` | `_procesar_twilio_webhook_cuerpo` |
| 1769 | `core/response_templates.py:545` | `get_response_for_intent` |
| 513 | `core/bot_comercial/webhook.py:807` | `_procesar_bot_comercial_twilio_webhook_cuerpo` |
| 201 | `core/utils.py:184` | `enviar_whatsapp_twilio` |
| 194 | `core/bot_comercial/webhook.py:247` | `_contexto_fallback_web_agro` |
| 190 | `core/certificado_service.py:444` | `generar_y_guardar_certificado` |
| 178 | `core/sandbox_menu.py:315` | `resolver_ruta_sandbox` |
| 178 | `core/bot_comercial/webhook.py:501` | `_bot_comercial_respuesta_catalogo` |
| 175 | `core/response_templates.py:172` | `_generar_completado_final` |
| 164 | `core/module_steps.py:749` | `entregar_bloque_secciones_desde_paso` |

Duplicado vivo:

- Tres `messages.create` de plantilla (hallazgo 1).
- `enviar_video_whatsapp` es `pass` (`whatsapp_service.py:2-3`).
- `enviar_mensaje_whatsapp` referenciada y no definida (`tasks.py:376`).
- `linea_origen` y credenciales Twilio por cliente persistidas y no leídas al enviar.
- `_eki_reply_from` escrito y no leído.

## 14. Tres números (mixto, solo IA, solo cursos)

Hoy el supuesto de un solo From de cursos está en estos puntos. Nat ya es un segundo número de entrada.

1. From de cursos: settings `TWILIO_PHONE_NUMBER` / `TWILIO_WHATSAPP_NUMBER` y el literal de fallback (`utils.py:228-232`, `webhook_twilio.py:3466`, `whatsapp_service.py:58`, `enviar_plantillas.py:34-46`). Un tercer número de “solo cursos” o “solo IA” no se elige por cliente ni por tipo de mensaje.
2. El webhook educativo no lee el `To` para elegir el From de la respuesta. Responde con el número global aunque el usuario haya escrito a otro (`webhook_twilio.py:3466-3474`). Nat sí pasa `from_number` (`bot_comercial/webhook.py:1250`).
3. El enrutado binario es “¿`To` está en el set comercial?” (`bot_comercial_routing.py:56-79` y `entrada.py:186-188`). No hay tercer cubo (mixto / solo IA / solo cursos). Lo que no es comercial cae al procesador educativo.
4. Sandbox Meta es otra línea (`SANDBOX_WHATSAPP_PHONE_ID` o `WHATSAPP_PHONE_ID`, `sandbox_canal.py:38-42`) y, con el contexto activo, todo `messages.create` del educativo se va a ese phone id (`MetaOutboundClient`, `:66-81`). No distingue “este módulo es solo IA”.
5. Plantillas de onboarding usan un From fijo, distinto del `from_number` que pudiera traer el mensaje (`whatsapp_service.py:58`).
6. Campañas Twilio no tienen selector de línea efectivo (`linea_origen` sin uso). Campaña Meta sí tiene `phone_number_id` (`models_campana_meta.py:357`).
7. `Cliente.whatsapp_numero` está documentado en el modelo como “multi-tenant futuro” (`models.py:401-408`) y el transporte no lo consulta.
8. El parche de contexto `_eki_reply_from` (`twilio_transporte.py:41-44`, `wa_reply_context.py`) es el único gancho pensado para contestar desde el mismo número, y la tarea async no lo aplica (`tasks.py:294-309`).
