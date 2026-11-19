# Expediente — listo para merge (flags off)

Fecha: 2026-11-19. Rama: `feat/expediente-b4-residual` (6 commits sobre `origin/main` @ `18858ca1`).

**No mezclar** con `slice/bloque-2-gate` (outbox / sleeps / Redis / W1) en el mismo paquete de deploy.

## Commits

1. Expediente corte 1 — baseline tests  
2. Corte 2 — un escritor de progreso completado  
3. Corte 3 — diploma por reglas (`EKI_DIPLOMA_LEE_REGLAS` off)  
4. Corte 4 — `origen_cierre` + migración 0209  
5. Corte 5 — nota vacía sin preguntas (`EKI_DIPLOMA_NOTA_VACIA_SIN_PREGUNTAS` off) + 0210  
6. Residual B4 — `lectura_entrega` (`EKI_CURSO_VERSIONES` off)

## Merge (cuando lo pidas)

Desde worktree limpio de `main`:

```text
git fetch origin
git checkout main
git merge --ff-only feat/expediente-b4-residual
```

Si no es fast-forward: rebasar la rama sobre `origin/main` y repetir. Migraciones 0209/0210 son expand compatibles.

## Flags

Todos **off** por default. No hace falta setenv para merge/deploy del expediente.
