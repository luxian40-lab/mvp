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

Workers lógicos (añadido): `conversacion` (webhooks Meta, Twilio y Nat, más `media_encode`) y `masivo` (campañas, reenganche, resúmenes). `run_worker.sh` toma `-Q` de `CELERY_QUEUES`. El default escucha `conversacion,masivo,celery,media_encode` en un solo proceso, igual que hoy un worker. Para separarlos, dos procesos con `CELERY_QUEUES=conversacion,media_encode` y `CELERY_QUEUES=masivo`. `rag_index` sigue en `run_worker_rag.sh`. La cola `celery` es el `default` del plan: lo que no tiene ruta sigue ahí.

Pool y tiempos: el default de `run_worker.sh` es `--pool=prefork` y `--concurrency=1` (`CELERY_POOL`, `CELERY_CONCURRENCY`). `CELERY_POOL=threads` comparte la memoria del proceso, así que una llamada larga al modelo no multiplica el RSS. En hilos, `soft_time_limit` (45 s) y `time_limit` (60 s) no matan el hilo: Celery solo interrumpe procesos del pool prefork. Un hilo que se pasa de tiempo sigue ocupando cupo, y el tope real pasa a ser el candado Redis de 90 s. `reject_on_worker_lost` cubre la muerte del proceso, no un hilo colgado. No subir la concurrencia de hilos por encima de lo que aguanten ese candado y el límite de 60 s.

[MANUAL] ElastiCache, `REDIS_URL` en staging y luego prod, entorno `eki-prod-worker`, PITR de RDS y un restore real. No migrar RDS a Postgres en EC2.

Commit: `feat(infra): EKI_ROLE, colas, REDIS_URL, migrate con advisory lock`

### P4 — Envíos por lotes, idempotentes y con rate limit

- Primero `auditar_envios_duplicados` (pares campana+estudiante con más de un `EnvioLog`). Mostrar salida y esperar.
- Con salida limpia: `UniqueConstraint` parcial en `EnvioLog(campana, estudiante)` solo para envío efectivo. Solo `ENVIADO` cuenta como éxito (el código no escribe `exitoso`). Confirmar estados con el usuario.
- Tarea padre encola lotes de 50 (`rate_limit="20/s"`). Hija: backoff con jitter ante 429; `get_or_create` antes de enviar.
- Mismo patrón para `reenganche_drip_content_diario`.
- `reenganche_inactivos_diario` listo pero `REENGANCHE_INACTIVOS_ENABLED=False`.

[MANUAL] Activar o no el reenganche de inactivos a las 09:00.

Commit: `feat(campanas): envío por lotes, idempotente y con rate limit`

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
