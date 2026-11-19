# Ops — REDIS_URL externo en Elastic Beanstalk

Antes de desplegar `slice/bloque-2-gate` (fail-closed Redis en producción) o de abrir el padrón de 5.000.

**No ejecutar setenv desde aquí.** Pedido explícito.

## Por qué

Con `EKI_REDIS_FAIL_CLOSED` default **true** en `settings_production`, sin `REDIS_URL` / `CELERY_BROKER_URL` externo el proceso **no arranca**. Web y workers deben ver el **mismo** broker.

## Checklist (manual)

1. ElastiCache (o Redis gestionado) en la VPC de EB; `noeviction` en el broker.
2. Caché/locks en otra base lógica (`REDIS_CACHE_URL` o broker con `/1` — ya se deriva en settings).
3. En **ambos** entornos, misma URL:
   - `eki-prod-final`
   - `eki-ai-workers`
4. Variables (ejemplo):
   - `REDIS_URL=rediss://…` o `redis://…` (no `127.0.0.1` / `localhost`)
   - opcional `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` / `REDIS_CACHE_URL`
5. Verificar tras setenv/deploy:
   - `eb status` Green
   - `/health/` 200
   - Django lee broker externo (no local)
   - beat único en `eki-prod-final`; IA sin beat
6. Rollback de emergencia: `EKI_REDIS_FAIL_CLOSED=false` (vuelve el plan B local; no es el estado deseado).

## Orden sugerido con W1

1. `REDIS_URL` en las dos cajas y smoke.
2. Luego, si pedís: `EKI_MEDIA_ENCODE_SOLO_AI=true` y `EKI_RAG_INDEX_SOLO_AI=true` solo en `eki-prod-final` (ver `docs/INFORME_W1_DUENOS.md`).
3. W2 medir colas. No prender `EKI_OUTBOX_ENVIO` ni campañas v2 en este paso.
