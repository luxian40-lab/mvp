# Informe W3 — no crecer

Fecha: 2026-11-19, noche (Bogotá). Corte W3 de `docs/PLAN_WORKERS_EKI.md`.

## Decisión

No se sube concurrencia ni se separa `masivo`. No hay segundo worker de `conversacion`.

| Hecho | Evidencia |
| --- | --- |
| Concurrencia ya es 2 | `CELERY_CONCURRENCY=2` en `eki-prod-final` (prefork `fast@`) |
| Colas en esta lectura | `conversacion` / `masivo` / `media_encode` LLEN 0 (no es pico) |
| Encode | Solo AI (`EKI_MEDIA_ENCODE_SOLO_AI=true`; `fast@` sin `media_encode`) |
| RAG | Prod no indexa: `EKI_ROLE=web` hace `sleep infinity` en `run_worker_rag.sh`. AI tiene `rag@` |
| Outbox | Sigue el claim del bloque 2 |

## RAG setenv

`eb setenv EKI_RAG_INDEX_SOLO_AI=true` **falló** (CloudFormation: `EnvironmentVariables` > 4096). El flag queda unset. El dueño único ya lo da el rol `web`, no hace falta reintentar el setenv hasta liberar variables.

## Qué no se abre

- Concurrencia 3.
- Proceso aparte de `masivo` (hace falta un pico donde la campaña empuje la edad).
- Alarma `CPUCreditBalance` y cambio de tipo de instancia.
- Ciclo de imports &lt; 30 (bloque 6, después del padrón).
