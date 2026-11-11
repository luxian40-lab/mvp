# Plan maestro — tronco de eki

Canon corto del bloque 0. El detalle de cada bloque sigue en los planes de abajo y no se copia aquí.

| Plan | Qué manda |
| --- | --- |
| `docs/PLAN_MODULARIDAD_EKI.md` | Refactor B–H1 hecho. Origin hoy: ciclo **211** (H2). No portar H1. No se trabaja el ciclo para abrir el padrón. |
| `docs/PLAN_ESCALABILIDAD_EKI.md` | P0–P8: CI, idempotencia, Redis, campañas, tope de LLM, tenancy, índices |
| `docs/PLAN_WORKERS_EKI.md` | Quién consume cada cola en las dos cajas. Va con el bloque 2, no abre otra flota. |
| `docs/PLAN_CONSTRUCTOR_CURSOS_EKI.md` | Constructor oficial, después de que el webhook esté ordenado |
| `docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md` | Qué significa “completó el curso”. Corte paralelo al bloque 2. No abre el padrón. Camino a 8: bloque A. |

Orden de salida: tronco y checklist corto, **bandeja**, **outbox** junto con el mapa de workers (`docs/PLAN_WORKERS_EKI.md`), versiones de cohorte, constructor, ciclo bajo 30 (después del padrón), campañas y conservación, contrato del IQ Rural. H1 ya está en producción (28 oct). Un bloque a la vez. `core` sigue siendo la única app de dominio. El expediente de aprendizaje se puede cortar **en paralelo**: un commit no mezcla diploma con outbox ni con sleeps.

## Cifra de ciclo (8 de noviembre de 2026)

`scripts/complejidad_baseline.json` en `origin/main`: **211**. H1 bajó 233→159 el 28 de octubre y sacó los modelos del ciclo. H2 (30 oct) subió el titular a 211 con reexports. **No se porta** `refactor/h1-imports-modelos`. **No se trabaja el ciclo ahora.** El padrón de 5.000 espera los bloques 1 y 2, no un número más chico.

## Reconciliación (8 de noviembre de 2026)

| Ref | Commit | Qué hacer |
| --- | --- | --- |
| `origin/main` | `5b992fde` | Tronco. Línea 3: Ver curso abre la clase. Ciclo 211. |
| `main` local | `3bf5393f` | Ocho commits E4–G6 que no están en origin. No es tronco. No se fusiona mientras Alitic y Lhaura vet escriben. |
| Producción | ver `docs/CONTINUAR_EKI.md` | Último anotado: `6bd02cd4` / `main-entrada-asesoria-20261029-220849`. Origin tiene más (línea 3, video, certificado). Confirmar `eb status` antes de desplegar. |
| `integrar/e4-g6-origin` | `97cc7c03` | Cherry-picks E4–G6 sobre origin. Flags apagados. No desplegar. |
| `slice/bloque-1-bandeja` | sucia | No commitear encima. Bandeja sale de `origin/main` en árbol limpio. |
| `refactor/h1-imports-modelos` | `bcdb9d58` | No fusionar. H1 ya está en origin. El bloque 3 no se reabre. |
| `feat/module-builder-nativo` | `c745244d` | No fusionar. El constructor nuevo reutiliza lecciones, no esa rama. |
| `slice/escalabilidad-base` | atrás de producción | No se despliega. |

## Suite

El pull request corre solo el checklist de `.github/workflows/ci.yml`. Ese pytest tiene tope de 8 minutos. Entran los contratos cortos de presupuesto LLM, antiflood, campañas Meta v2, tenancy y el contrato del Builder. La UI del Builder (65 tests) y Playwright se quedan fuera.

`pytest .` vive en `.github/workflows/ci-suite-nocturna.yml`: 01:00 Bogotá, y a mano con `workflow_dispatch`. Falla si aparece un fallo que no está en `scripts/baseline_failures_before.txt`. No frena el merge.

## Deploy

`.cursor/hooks/antes_de_deploy.py` niega `eb deploy` si la carpeta está sucia, si la rama es `slice/escalabilidad-base`, o si `HEAD` no es ancestro de `origin/main`.
