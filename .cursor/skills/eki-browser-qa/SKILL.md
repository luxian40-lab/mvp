---
name: eki-browser-qa
description: >-
  Browser verification for eki_mvp admin (Module Builder). DevTools-style
  checks on DOM, network fetch, hidden fields. Use post-deploy when JS/HTML
  changed or drip/calendario gates apply.
---

# eki Browser QA

Verificación en browser del admin — complementa pytest, no lo reemplaza.

## Cuándo usar

- Post-deploy de Module Builder (`module_builder.js`, template, CSS).
- Bug reportado «guardé pero no persistió» (drip, calendario, nombres).
- Cualquier `fetch` ajax del Builder.

## Proceso (Module Builder P0)

1. **Hard refresh** — Ctrl+F5 (cache bust `?v=` en static).
2. **Calendario** — Elegir fecha + hora → Guardar.
3. **Network** — POST `save_modulo`; body incluye `modulo_habilitado_desde` con valor ISO (`YYYY-MM-DDTHH:MM`).
4. **Response** — redirect 302 o 200; mensaje Django «Drip guardado: …» si aplica.
5. **Reload** — Ctrl+F5; misma fecha/hora visible en inputs.
6. **Limpiar** — Botón Limpiar → Guardar → recarga sin fecha.
7. **Regresión** — Subir PDF sin tocar General → drip y publicado WA intactos.

## Qué inspeccionar (DevTools)

| Pestaña | Buscar |
|---------|--------|
| Network | POST save_modulo, status 200/302, `modulo_habilitado_desde` en payload |
| Payload | `modulo_habilitado_desde`, `action=save_modulo` |
| Console | Sin errores JS (syntax error = P0 FAIL) |
| Elements | `#eki-mb-habilitado` (hidden) sincronizado con date/time inputs |

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «El test ajax pasó» | El bug fue hidden vacío en browser real — inspeccionar Network. |
| «No tengo DevTools» | Mínimo: Guardar → Ctrl+F5 → ¿misma fecha? Sin eso no hay PASS. |
| «Staging no tiene el módulo» | Usar módulo piloto Impulso o módulo de prueba staff. |

## Verificación (no negociable)

Evidencia en veredicto QA:

- URL del módulo probado (`/admin/module-builder/<id>/`).
- Fecha/hora probada y resultado tras recarga.
- Si falló: screenshot o copia de payload/response (sin PII).

## Cómo invocarlo

`@eki-browser-qa` o “verifica Builder en browser post-deploy”.
