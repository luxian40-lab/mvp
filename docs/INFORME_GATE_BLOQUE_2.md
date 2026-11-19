# Gate bloque 2 — 2026-11-19

Rama: `slice/bloque-2-gate` (desde `origin/main` @ `18858ca1`).  
Expediente + B4 quedó en rama aparte `feat/expediente-b4-residual` (no mezclado).

## Criterios

| Criterio | Resultado |
| --- | --- |
| W0 inventario colas | OK — `docs/INFORME_W0_COLAS.md`. `media_encode` aún puede tener dos consumidores con flag apagado (W1 dueño queda anotado, no se prende flag aquí). |
| Cero `time.sleep` en `conversacion/` / `lineas/` / `avisos/` | OK — `entrega_delays` + `activo_puerta` (reenvío) sin sleep; DELAY/avisos encolan Celery. |
| Redis sin caer a `127.0.0.1` en prod | OK en código — `EKI_REDIS_FAIL_CLOSED` default **true** en `settings_production`. **Antes de desplegar:** `REDIS_URL` externo obligatorio o el proceso no arranca. |
| Claim/outbox en camino real | OK — `enviar_respuesta_turno` → `enviar_respuesta_linea` → Sender → `OutboxEnvio.ejecutar`. Flag `EKI_OUTBOX_ENVIO` sigue apagado por defecto (filas solo con flag on). |
| Mitigación 5 (LLM si Redis cae) | OK — Nat/asesoría + tutor aula (`_get_client`), `pregunta_handler`, `completar_chat`; sin URL de broker no hay llamada de pago. |

## Commits en esta rama

1. `1da2407d` W0 inventario  
2. `b508626f` W0 nota fail-closed  
3. `5a7832e0` cero sleep / DELAY Celery  
4. `16e24b84` turno Meta por Sender  
5. `99e05156` Redis fail-closed + LLM sin URL local  

## Verificación

- `manage.py check` (settings_test): sin problemas  
- Tests área (Postgres 5433): 93 OK (`entrega_delays`, `envio_meta_marcas`, `lineas_cortes` Sender, `presupuesto_llm`, `infra_redis`, `outbox_envio`, `aviso_modulo`)  
- `makemigrations --check --dry-run`: deriva un `AlterField meta_plantilla_diploma` **preexistente** en main (no tocado por este bloque)

## No hecho / no mezclado

- Prender `EKI_OUTBOX_ENVIO` o `EKI_MEDIA_ENCODE_SOLO_AI` en producción  
- ElastiCache / setear `REDIS_URL` en EB (manual)  
- Expediente cortes 1–5 + B4 (`feat/expediente-b4-residual`)  
- Deploy / push  

## Esperar

«continúa» para el siguiente corte (W1 dueño de `media_encode`, o merge/push de estas ramas).
