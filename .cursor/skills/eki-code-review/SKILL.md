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

## Mantenibilidad: umbrales (Blocker si se rompen)

Canon: `docs/PLAN_MODULARIDAD_EKI.md` §3. `python scripts/ratchet_complejidad.py` debe salir en 0.

- Función nueva de más de 150 líneas, o función existente que crece.
- `except Exception` nuevo sin `logger.exception` y motivo.
- `es_modo_twilio()` / `es_solo_cursos()` nuevo fuera de `core/lineas/`: va como capacidad del perfil.
- Marcador de texto nuevo (`[MULTI_MSG]`, `[MEDIA:]`, `[DELAY:]`…) o `enviar_*` nuevo fuera del Sender.
- Reemplazar atributos de módulos en runtime (`modulo.Clase = Otra`).
- Lógica nueva dentro de `_procesar_twilio_webhook_cuerpo`, `dispatch_sandbox_menu` o `get_response_for_intent`.
- `core` importando `portal`, `aprende`, `studio` o `formulario`; modelos importando servicios.
- Movimiento y cambio de comportamiento en el mismo commit.
- Cambio de conversación sin los contratos de la línea principal y de la línea 2 en verde.

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
