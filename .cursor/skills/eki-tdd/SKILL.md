---
name: eki-tdd
description: >-
  Test-driven development for eki_mvp. Red-green-refactor, test pyramid,
  contract tests for JS↔Django. Use when implementing logic, fixing bugs,
  or touching module_builder.js / views with ajax.
---

# eki TDD

Workflow TDD adaptado a Django + admin JS (Module Builder, Twilio, media).

## Cuándo usar

- Cambio de comportamiento en backend o JS del Builder.
- Bug en prod (drip, calendario, uploads, media WA).
- Nuevo endpoint ajax o contrato POST.

## Proceso

1. **Red** — Test que falla por el bug o la feature (pytest o contrato ajax).
2. **Green** — Código mínimo que pasa.
3. **Refactor** — Sin cambiar comportamiento; tests siguen verdes.
4. **Beyoncé Rule** — Si quitas el fix, el test debe volver a fallar.

## Pirámide eki

| Capa | % | Ejemplos |
|------|---|----------|
| Unit / Django | ~80 | `core/tests_module_builder_ui.py`, `tests_twilio_*` |
| Integración | ~15 | smoke scripts, POST ajax con `Client()` |
| Manual browser | ~5 | Checklist P0 Builder post-deploy |

## Contratos JS↔backend (Module Builder)

Si tocas `module_builder.js` o inputs que alimentan POST:

- Test ajax: `ajax=1`, assert `ok`, campos clave (`habilitado_desde`, etc.).
- Si el bug es sync UI→hidden, añadir test que simule POST con el valor que **debería** enviar el JS, o test DOM si hay harness.

Legado: `core/tests_module_builder_ui.py` · `docs/MODULE_BUILDER_UI_CONTRATO.md`.
Producto nuevo: `docs/PLAN_CONSTRUCTOR_CURSOS_EKI.md`.

## Código legado: caracterización y contratos de línea

Para el cuerpo del webhook, `sandbox_menu` y `response_templates` el test no describe lo que debería pasar: fija lo que pasa hoy.

1. Estado inicial explícito: estudiante, `estado_chat`, `estado_onboarding`, `contexto_temporal`, progreso, línea (phone id).
2. Un mensaje entrante (payload Meta firmado o form Twilio).
3. Afirmar los envíos capturados en el borde (Graph y Twilio, sin red) y el estado final en la base.
4. Si el comportamiento actual parece un bug, el test lo fija igual y el bug va a otro commit.

Contratos de línea (`docs/PLAN_MODULARIDAD_EKI.md` fase A): un recorrido de punta a punta de la línea principal y otro de la línea 2. Todo cambio de conversación los corre.

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Es un fix de una línea» | Una línea sin test se repite en prod. |
| «Ya hay tests del módulo» | ¿Cubren **este** contrato? Si no, red primero. |
| «El manual lo pruebo después» | Manual no reemplaza red; complementa post-deploy. |
| «Solo toqué HTML/CSS» | Si hay `name=` o `fetch`, puede romper persistencia — test o checklist P0. |

## Verificación (no negociable)

Antes de decir «listo»:

- [ ] `python manage.py test <suite relevante>` → OK con evidencia (conteo tests).
- [ ] Si Builder: `core.tests_module_builder_ui` verde.
- [ ] Si media/Twilio: suite correspondiente verde.
- [ ] Indicar a `@eki-qa` qué smoke manual corre post-deploy.

**«Parece bien» no es evidencia.**

## Cómo invocarlo

`@eki-tdd` o “red-green en este fix”.
