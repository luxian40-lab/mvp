# PLAN_ESCALABILIDAD_EKI — Slice único

Cómo usarlo: en Cursor (Agent mode) escribe: «Lee @docs/PLAN_ESCALABILIDAD_EKI.md y ejecuta el slice siguiendo el protocolo. Empieza por el bloque P0.» La sección 1 vive en `.cursor/rules/eki.mdc` (`alwaysApply: true`).

## 0. Contexto

Monolito Django 5.2, Python 3.11, AWS Elastic Beanstalk `eki-prod-final`, RDS PostgreSQL, S3 `eki-produccion`, Celery + Redis (hoy Redis local en la misma instancia).

Apps: `core`, `portal`, `aprende`, `studio`, `formulario`.

Producto principal: línea WhatsApp Meta (menú Formación/Asesoría por plan OP1/OP2/OP3). Twilio queda para demo y campañas HSM.

`core/views.py` ya es el paquete `core/views/`. `_procesar_twilio_webhook_cuerpo` (~3.500 líneas) sigue intacto: no se toca en este slice.

`eb deploy` empaqueta HEAD (`sc: git`): lo que no esté commiteado no sube.

Objetivo del slice: poder escalar horizontalmente sin duplicar mensajes, sin romper el orden por estudiante, sin disparar costos de LLM y sin fugar datos entre clientes.

## 1. Reglas permanentes

Copiadas a `.cursor/rules/eki.mdc`. Resumen:

- Un cambio por commit. No mezclar movimiento de código con cambio de comportamiento.
- No tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`. Solo se envuelve desde afuera (tareas, locks).
- Todo archivo nuevo debe quedar en git. Cada bloque termina con `git status` y listado de archivos sin trackear.
- Migraciones compatibles hacia atrás (expand/contract). Índices en tablas grandes: `AddIndexConcurrently` con `atomic = False` en migración separada.
- Nada de SQL con f-strings. Solo ORM o placeholders.
- Tests contra PostgreSQL, no SQLite.
- `patch()` apunta al módulo donde el caller busca el nombre (`core.views.<módulo>`), no al reexport de `core/views/__init__.py`.
- Firmas Meta (HMAC-SHA256 del body crudo) y Twilio (`RequestValidator`) antes de cualquier otra lógica. `hmac.compare_digest`, nunca `==`.
- Nada de secretos en git. Config nueva = variable de entorno con default seguro.
- Antes de editar, plan de archivos. Después: `check`, `makemigrations --check --dry-run` y tests del área.
- Si un test que no estaba en el baseline falla, detenerse y reportarlo. No cambiar el test para taparlo.
- Feature flags nuevos con default que no cambia el comportamiento actual, salvo que el bloque diga lo contrario.
- 13. Meta (WhatsApp Cloud API) es el canal principal de producto. Twilio es demo y campañas HSM históricas. Todo diseño nuevo de envío, estados, límites y alertas se piensa primero para Meta y se implementa detrás de una interfaz Sender intercambiable.
- 14. Los umbrales de Meta (mps, tamaños, códigos de error, ventana de 24 h) se leen de settings, nunca van fijos en el código, y se documentan con la fecha en que se verificaron.

## 2. Protocolo del slice

Rama: `slice/escalabilidad-base`. Un commit por bloque (más commits si el bloque lo indica).

Al terminar cada bloque, imprimir este informe y esperar que el usuario escriba «continúa»:

```
BLOQUE: Px
Commits: <hashes + mensajes>
Archivos tocados: <lista>
Archivos nuevos y estado en git: <lista>
Migraciones nuevas: <lista y si son reversibles>
Resultado: check / makemigrations --check / tests del área
Riesgos o dudas: <lista>
```

Deploy: no se despliega nada hasta terminar P0–P2 y verificarlos. P3 se despliega aparte y con fallback activo. P4–P8 se despliegan por bloque.

Tareas `[MANUAL]` no las ejecuta el agente: se listan al final del informe del bloque.

## 3. Orden de ejecución

| # | Bloque | Depende de |
|---|--------|------------|
| P0 | CI + baseline de tests | — |
| P1 | Idempotencia del webhook | P0 |
| P2 | Async por defecto + lock por teléfono | P1 |
| P3 | Roles web/worker/beat + Redis gestionado | P2 |
| P4 | Envíos por lotes, idempotentes y con rate limit | P3 |
| P5 | Topes de costo LLM, antiflood y allowlist | P2 |
| P6 | Test de aislamiento multi-tenant | — |
| P7 | Resúmenes diarios + índices | P3 |
| P8 | Arreglos pequeños + docs | — |

### P0 — CI y baseline

`pytest.ini` no recogía `tests_*.py` (solo `tests.py` y `test_*.py`). Hay fallos preexistentes en `scripts/baseline_failures_before.txt`.

- `python_files = tests.py test_*.py tests_*.py`.
- `DJANGO_SETTINGS_MODULE` de pytest = settings de test con PostgreSQL (`mvp_project.settings_test`).
- GitHub Actions (remoto `origin` en GitHub) con servicio `postgres:15`:
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
  - `pytest --maxfail=20` con el comando mínimo de `docs/CHECKLIST_PRE_DEPLOY.md`
- `xfail(strict=False, reason="baseline 56929af7")` solo para los nodeids de `scripts/baseline_failures_before.txt`. No se editan esos tests.

Aceptación: CI verde en la rama; un test roto a propósito (fuera del baseline) la pone roja.

Commit: `ci: pipeline con postgres, pytest recoge tests_*.py, baseline en xfail`

### P1 — Idempotencia del webhook

`whatsapp_webhook` en `core/views/entrada.py` recibe Meta (JSON Cloud API) y Twilio (form). Meta reintenta si no recibe 200 rápido.

- Modelo `WebhookEventoProcesado(canal, external_id, creado)` con `UniqueConstraint(canal, external_id)`.
- `reclamar_evento(canal, external_id) -> bool` con `IntegrityError` → `False`.
- Después de validar la firma y antes de procesar o encolar: Meta usa `wamid`; Twilio usa `MessageSid`. Si `False`, responder 200 y no procesar.
- No deduplicar `statuses` de Meta ni status callbacks de Twilio.
- Extender `limpiar_logs_antiguos` para borrar registros de más de 7 días.
- Tests: segundo POST idéntico no procesa; 2 wamid distintos sí; statuses no se deduplican; firma inválida no crea fila.

Commit: `feat(webhook): idempotencia por wamid/MessageSid`

### P2 — Async por defecto + lock por teléfono

Tareas: `procesar_sandbox_meta_async`, `procesar_twilio_webhook_async`, `procesar_bot_comercial_webhook_async`. Flags `SANDBOX_CELERY_ASYNC`, `WEBHOOK_CELERY_ASYNC`, `NAT_WEBHOOK_CELERY_ASYNC`.

- `core/locks.py`: `telefono_lock(telefono_normalizado, timeout=90, blocking_timeout=10)` con redis-py. Clave por teléfono, no por Estudiante.
- Envolver el cuerpo de las tres tareas. Si no hay lock: `self.retry(countdown=2, max_retries=5)`. Nunca descartar el mensaje.
- Celery: `task_acks_late=True`, `task_reject_on_worker_lost=True`, `visibility_timeout=3600`, `soft_time_limit=45`, `time_limit=60` en las tareas del webhook.
- Los tres flags en `True` por defecto en `settings_production`, override por entorno.
- No modificar `_procesar_twilio_webhook_cuerpo`.
- Revisar que no haya `select_for_update` durante llamadas al LLM. Listar envíos salientes que `acks_late` podría duplicar (el candado de `listo` de 90 s cubre la entrega de módulos).

Commit: `feat(celery): webhook async por defecto, lock por teléfono, acks_late`

### P3 — Roles de proceso + Redis gestionado

Hoy `Procfile` corre web, worker, worker_rag y beat en la misma instancia con Redis local.

- `EKI_ROLE = web | worker | all` (default `all`). Scripts `scripts/run_web.sh`, `run_worker.sh`, `run_worker_rag.sh`, `run_beat.sh`. Si el rol no aplica: `exec sleep infinity`.
- Beat solo si `RUN_BEAT=1`; con `EKI_ROLE=all` sigue corriendo.
- Colas: `wa_send`, `llm`, `audio`, `rag_index`, `campanas`, `default`. `run_worker.sh` usa `-Q $CELERY_QUEUES`.
- `CELERY_BROKER_URL`, results y `CACHES` leen `REDIS_URL`; si no está, Redis local actual.
- `CONN_MAX_AGE` desde env (default 60) y `conn_health_checks=True`.
- `migrate_locked` con `pg_advisory_lock(727274)` en la misma conexión. Hook `02_migrate.sh` lo usa.
- Transcripción de audio solo en la cola `audio` (concurrencia 1), no en el request web. Pendiente de este bloque: `transcribir_audio` y `transcribir_audio_meta` siguen dentro del request, porque salen del cuerpo del webhook y ese cuerpo no se reescribe aquí. La cola `audio` ya está declarada.

Workers lógicos (añadido): `conversacion` (webhooks Meta, Twilio y Nat) y `masivo` (campañas, reenganche, resúmenes). `run_worker.sh` toma `-Q` de `CELERY_QUEUES`. El default es el superconjunto `conversacion,masivo,celery,media_encode` para que esas rutas tengan consumidor. `rag_index` sigue en `run_worker_rag.sh`. La cola `celery` es el `default` del plan y la de Beat.

Pool y tiempos: el default de `run_worker.sh` es prefork implícito (sin `--pool`) y `--concurrency=1` (`CELERY_POOL`, `CELERY_CONCURRENCY`). `CELERY_POOL=threads` comparte la memoria del proceso, así que una llamada larga al modelo no multiplica el RSS. En hilos, `soft_time_limit` (45 s) y `time_limit` (60 s) no matan el hilo: Celery solo interrumpe procesos del pool prefork. Un hilo que se pasa de tiempo sigue ocupando cupo, y el tope real pasa a ser el candado Redis de 90 s. `reject_on_worker_lost` cubre la muerte del proceso, no un hilo colgado.

Regla de pool: prefork con concurrencia 2 si, tras arrancar web, worker, worker_rag y beat, quedan al menos 1,2 GiB libres. `threads` solo cuando cada llamada HTTP que esas tareas puedan hacer ya tiene timeout, y ese worker no lleva `--max-tasks-per-child` (un hilo no se recicla como un proceso hijo). El default de hoy sigue en prefork y concurrencia 1.

Alarma: `CPUCreditBalance` de la instancia T. El env guardado es t3.medium y `.ebextensions` dice t3.large. Si el saldo de créditos baja y no se recupera, la CPU se ahoga aunque el promedio se vea bajo. Mirarla en CloudWatch antes de subir el tipo de instancia.

Advisory locks y pooler: `pg_advisory_lock` es de sesión. PgBouncer en modo transaction, y RDS Proxy, pueden devolver la conexión al pool entre sentencias: el candado queda en otra sesión o se suelta. `migrate_locked` vale con una conexión directa a Postgres, sin pooler en medio.

[MANUAL] ElastiCache, `REDIS_URL` en staging y luego prod, entorno `eki-prod-worker`, PITR de RDS y un restore real. No migrar RDS a Postgres en EC2.

Commit: `feat(infra): EKI_ROLE, colas, REDIS_URL, migrate con advisory lock`

### P4 — Solo Meta para campañas y reenganche (diseño, sin código)

Sustituye el P4 de lotes y el de dos Senders en paralelo. No hay cohorte viva que migrar: campañas y reenganche tienen un solo camino, `MetaSender`. `TwilioSender` queda detrás de la misma interfaz, sin métodos nuevos, y solo atiende demo y HSM históricos que ya existen. Este bloque no se implementa hasta que estén listos el dry-run, el restore de RDS y la carga sintética.

`reenganche_inactivos_diario` sigue apagado (`REENGANCHE_INACTIVOS_ENABLED=False`). [MANUAL] Activar o no el reenganche de inactivos a las 09:00.

#### Sender

```text
ResultadoEnvio
  estado: ENVIADO | ERROR | INCIERTO
  provider_id: wamid o SID, o vacío
  codigo_error: str o vacío
  reintentable: bool

Sender
  enviar_plantilla(destino, plantilla, variables, correlacion) -> ResultadoEnvio
  enviar_texto(destino, cuerpo, correlacion) -> ResultadoEnvio

MetaSender    único camino de Campana, CampanaMeta y reenganche
TwilioSender  legacy: demo y HSM ya escritos. No se extiende.
```

No se reescribe el historial. Rellenar `linea_origen` con la línea Meta en campañas que salieron por Twilio falsearía el dato.

`Campana.proveedor` es `meta` o `twilio`. Expand: la columna nace con default `twilio`, así el backfill marca de Twilio todo lo que ya existe. Después, el default del modelo pasa a `meta` (un `AlterField` de default no toca las filas viejas). Lo nuevo sale por Meta. `linea_origen` sigue pudiendo ser null en la base. Obligatoria solo al crear una campaña (formulario o `clean` cuando `pk` es null). Las filas históricas no se fuerzan.

El primer grupo, unas 150 personas, usa `CampanaMeta` (plantilla de Graph que ya existe) si el bloque X confirma que ese camino es viable. El código completo de P4 (claim, bucket, reconciliación) va después del lanzamiento.

#### Carga sintética

No hay estudiantes reales para medir el pico de las 08:00, el Centro de Éxito ni los resúmenes. El generador, cuando se escriba, tiene cuatro piezas:

- Servidor local de Graph: `POST /{phone-id}/messages` responde 200 con un wamid falso. Un query o header pide 131056, 131047 o un timeout.
- Payloads de webhook Meta firmados con el `WHATSAPP_APP_SECRET` de prueba (HMAC-SHA256, `compare_digest` del lado receptor).
- Organización de prueba con 200 estudiantes ficticios, teléfonos que no existen en la línea real.
- Locust (o un script) que dispara el reenganche y el webhook contra ese Graph. La salida muestra latencia, profundidad de cola (`LLEN` de `masivo` y `conversacion`) y errores por código.

La meta de la prueba es el pico de las 08:00, no un envío a personas.

#### Orden de esta ventana

1. `reenganche_dry_run` y `campanas_pendientes` (ya escritos; no envían).
2. Verificación manual en EB: secreto de Meta, token, `TWILIO_VALIDATE_SIGNATURE`.
3. PR a main con el job `test` obligatorio, y deploy del slice con los tres flags async en false.
4. Restore de un snapshot de RDS a una instancia temporal. Valida el backup y las migraciones 0159/0160 sobre una copia. El clon de la app queda opcional. Rollback de código: `main-20261001-213708`.
5. `kill -9` y prueba de `redelivered` en horas muertas, solo con el teléfono interno.
6. Carga sintética, y después el código de P4.

`MetaSender` manda `correlacion` en `biz_opaque_callback_data`. Meta lo devuelve en `statuses[].biz_opaque_callback_data` solo si se envió. Verificado el 2026-10-03 en la referencia de webhooks de estado (campo `messages`). El valor es el id del `EnvioLog`. No se deduplica por wamid: P1 ya dejó los `statuses` fuera del reclamo.

HTTP 200 con `messages[].id` → `ENVIADO`. HTTP 4xx con código conocido no reintentable → `ERROR`. Timeout, 5xx o corte sin cuerpo → `INCIERTO`. Un `INCIERTO` no se reenvía solo.

#### Claim

Estados del registro: `PENDIENTE` → `ENVIANDO` → `ENVIADO` | `ERROR` | `INCIERTO`.

El claim es un `UPDATE … WHERE id=%s AND estado='PENDIENTE'` (compare-and-set). `rowcount == 1` gana y escribe `intento_en`. Cualquier otro worker ve 0 filas y no envía.

Si el proceso muere o el HTTP no responde después del claim, el registro queda `ENVIANDO`. Una tarea de Beat pasa a `INCIERTO` todo `ENVIANDO` con `intento_en` de más de 10 minutos (`WA_ENVIANDO_DUDOSO_MIN`, default 10). No reenvía.

#### Reconciliación

El webhook `statuses` (sent, delivered, read, failed) busca el `EnvioLog` por `correlacion`. Si está `INCIERTO` o `ENVIANDO` y el estado es sent, delivered o read, pasa a `ENVIADO` y guarda el wamid. `failed` pasa a `ERROR` y guarda `errors[].code`. Las métricas cuentan enviados, entregados, leídos y fallidos por código. Hoy ese webhook no se lee: ver inspección S.

#### Token bucket

Redis, una clave global por proveedor (`INCR` + ventana de 1 s, o bucket). No el `rate_limit` de Celery.

| Setting | Default | Verificado |
| --- | --- | --- |
| `WA_META_MPS` | 20 | 2026-10-03. Throughput de Cloud API: 80 mps por número registrado; 20 mps si el número convive con la app de WhatsApp Business. 20 es el arranque conservador, no el tope de la cuenta. |
| `WA_TWILIO_MPS` | 3 | Tope propio de eki para el canal demo. |
| `WA_DESTINO_GAP_SEG` | 6 | El código 131056 dice «demasiados mensajes al mismo destinatario en poco tiempo» y pide esperar. Meta no publica «6 s» en esa fila (error codes, 2026-10-03). 6 s es el hueco conservador de este diseño y vive en el setting. |

Clave Redis por par remitente+destino. Si no hay ficha, el mensaje espera; no se marca error.

#### Errores Meta → acción

Leídos de settings (`WA_META_ERRORES`, mapa código → acción), con esta tabla como default. Fecha de la tabla oficial: 2026-10-03.

| Código | Acción |
| --- | --- |
| 130429, 131056 | Reintento con backoff y jitter. 131056 solo hacia ese destinatario; el resto sigue. |
| 131047 | Fuera de la ventana de 24 h. No reintentar el texto libre: cambiar a plantilla aprobada. |
| 131026, 131048, 131049 | No reintentar. Marcar `ERROR` y contar. 131048 es restricción del número (spam); 131049 es límite de ecosistema. |
| 190 | Alerta crítica y parar la cola de envíos. Token caducado o inválido. |

131052 es fallo al descargar media que mandó el usuario. 131053 es fallo al subir la media del mensaje saliente. Ninguno reintenta el mismo archivo a ciegas: se cuentan y se dejan para el reenvío de media cuando exista en Meta.

#### Pausa de campaña

Si la tasa de fallo de plantilla en una campaña pasa el umbral en la muestra inicial, la campaña se pausa sola. Settings: `WA_CAMPANA_FALLO_UMBRAL` default `0.15`, `WA_CAMPANA_FALLO_MUESTRA` default `100`. Protege la calidad del número. Hace falta un booleano nuevo `pausada_automatica` (default `False`) en `Campana` y en `CampanaMeta`.

#### EnvioLog (expand, luego contract)

Hoy (`core/models.py`, `EnvioLog`): `campana`, `estudiante`, `estado` (`CharField` 20, default `PENDIENTE`), `respuesta_api`, `fecha_envio`. El servicio de campaña escribe `ENVIADO` o `FALLIDO` después del HTTP. No hay `ENVIANDO` ni constraint.

Expand (columnas nuevas, null o blank, sin reescribir filas, reversible):

- `proveedor` (`''`)
- `provider_id` (`''`, wamid o SID)
- `codigo_error` (`''`)
- `reintentable` (null)
- `correlacion` (`''`, índice; el id del registro como texto)
- `intento_en` (null)

`ENVIANDO`, `ERROR` e `INCIERTO` caben en `estado` (max 20). `FALLIDO` se sigue leyendo.

Antes del `UniqueConstraint` parcial `(campana, estudiante)` para filas en `PENDIENTE`, `ENVIANDO`, `ENVIADO` o `INCIERTO`: correr `auditar_envios_duplicados` y mostrar la salida. Si hay duplicados, no se crea el índice. `ERROR` puede repetirse (un intento fallido no bloquea un envío nuevo decidido a mano).

Contract, en un bloque posterior y con el código ya escribiendo las columnas nuevas: dejar de escribir `FALLIDO` (mapear a `ERROR`) y dejar `respuesta_api` solo como texto legado. No se borra la columna en el mismo deploy que la deja de usar.

#### Fuera de este bloque

No entran aquí, aunque la inspección S los deja abiertos: alerta del 190 en el proceso actual, lectura de `quality_rating` / tier, subida a `/media` (el `media_id` de un upload caduca a los 30 días; el de un webhook entrante, a los 7. Verificado 2026-10-03 en la doc de Media), y el pin `GRAPH_API_VERSION`. Hoy la versión es `WHATSAPP_API_VERSION` con default `v19.0`.

#### Tests (cuando se implemente)

- Claim: dos workers, uno solo pasa de `PENDIENTE` a `ENVIANDO`.
- Timeout simulado después del claim → `INCIERTO`, y un segundo tick no vuelve a llamar al Sender.
- Webhook `statuses` con `biz_opaque_callback_data` igual a la correlación: `INCIERTO` → `ENVIADO`. `failed` guarda el código. Dos entregas del mismo wamid no crean dos filas.
- `ENVIANDO` con `intento_en` de más de 10 min → `INCIERTO`.
- El bucket de Redis, no el `rate_limit` de Celery, frena por encima de `WA_META_MPS`.
- 131047 no reintenta el texto; 131026 no reintenta; 130429 sí, con jitter; 190 no llama al Sender y marca la cola parada.
- 15 fallos de plantilla en los primeros 100 dejan `pausada_automatica`.
- La migración expand corre sobre filas viejas `ENVIADO`/`FALLIDO` sin tocarlas.

Commit, cuando se escriba el código: `feat(envio): Sender, claim atómico y tope Redis`. Este documento no lo hace.

### P5 — Topes de costo del LLM

- Modelo `UsoLLM` + registro en `openai_compat`. Precios por modelo en settings (`gpt-5-mini`, `gpt-5`, `gpt-5-nano`).
- `LLM_PRESUPUESTO_DIARIO_USD`: si se supera, respuesta degradada (fallback existente) y alerta. Contador Redis `INCRBYFLOAT` con TTL. No bloquea `listo` ni el curso, solo el LLM.
- Antiflood: `LINEA_MAX_MSG_MIN` default 12.
- `LINEA_META_SOLO_REGISTRADOS` default `True`, sin bloquear onboarding (habeas → cédula).
- Timeouts explícitos; fallback Gemini detrás de un flag.

Commit: `feat(llm): ledger de uso, presupuesto diario, antiflood y allowlist`

### P6 — Aislamiento multi-tenant

`portal/tests_tenant_isolation.py`: dos `Cliente`. Usuario del A recorre URLs de `portal/urls.py` con IDs del B. Exigir 403/404 o body/JSON sin datos del B. Igual para exports y `POST /portal/retencion/agente/`.

Si algo falla, no arreglarlo en ese commit: listar y detenerse.

Commit: `test(portal): aislamiento multi-tenant sobre todas las rutas`

### P7 — Resúmenes diarios + índices

- `ResumenDiarioCurso` con `UniqueConstraint(fecha, cliente, curso)`.
- Tarea 03:00 America/Bogota, idempotente. `backfill_resumen_diario --dias 90`.
- Centro de Éxito e Inicio leen agregados; el score por estudiante sigue en vivo.
- Migración aparte (`atomic = False`): `AddIndexConcurrently` en `WhatsappLog(estudiante, agente_usado, fecha)` y `EstudianteEventoAprendizaje(estudiante, tipo, creado)`. Antes, `EXPLAIN`.

Commit: `perf(analitica): resumen diario e índices`

### P8 — Arreglos pequeños (commits separados, cada uno con test)

a) `detect_intent`: palabras completas `(?<!\w)palabra(?!\w)`. «casi» y «perseguir» no son `continuar_leccion`. Con evaluación abierta, pedir A–D, no avanzar.

b) Código del aula: máx. 5 intentos / 10 min en Redis (`aprende/acceso_whatsapp.py`).

c) `settings_production.py`: si falta `EKI_ALLOWED_HOSTS`, `ImproperlyConfigured` (no `['*']`). `INTEGRACION_API_REQUIRE_KEY` default `True`.

[MANUAL] Confirmar en EB que ambas variables están seteadas antes de desplegar ese commit.

d) Docs: quitar reenganche 09:00 hasta decidir; alinear guía §9.2 con auditoría §7; añadir `studio` a auditoría §13; `core/views/admin_panel.py` en guía §11.5 y Apéndice A; Django 5.2 y Meta como canal principal en §2.1; marcar en §25 que la firma Twilio ya está implementada.

## 4. Checklist de deploy

```bash
git status
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
git log --oneline -n 20
```

Revisar migraciones nuevas (compatibles con el código del rollback). `eb deploy`, Health Green, smokes `/health/`, `/portal/login/`, `/aprende/`, `/studio/`, mensaje de prueba. Logs sin `ImportError` ni errores de lock/Redis. Anotar versión desplegada y rollback.

## 5. Rollback por bloque

| Bloque | Cómo se revierte |
|--------|------------------|
| P1 | `eb deploy` versión anterior. La tabla nueva queda inerte. |
| P2 | Flags `*_CELERY_ASYNC=false` por entorno (sin redeploy). |
| P3 | Quitar `REDIS_URL` y `EKI_ROLE` (vuelve a Redis local y a `all`). |
| P4 | Versión anterior. El constraint parcial puede dejarse. |
| P5 | `LLM_PRESUPUESTO_DIARIO_USD` alto, `LINEA_META_SOLO_REGISTRADOS=false`. |
| P7 | Versión anterior. Los paneles vuelven a calcular en vivo. |

## 6. Definición de terminado

- CI verde y obligatorio en la rama principal.
- Mensaje duplicado de Meta/Twilio no se procesa dos veces.
- Dos mensajes simultáneos del mismo teléfono se procesan en orden.
- Webhook responde 200 antes de la lógica pesada.
- Redis gestionado en uso; beat corre en una sola instancia.
- Migraciones con advisory lock.
- Campañas y reenganche por lotes, idempotentes y con rate limit.
- Presupuesto diario de LLM, antiflood y allowlist activos.
- Test de aislamiento multi-tenant en verde (o fallos listados y asignados).
- Paneles leyendo resúmenes diarios; índices creados.
- RDS con PITR y un restore probado.
- Docs sin contradicciones.
