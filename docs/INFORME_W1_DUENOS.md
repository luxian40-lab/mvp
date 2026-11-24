# Informe W1 — dueño de cada cola

Fecha decisión: 2026-11-19. Cierre formal código: **2026-11-23** (auditoría en `origin/main`).

Fuente: `docs/PLAN_WORKERS_EKI.md` corte W1. Antecedente: `docs/INFORME_W0_COLAS.md`. Gate desplegado: `docs/INFORME_GATE_BLOQUE_2.md` (`main-bloque-2-gate-20261119-141312`).

## Decisión

| Cola | Dueño único | Caja que **no** consume |
| --- | --- | --- |
| `conversacion` | `eki-prod-final` (`fast@`) | `eki-ai-workers` (ya `sleep infinity` en `run_worker.sh`) |
| `masivo` | `eki-prod-final` (`fast@`) | Igual; W3 separará proceso si hace falta |
| `celery` | `eki-prod-final` (`fast@` + beat) | IA sin beat |
| **`media_encode`** | **`eki-ai-workers` (`media@`)** | **`eki-prod-final` deja de escucharla** |
| **`rag_index`** | **`eki-ai-workers` (`rag@`)** | **`eki-prod-final` deja de indexar** |
| `course_engine` | `eki-ai-workers` (`ce@`) | ya solo IA |
| `llm` / `certificados` | `eki-prod-final` (`fast@`) hasta I1 operativo | — |
| `audio` | sin consumidor (deuda P3) | — |

Meta sigue siendo el canal de producto. Twilio queda como hook (código de *aula*). No se abre segundo worker de conversación.

## Estado live (prod + código en `origin/main`, 2026-11-23)

| Flag / hecho | Estado |
| --- | --- |
| `EKI_MEDIA_ENCODE_SOLO_AI=true` en `eki-prod-final` | **Activo** — `run_worker.sh` sin `media_encode` en prod |
| `EKI_RAG_INDEX_SOLO_AI` | **unset** en EB (setenv chocó con tope 4096). **Código en main** respeta el flag (`run_worker_rag.sh`). Prod no indexa vía `EKI_ROLE=web`; IA consume con `rag@` |
| Redis / broker ElastiCache | **Activo** (ver `docs/OPS_REDIS_URL_EB.md`) |
| `EKI_OUTBOX_ENVIO=true` | **Activo** en prod (muestreo pre-gate: 88 `ENVIADO`, 0 `INCIERTO`) |
| Cero `time.sleep(` en `core/conversacion`, `core/lineas`, `core/avisos` | **VERDE en main** (solo comentarios) |
| `entrega_delays.dormir` / `delays_por_celery` | **VERDE** — no-op + DELAY→Celery, flag siempre on en código |

## RAG — operación opcional

El dueño único ya cumple en prod (`EKI_ROLE=web` + `rag@` en IA). Cuando EB deje hueco en setenv:

- `eb setenv EKI_RAG_INDEX_SOLO_AI=true -e eki-prod-final` — prod duerme `rag@` explícito; IA sigue con `Procfile.ai` `worker_rag`.

Apagar encode/RAG: `false` en prod-final. No hace falta setenv en `eki-ai-workers` para estos dos.

## Gate W1

| Criterio | Estado |
| --- | --- |
| Cero `time.sleep` en conversación/líneas/avisos | **VERDE** — `origin/main` + prod tras gate 2026-11-19 |
| Redis sin caer a `127.0.0.1` en prod | **VERDE** — ops OK (broker ElastiCache + fail-closed setenv) |
| Dueño único encode | **VERDE** — ops OK (`EKI_MEDIA_ENCODE_SOLO_AI=true`) |
| Dueño único RAG | **VERDE** — ops por `EKI_ROLE=web` + `rag@` en IA; setenv del flag opcional |
| Concurrencia conversación = 1 | **VERDE** — sin cambio |

## Fuera de este corte

- Campañas v2.
- W3 (cerrado: no crecer — `docs/INFORME_W3_DECISION.md`).
- W2 pico laborable (ops; no bloquea cierre de código del bloque 2).