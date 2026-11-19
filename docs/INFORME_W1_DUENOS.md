# Informe W1 — dueño de cada cola

Fecha: 2026-11-19. Decisión de producto/ops. **Flags apagados**; el `eb setenv` queda para pedido explícito.

Fuente: `docs/PLAN_WORKERS_EKI.md` corte W1. Antecedente: `docs/INFORME_W0_COLAS.md`.

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

Meta sigue siendo el canal de producto. Twilio queda como **hook** (código de *aula* y restos históricos). No se abre segundo worker de conversación.

## Cómo se aplica (cuando digas setenv)

Sin tocar `CELERY_QUEUES` fijo en EB:

1. `eb setenv EKI_MEDIA_ENCODE_SOLO_AI=true -e eki-prod-final`  
   → `run_worker.sh` quita `media_encode` del `-Q` default.
2. `eb setenv EKI_RAG_INDEX_SOLO_AI=true -e eki-prod-final`  
   → `run_worker_rag.sh` en prod hace `sleep infinity`; IA sigue con `Procfile.ai` `worker_rag`.

Apagar: `false` en ambos. No hace falta setenv en `eki-ai-workers` para estos dos.

**Hoy (flags off):** comportamiento actual; las dos cajas pueden seguir consumiendo encode y RAG. Esta decisión no cambia producción hasta el setenv.

## Gate W1 (código vs ops)

| Criterio | Estado |
| --- | --- |
| Cero `time.sleep` en conversación/líneas/avisos | Hecho en `slice/bloque-2-gate` |
| Redis sin caer a `127.0.0.1` en prod | Código: fail-closed default on; **falta** `REDIS_URL` en EB (ver `docs/OPS_REDIS_URL_EB.md`) |
| Dueño único encode + RAG | **Decidido** aquí; **activo** solo tras setenv |
| Concurrencia conversación = 1 | Sin cambio |

## Fuera de este corte

- Prender `EKI_OUTBOX_ENVIO` / campañas v2.
- W2 (medir edad de colas).
- Merge/deploy de expediente o bloque 2 (pedido aparte).
