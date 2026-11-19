# Ops — REDIS_URL externo en Elastic Beanstalk

Antes de desplegar código con fail-closed Redis por default, o de abrir el padrón de 5.000.

**No ejecutar setenv desde aquí** salvo pedido explícito.

## Estado live (2026-11-19, lectura `eb printenv` + SSH)

| Variable | `eki-prod-final` | `eki-ai-workers` |
| --- | --- | --- |
| `CELERY_BROKER_URL` | `redis://eki-celery-prod…:6379/0` | igual |
| `CELERY_RESULT_BACKEND` | mismo host `/0` | igual |
| `REDIS_CACHE_URL` | mismo host `/1` | igual |
| `REDIS_URL` | unset (no hace falta: broker cubre) | unset |
| `EKI_REDIS_FAIL_CLOSED` | `true` | unset (código desplegado aún default false; setenv en prod-final ya cierra) |
| `USE_LOCAL_REDIS` | `0` | `0` |

Web y workers ven el **mismo** ElastiCache. Checklist Redis externo: **cumplido** en prod.

## Por qué sigue el doc

Con `EKI_REDIS_FAIL_CLOSED=true` (setenv o default de `slice/bloque-2-gate`), sin broker externo el proceso **no arranca**. Tras desplegar bloque 2, conviene setenv también en `eki-ai-workers` o depender del default del código.

## Checklist (referencia)

1. ElastiCache en la VPC de EB; `noeviction` en el broker.
2. Caché/locks en otra base lógica (`REDIS_CACHE_URL` `/1` — ya en prod).
3. Misma URL de broker en **ambos** entornos.
4. Verificar: `eb status` Green, `/health/` 200, Django no habla con `127.0.0.1`.
5. Rollback de emergencia: `EKI_REDIS_FAIL_CLOSED=false`.

## Orden con W1

1. ~~`REDIS_URL` / broker externo~~ → **hecho** (`CELERY_BROKER_URL`).
2. ~~`EKI_MEDIA_ENCODE_SOLO_AI=true`~~ → **hecho** en `eki-prod-final`.
3. `EKI_RAG_INDEX_SOLO_AI=true` → **falta** desplegar `slice/bloque-2-gate` (el flag no existe en `origin/main`) y luego setenv en `eki-prod-final`.
4. W2 medir colas (muestra 1 ya en `docs/INFORME_W2_COLAS.md`).
