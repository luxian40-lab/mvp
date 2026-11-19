# Informe W1 — dueño de cada cola

Fecha: 2026-11-19. Decisión de producto/ops + lectura live EB.

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

Meta sigue siendo el canal de producto. Twilio queda como hook (código de *aula*). No se abre segundo worker de conversación.

## Estado live (2026-11-19)

| Flag / hecho | Estado |
| --- | --- |
| `EKI_MEDIA_ENCODE_SOLO_AI=true` en `eki-prod-final` | **Activo** |
| `EKI_RAG_INDEX_SOLO_AI` | **unset**; el script en `origin/main` **aún no** respeta el flag (llega con `slice/bloque-2-gate`) |
| Redis / broker ElastiCache | **Activo** (ver `docs/OPS_REDIS_URL_EB.md`) |
| `EKI_OUTBOX_ENVIO=true` | **Activo** en prod (88 `ENVIADO`, 0 `INCIERTO` al muestrear) |

## Cómo cerrar RAG (pedido explícito)

1. Desplegar `slice/bloque-2-gate` (trae `run_worker_rag.sh` + setting).
2. `eb setenv EKI_RAG_INDEX_SOLO_AI=true -e eki-prod-final`  
   → prod duerme el `rag@`; IA sigue con `Procfile.ai` `worker_rag`.

Apagar encode/RAG: `false` en prod-final. No hace falta setenv en `eki-ai-workers` para estos dos.

## Gate W1

| Criterio | Estado |
| --- | --- |
| Cero `time.sleep` en conversación/líneas/avisos | Código en `slice/bloque-2-gate` (falta deploy) |
| Redis sin caer a `127.0.0.1` en prod | **Ops OK** (broker ElastiCache + fail-closed setenv) |
| Dueño único encode | **Ops OK** (`EKI_MEDIA_ENCODE_SOLO_AI=true`) |
| Dueño único RAG | **Pendiente** deploy bloque 2 + setenv |
| Concurrencia conversación = 1 | Sin cambio |

## Fuera de este corte

- Campañas v2.
- W3.
- Push/deploy (pedido aparte).
