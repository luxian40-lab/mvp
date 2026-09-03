---
name: eki-code-review
description: >-
  Code review for eki_mvp before merge. Five-axis review, change sizing,
  severity labels. Use before merging Builder, webhooks, or media changes.
---

# eki Code Review

Revisión pre-merge — mejorar salud del código, no nitpicking sin impacto.

## Cuándo usar

- PR o diff grande en `core/`, `static/admin/`, webhooks.
- Antes de deploy sin PR formal (revisión del diff en chat).

## Cinco ejes

| Eje | Pregunta |
|-----|----------|
| Correctness | ¿Hace lo que dice el CA? ¿Tests? |
| Security | ¿Auth, uploads, webhooks, PII? → `eki-sec` |
| Maintainability | ¿Sigue patrones del archivo? |
| Performance | ¿N+1, sync pesado en request? |
| UX ops | ¿Staff entiende errores y estados? |

## Tamaño

- Ideal: **~100 líneas** útiles por review.
- >500 líneas Builder → pedir split (`eki-incremental`).

## Severidad en comentarios

- **Blocker** — Debe arreglarse antes de merge/deploy.
- **Important** — Debería arreglarse; negociable con PM.
- **Nit** — Estilo; no bloquear.

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Ya pasó pytest» | Review cubre seguridad y contratos que tests no tienen. |
| «Es urgente» | Blockers de seguridad no se negocian. |
| «Lo refactorizo después» | Chesterton's Fence: entender por qué está así antes de borrar. |

## Verificación (no negociable)

- Lista de findings con severidad + archivo.
- Blockers = 0 para recomendar merge/deploy.

## Cómo invocarlo

`@eki-code-review` o “revisa este diff antes de merge”.
