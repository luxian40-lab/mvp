---
name: eki-observability
description: >-
  Observability for eki_mvp. Structured logging, health, post-deploy signals.
  Use when shipping features that fail silently or need on-call visibility.
---

# eki Observability

Instrumentar para responder «¿qué pasó?» sin adivinar.

## Cuándo usar

- Saves ajax que fallan silenciosos.
- Celery/Nat colas.
- Deploy nuevo — confirmar que tráfico sano.

## Señales eki

| Señal | Dónde |
|-------|--------|
| Liveness | `GET /health/` |
| Request done | `core.middleware` logs |
| EB | `eb health`, `eb logs` |
| Celery | `scripts/smoke_nat_celery.py --remote` |
| Twilio | Message SID, error codes 63xxx |

## Logging útil (sin PII)

- `action=save_modulo`, `modulo_id`, `ajax=1`, `ok=true/false`
- No loguear teléfonos completos ni tokens en prod.

## Pre-launch gate

- [ ] `/health/` 200 post-deploy
- [ ] Sin spike 5xx en EB logs (muestra 5 min)
- [ ] Si async: Celery ping remoto OK

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «El usuario no reportó nada» | Fallos silenciosos (ajax) no generan ticket. |
| «Logs después» | Un `logger.warning` en save fallido cuesta 1 línea. |
| «Solo local» | Mismo patrón en prod evita ciegos post-deploy. |

## Verificación (no negociable)

- Saber qué mirar si el usuario dice «no guardó» (Network + logs EB + versión label).

## Cómo invocarlo

`@eki-observability` o “qué logs mirar post-deploy”.
