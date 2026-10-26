# Continuar eki — 25 de octubre de 2026

Handoff para la siguiente sesión. `main` es lo que está en producción.

## Dónde quedó el código

- Producción `eki-prod-final`: versión `main-tareas-programadas-20261025-200537`, commit `ebbdfecb`. `main` lo lleva y solo le suma este documento. Rollback: `main-mps-por-linea-20261025-194649` (commit `e913274b`), que vuelve a los tres fallos de abajo pero no rompe nada más.
- Revisión de producción del 26 de octubre (UTC), solo lectura. Webhook de WhatsApp sin 429 ni 400, `WebhookFallido` vacío en 7 días, colas vacías; los 502 y 429 de nginx son bots buscando `.env` y `.php`. Arreglado y desplegado: (1) `generar_reporte_actividad` y `limpiar_logs_antiguos` importaban `MensajeChat`, que nunca existió, y fallaban siempre; la limpieza nocturna no purgaba nada. Ahora purga `WebhookEventoProcesado` y `WebhookFallido` de más de 10 días y `MetaWebhookEvento` de más de 30. (2) Beat programaba `core.tasks_infra.revisar_infra_advisor` y el worker no la tenía (`KeyError` cada hora); `CELERY_IMPORTS` la registra. Corre a los :15 y manda email a `ADMINS` si el estado pasa a ACTUAR, máximo uno cada 6 h. (3) `www.eki.technology` respondía 400; ya entra y redirige como `eki.technology`.
- Abierto, decidido no tocar: `WhatsappLog` no se purga (14 107 filas desde febrero, 10 470 de más de 90 días). Es decisión de retención y habeas data, no un bug.
- Fase I2 (tope de mensajes por segundo por línea) desplegada con `WA_META_BUCKET_POR_LINEA` apagado: cada phone id con su bucket y su tope de `WA_META_MPS_POR_LINEA` (`phone_id:mps,...`). Hoy no cambia nada aunque se prenda: el bucket solo lo usa Campañas Meta v2 y `META_CAMPANAS_V2_ENABLED` está en `false`; las campañas salen por el camino viejo con 0,35 s entre mensajes. Prender v2 no es neutro: omite a quien no tenga opt-in y no verifica que el phone id sea del WABA. Línea principal (`...5771`): throughput `STANDARD` (80 mps), no convive con la app, calidad `GREEN`. La línea 2 no está en la base todavía; al crearla, mirar su throughput con `GET /<phone_id>?fields=throughput` (20 mps si convive con la app de WhatsApp Business).
- Las tareas de webhook (`_WEBHOOK_TASK`: Meta, Twilio, Nat) llevan `ignore_result=True`: devolvían el `HttpResponse` de la vista, Celery no lo podía serializar y cada mensaje quedaba como tarea fallida y fila en `WebhookFallido` aunque la respuesta sí salía. Claves de contexto que sobreviven con `EKI_CONTEXTO_CONSERVA_CLAVES` apagado (sin migración); prenderlo es `eb setenv EKI_CONTEXTO_CONSERVA_CLAVES=true` y apagarlo, `false`. Fases A a F de `docs/PLAN_MODULARIDAD_EKI.md`: estado por persona y línea (tabla `EstadoLinea`, migración `0191`); puertas en `core/conversacion/puertas.py`; menú, carrusel, cursos empezados y asesores en `core/lineas/principal/`. Una nota de voz de Meta se transcribe una vez por turno (`core/conversacion/transcripcion_turno.py`). Cursos por línea (`LineaWhatsapp.cursos`, migración `0192`) con `EKI_CURSOS_POR_LINEA` apagado.
- Más atrás: `main-tareas-sin-resultado-20261025-192242` (commit `49632bb0`) y `main-contexto-claves-20261025-184511` (commit `daaf8d18`), pero con `SANDBOX_CELERY_ASYNC=true` esa versión vuelve a dejar cada mensaje como tarea fallida: si se hace rollback, apagar antes `SANDBOX_CELERY_ASYNC`. Antes, `main-cursos-por-linea-20261025-180030` (commit `243e7ff0`) y `main-audio-una-transcripcion-20261025-171016` (commit `57c311e8`): la tabla `core_lineawhatsapp_cursos` no le estorba mientras nadie borre un curso o una línea que esté en una lista.
- Para usar cursos por línea: en Líneas de WhatsApp crear la fila de la línea 2 con su phone id (no hace falta `EKI_LINEAS_BD_ENABLED`), elegir sus cursos y prender `EKI_CURSOS_POR_LINEA=true`. Lista vacía = todos. El foco automático del curso de la línea 2 solo corre con `EKI_ESTADO_LINEA_LECTURA`.
- Estado por línea, prendido completo. El 25 de octubre a las 22:16 UTC: `backfill_estado_linea --aplicar` (8 filas) y `EKI_ESTADO_LINEA_ESCRITURA=true`. El 26 de octubre (UTC): revisión de filas (8, todas iguales al estado compartido; casi sin tráfico), segundo `--aplicar` (0 por crear), `CELERY_CONCURRENCY=2` (memoria disponible 2,6 GiB de 3,8, §1.8 de `docs/RUTA_FINAL_EKI.md`), `SANDBOX_CELERY_ASYNC=true` a las 00:06 y `EKI_ESTADO_LINEA_LECTURA=true` a las 00:34, cada paso con prueba desde el teléfono interno y tareas `succeeded` en el worker. `WEBHOOK_CELERY_ASYNC` y `NAT_WEBHOOK_CELERY_ASYNC` siguen en `false`. Apagar, en este orden: `EKI_ESTADO_LINEA_LECTURA=false`, luego `SANDBOX_CELERY_ASYNC=false`; las filas se quedan y no estorban. Seguir mirando que las filas no se aparten del estado compartido mientras haya una sola línea con tráfico.
- Decidido el 25 de octubre: los campos viejos de estado se siguen escribiendo como espejo (E4 espera); las líneas `contexto_temporal = None` pasan a una lista de claves que sobreviven, detrás de `EKI_CONTEXTO_CONSERVA_CLAVES` (apagado, ya en producción), un archivo por commit. Las dos del cuerpo (selección de curso) no se tocaron. Detalle en `docs/PLAN_MODULARIDAD_EKI.md`, fase E.
- Tests que fallan según el orden en que corren: los de hilos (`tests_telefono_lock`, `tests_webhook_idempotencia`) escriben fuera de la transacción del test y a veces tumban `tests_medicion_turno` o `test_dos_hilos_un_solo_true`. Pasa también en `main`; no es de ningún cambio reciente.
- `slice/escalabilidad-base` quedó atrás de producción. Desplegarla sería un rollback de dos semanas.
- `.ebignore` existe, así que `eb deploy` comprime la carpeta tal como está en disco, no `git archive`. Desde una carpeta sucia subirían archivos sin commit; desde un worktree limpio, lo que no tiene commit no existe y el web arranca con `ImportError`.

## Cómo commitear y desplegar

1. Un cambio por commit, en una rama que sale de `main`. No mezclar con el árbol sucio (Aprende, settings, docs de auditoría, scripts `qa_*`, conectores ajenos).
2. Para desplegar, adelantar `main` sin merge: `git fetch . <rama>:main` (falla si no es fast-forward; en ese caso rebasar la rama sobre `main`).
3. Worktree limpio de `main`: la primera vez `git worktree add --detach C:\Users\luxia\eki_deploy_main main`; después `git -C C:\Users\luxia\eki_deploy_main checkout --detach main`. `git status` vacío y sin archivos sin trackear.
4. Label `main-<tema>-YYYYMMDD-HHMMSS`. Anotar la versión anterior (`eb status eki-prod-final`) antes de subir. Desplegar desde esa carpeta.
5. Después: `/health/` en `http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/health/` debe ser 200.
6. Si hay rollback en EB, revertir también el commit en `main`: `main` no puede quedar adelante de producción.
7. No hay más cherry-pick sobre árboles viejos. Los worktrees `eki_deploy_*` anteriores son historia.

Reglas fijas que ya están en `.cursor/rules/eki.mdc`: no tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`; firma Meta/Twilio antes de cualquier lógica; `patch()` al módulo que usa el nombre.

## Meta ya hace esto

- Línea de producto y menú sandbox (agentes, incluido el experto en café).
- Imagen del diploma. `enviar_whatsapp_twilio` llama a `core/views/diploma_meta.py` y, si el texto es el certificado, sale por Graph y no llega a la API de Twilio. Cubre el cierre del curso y el botón de enviar del admin.
- Respuesta de PQRS: `core/pqrs_respuesta.py` usa `core/views/pqrs_meta.py`. Si Meta falla, el caso sigue pendiente.
- Pruebas: `core/tests_diploma_y_pqrs_meta.py` y `core.tests_pqrs_agent.TestPQRSRespuestaWhatsApp`.

## Twilio se queda solo para el código de *aula*

El aula es Aprende: el mismo curso, en la web. En el número de Twilio la puerta (`core/twilio_puerta.py`, llamada desde `core/views/entrada.py` y desde la tarea Celery) solo hace dos cosas: si escriben *aula*, manda el código; cualquier otra palabra recibe el aviso de que el curso sigue en Meta y no entra a las 3.522 líneas. Un callback de estado sí entra, solo para registrar entrega. Quien escribe al número de Meta y pone *aula* recibe el código por Meta (`responder_aula_meta`). El curso por Meta sigue reentrando a esa función grande: no se reescribe.

La plantilla de diploma en Meta ya se puede usar. En admin, Configuración Global, campo «Diploma — nombre de plantilla Meta». Encabezado imagen; cuerpo `{{1}}` nombre, `{{2}}` curso, `{{3}}` código. Vacío: se sigue mandando la imagen de sesión (la persona tiene que haber escrito en 24 h, o escribir y reenviar). Con nombre, y cuando Meta la haya aprobado, el botón Enviar certificados por WhatsApp usa esa plantilla. Si Meta la rechaza, cae a la imagen. El aviso `HX…` de Twilio sigue hasta que esa plantilla esté aprobada y el envío real salga bien.

### Sigue en Twilio y se puede quitar después del aula

Cada fila es un commit. `enviar_whatsapp_twilio` se queda: por ahí salen el código de *aula* y el aviso de número cerrado. Lo de abajo es salida que todavía puede llamar a Twilio aunque nadie escriba el curso en ese número.

| Qué | Dónde | Condición para quitarlo |
|---|---|---|
| Aviso previo del diploma con plantilla `HX…` | `core/certificado_presencial_service.py` (`enviar_previo_whatsapp`, `_enviar_plantilla_twilio_cert`) y `core/certificado_service.py` (`_enviar_plantilla_media_twilio`, `enviar_plantilla_twilio`) | Solo después de que la plantilla de imagen en Meta esté aprobada y un envío real salga bien. El código ya la usa si el nombre está en Configuración Global. |
| Campañas HSM viejas | `core/services.py`, `core/admin_campana_actualizado.py`, `core/enviar_plantillas.py` | Confirmar que no hay campaña viva en Twilio. El camino nuevo ya es `CampanaMeta`. |
| Mensaje del admin al estudiante, avisos, gamificación | `core/admin/estudiantes.py`, `core/admin/cursos.py`, `core/mensajes_push.py`, `core/gamificacion_actions.py`, `core/seguimiento_proactivo.py`, `core/whatsapp_service.py` | El mismo texto sale por `enviar_meta` / Graph. |
| Bot comercial y carrusel demo fuera de la línea Meta | `core/bot_comercial/webhook.py`, `core/bot_comercial/productos_media.py`, `core/catalogo_demo_carousel.py` | Dentro del sandbox Meta ya se intercepta. Fuera, sigue Twilio. |
| Reintento de media | `core/media_entrega.py` | Solo si el log es de Twilio. Un video de aula no se mueve. |

El aviso `HX…` se quita cuando el envío real con la plantilla Meta esté aprobado. No es borrar Twilio entero. Aprende y el aula son el mismo curso.
