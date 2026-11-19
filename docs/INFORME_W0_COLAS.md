# Informe W0 — inventario de colas

Fecha: 2026-11-19. Solo lectura de código y Procfiles. Sin cambio de máquinas ni variables en EB.

Fuente: `docs/PLAN_WORKERS_EKI.md` corte W0. Gate: tabla caja / proceso / colas / Redis.

## Tabla (código en `origin/main` @ 18858ca1)

| Caja | Proceso | Colas que escucha | Beat | Redis |
| --- | --- | --- | --- | --- |
| `eki-prod-final` | `Procfile` → `scripts/run_web.sh` | n/a (web) | no | Caída histórica a `127.0.0.1` si falta `REDIS_URL` y `EKI_REDIS_FAIL_CLOSED=false` |
| `eki-prod-final` | `scripts/run_worker.sh` (`fast@`) | Default `conversacion,masivo,celery,media_encode,llm,certificados`. Con `EKI_MEDIA_ENCODE_SOLO_AI` y sin `CELERY_QUEUES`: quita `media_encode` | no | Idem |
| `eki-prod-final` | `scripts/run_worker_rag.sh` | `rag_index` | no | Idem |
| `eki-prod-final` | `scripts/run_beat.sh` | n/a (beat) | **sí** | Idem |
| `eki-ai-workers` | `Procfile.ai` → `worker_media` | `media_encode` | no | Idem |
| `eki-ai-workers` | `Procfile.ai` → `worker_rag` | `rag_index` | no | Idem |
| `eki-ai-workers` | `Procfile.ai` → `worker_course` | `course_engine` | no | Idem |
| `eki-ai-workers` | `run_worker.sh` si alguien lo arranca | `sleep infinity` cuando `EKI_EB_ROLE=ai_workers` — no lee `conversacion` ni `masivo` | no | Idem |

## Dueños (quién produce / quién consume)

| Cola | Productores (rutas) | Consumidor esperado |
| --- | --- | --- |
| `conversacion` | webhooks Meta/Twilio/Nat, `continuar_entrega_marcada_async` | solo `eki-prod-final` / `fast@` |
| `masivo` | campañas, reenganche, avisos, recordatorios, reportes | `fast@` (aún mismo proceso que conversación) |
| `celery` | beat y tareas sin ruta | `fast@` |
| `media_encode` | `encode_paso_modulo_media` | **dos cajas hoy**: default de `run_worker.sh` **y** `eki-ai-workers` `worker_media`. Flag `EKI_MEDIA_ENCODE_SOLO_AI` (apagado) deja un solo dueño en AI |
| `rag_index` | indexación Nat/RAG | `worker_rag` en ambas cajas (prod + AI) |
| `course_engine` | Course Engine | solo `eki-ai-workers` |
| `llm` / `certificados` | rutas I1 si `EKI_COLAS_POR_TIPO` | en el default de `fast@`; sin flag las tareas van a `celery` |

## Tres cifras del camino a 5.000 (anotación W0)

Sin pantalla Entregas ni acceso live a Redis en este corte:

| Cifra | Estado en este informe |
| --- | --- |
| Tasa de duplicados | No medida en vivo. Claim `OutboxEnvio` existe detrás de `EKI_OUTBOX_ENVIO` (apagado). |
| Latencia / edad de cola `conversacion` | No medida en vivo. |
| `INCIERTO` abiertos | Modelo y beat `vencer_outbox_enviando` existen; conteo live pendiente de Entregas. |

## Hallazgo bloqueante para W1

`media_encode` tiene **dos consumidores** potenciales mientras `EKI_MEDIA_ENCODE_SOLO_AI` esté apagado. W1 no arranca dueño único hasta decidir: prender el flag (prod deja de escuchar encode) o quitar `media_encode` del default de `run_worker.sh`.

## Redis

- Código: `mvp_project/infra_redis.py` + `EKI_REDIS_FAIL_CLOSED` (default apagado en settings base; producción lo lee del env).
- Con flag apagado, sin `REDIS_URL` → `redis://127.0.0.1:6379/0`.
- Cierre del bloque 2: sin caer a localhost en producción (fail-closed).
