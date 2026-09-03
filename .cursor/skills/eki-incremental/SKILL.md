---
name: eki-incremental
description: >-
  Incremental implementation for eki_mvp. Thin vertical slices, safe defaults,
  rollback-friendly diffs. Use when changes touch multiple files (Builder, WA).
---

# eki Incremental

Un slice vertical a la vez — implementar, testear, verificar, siguiente slice.

## Cuándo usar

- Module Builder (JS + view + template + tests).
- Pipeline media WA (upload → encode → smoke).
- Cualquier diff >3 archivos relacionados.

## Proceso

1. **Slice mínimo** — Un comportamiento observable (ej. solo guardar calendario ajax).
2. **Test del slice** — pytest o contrato antes del siguiente slice.
3. **Deploy opcional** — Solo si PM autoriza; preferir label descriptivo.
4. **Siguiente slice** — No mezclar drip + reorder + upload en un solo commit caótico.

## Defaults seguros eki

- Subidas Builder: `include_modulo_titulo=False` (no pisar nombres).
- Feature flags: `EKI_MODULE_BUILDER_BETA`, settings existentes.
- Static cache bust: bump `?v=` en template al cambiar JS/CSS.

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Lo hago todo junto y probamos» | Bugs mezclados son imposibles de localizar (drip histórico). |
| «Refactor grande primero» | Comportamiento primero; refactor con tests verdes. |
| «Deploy al final del sprint» | Slices P0 pueden shipear solos con gates. |

## Verificación (no negociable)

- Cada slice tiene test o checklist P0 propio.
- Diff revisable (~100–300 líneas útiles por PR ideal).

## Cómo invocarlo

`@eki-incremental` o “parte esto en slices verticales”.
