---
name: eki-ship
description: >-
  Shipping and launch for eki_mvp on Elastic Beanstalk. Pre-launch gates,
  staged rollout, rollback. Use when deploying to eki-prod-final.
---

# eki Ship

Deploy con evidencia — Faster is Safer **con** gates, no sin ellos.

## Cuándo usar

- `eb deploy eki-prod-final`
- Post-fix P0 (Builder, WA, Nat/Celery)
- Rollback tras regresión

## Pre-launch checklist

| # | Gate | Comando / acción |
|---|------|------------------|
| 1 | Precheck | `.\scripts\eb_precheck_main.ps1` (incluye `node --check module_builder.js`) |
| 2 | Tests scope | `python manage.py test <suites del diff>` |
| 3 | QA_PASS | `@eki-qa` veredicto (P0 Builder si aplica) |
| 4 | Sec | `@eki-sec` si webhooks/auth/uploads |
| 5 | Label | `builder-*` / `main-*` descriptivo |
| 6 | Rollback anotado | `eb status` → versión anterior |

## Deploy

```powershell
.\scripts\eb_deploy_main.ps1
# o con label explícito:
eb deploy eki-prod-final --label builder-calendario-v21-YYYYMMDD-HHMMSS
```

## Post-deploy

1. `eb health eki-prod-final` → Green
2. `curl /health/` → 200
3. `python scripts/smoke_nat_celery.py --remote eki-prod-final`
4. Manual P0 Builder si diff JS/HTML (`@eki-browser-qa`)
5. Smoke WA solo con autorización explícita

## Rollback

```powershell
eb deploy eki-prod-final --version <previous_version_label>
```

Anotar siempre label anterior antes de deploy.

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Health 200 alcanza» | Builder P0 no se ve en /health/ — manual o browser QA. |
| «Precheck solo warn dirty tree» | OK para deploy urgente; anotar deuda commit. |
| «JS parse no importa si pytest verde» | Bug histórico v22: syntax error mataba todo el Builder. Gate obligatorio. |
| «Rollback después si falla» | Sin label previo anotado, rollback es adivinar. |

## Verificación (no negociable)

- Label desplegado + health 200 + smokes del scope.
- Si Builder: browser P0 cerrado o `QA_PASS condicionado` con plazo.

## Cómo invocarlo

`@eki-ship` o “despliega con checklist”.
