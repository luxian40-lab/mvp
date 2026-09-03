---
name: eki-debug
description: >-
  Debugging and error recovery for eki_mvp. Reproduce, localize, reduce,
  fix, guard. Use when tests fail, prod bugs, or Builder save errors.
---

# eki Debug

Triage estructurado — stop-the-line en P0 prod.

## Cuándo usar

- «Guardar no funciona» en Builder.
- Twilio 63019/63021/63005.
- Celery encola pero no ejecuta.
- Deploy verde pero feature rota.

## Proceso (5 pasos)

1. **Reproduce** — Mismo entorno (prod/staging/local), mismos pasos, mismo módulo/curso.
2. **Localize** — Capa: JS (hidden/fetch) · vista Django · `module_builder_config` · DB.
3. **Reduce** — Quitar variables: solo calendario, sin upload; POST directo vs browser.
4. **Fix** — Diff mínimo + test de regresión (`@eki-tdd`).
5. **Guard** — Test + checklist P0 + doc si patrón recurrente.

## Árbol rápido Builder «no guarda drip»

```
¿Alerta JS «No se pudo guardar»?
  sí → v21: fetch devolvió HTML (sesión/500). v22+: POST clásico — revisar mensaje Django arriba.
  no → ¿Banner verde «Drip guardado» tras recarga?
    no → hidden vacío al guardar → readCalendarioPostValue / fecha sin input
    sí → ¿Drip por empresa activo? (sustituye calendario global para ese cliente)
```

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Probablemente es cache» | Ctrl+F5 primero; si persiste, localize con Network. |
| «Arreglo y vemos» | Sin reproduce documentado, el fix puede ser wrong layer. |
| «Solo pasa en prod» | Comparar static `?v=`, EB version label, datos del módulo. |

## Verificación (no negociable)

- Causa raíz en una frase (capa + archivo).
- Test o paso manual que fallaba antes y pasa después.
- Rollback label si el fix va en deploy.

## Cómo invocarlo

`@eki-debug` o “reproduce y localiza este bug”.
