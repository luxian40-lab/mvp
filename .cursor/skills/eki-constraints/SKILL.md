---
name: eki-constraints
description: >-
  Constraint-driven quality bar for eki_mvp. Defines observable gates before
  deploy; agents cannot silence checks to get green. Use with PM/QA before
  shipping Builder, webhooks, or media changes.
---

# eki Constraints

Define la barra de calidad **antes** de implementar. PM escribe; Dev/QA ejecutan; nadie baja el listón para quedar verde.

## Cuándo usar

- Feature o fix que toca estudiantes en prod (WA, drip, certificados).
- Deploy Module Builder, webhooks Twilio, S3 media.
- Cuando un agente «pasa tests» pero el usuario reporta bug en UI.

## Proceso

1. **Listar constraints** observables (comando, URL, smoke, screenshot).
2. **Clasificar por costo**: barato (pytest) → medio (smoke script) → caro (manual browser prod).
3. **Ordenar gates**: todos los baratos verdes antes del deploy; caros post-deploy con plazo.
4. **Documentar** en CA del PM o `docs/MODULE_BUILDER_QA_S4_CHECKLIST.md` si aplica.
5. **QA_FAIL** si falta un gate P0, aunque el resto esté verde.

## Constraints estándar eki (plantilla)

```markdown
## P0 (bloquea deploy)
- [ ] pytest: <suite> OK
- [ ] manage.py check --deploy OK
- [ ] Sec: sin Critical/High (si webhooks/auth)

## P1 (post-deploy <24h)
- [ ] /health/ 200
- [ ] Manual Builder P0 (si diff JS/HTML Builder)

## P2 (seguimiento)
- [ ] Smoke WA autorizado (si media)
```

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Solo warnings en precheck» | Warnings de dirty tree / branch ≠ PASS de constraints P0. |
| «Deploy urgente, probamos en prod» | P0 existe por bugs históricos (drip). No negociable. |
| «El checklist manual es opcional» | En Builder, manual P0 **es** constraint P0. |
| «Quito el test que falla» | Violación. Arreglar código o actualizar spec con PM. |

## Verificación (no negociable)

- Tabla constraints con estado ✅/❌ y evidencia (comando + salida resumida).
- Sin filas P0 en ❌ → PM puede autorizar deploy.
- Cualquier P0 manual pendiente → veredicto `QA_PASS condicionado` o `QA_FAIL`.

## Cómo invocarlo

`@eki-constraints` o “define gates antes de deploy”.
