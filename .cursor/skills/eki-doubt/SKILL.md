---
name: eki-doubt
description: >-
  Doubt-driven review for high-stakes eki_mvp changes. Adversarial
  CLAIM→DOUBT→RECONCILE on prod, security, irreversible ops. Use for P0
  bugs and unfamiliar code paths.
---

# eki Doubt

Revisión adversarial cuando el costo de estar equivocado es alto.

## Cuándo usar

- Bug P0 prod (drip, WA roto, PII).
- Webhook / auth / certificados.
- Código desconocido con fix confiado del agente.
- Antes de deploy sin QA manual completo.

## Proceso

1. **CLAIM** — «El fix resuelve X porque Y».
2. **EXTRACT** — Supuestos explícitos (ej. «JS siempre sync hidden antes de fetch»).
3. **DOUBT** — ¿Qué evidencia contradice cada supuesto?
4. **RECONCILE** — Test, manual, o spike que confirma o refuta.
5. **STOP** — Si duda persiste en P0 → no deploy.

## Preguntas duda estándar (Builder)

- ¿El test falla si quito el fix?
- ¿Probé en browser, no solo `Client().post`?
- ¿Upload/reorder puede pisar General por otro code path?
- ¿Timezone convierte mal `habilitado_desde`?

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Confío en el agente» | El bug drip pasó con tests verdes — duda obligatoria. |
| «No hay tiempo para dudar» | Debug en prod cuesta más que 10 min de reconcile. |
| «Es obvio» | Obvio ≠ probado. |

## Verificación (no negociable)

- Cada CLAIM P0 tiene evidencia enlazada (test name, paso manual).
- Supuestos sin evidencia → deploy bloqueado o condicionado.

## Cómo invocarlo

`@eki-doubt` o “cuestiona este fix antes de ship”.
