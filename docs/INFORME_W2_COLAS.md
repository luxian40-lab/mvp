# Informe W2 — medir antes de crecer

Fecha: 2026-11-19. **Código listo**; cifras de un día laborable en prod = ops (sin setenv de flags de encode/outbox).

Fuente: `docs/PLAN_WORKERS_EKI.md` corte W2. Antecedentes: W0, W1.

## Cómo medir

En una caja con el mismo `REDIS_URL` / broker que prod (o SSH a `eki-prod-final`):

```text
python manage.py medir_colas_w2 --json --settings=mvp_project.settings_production
```

También sale en `health_deep` → `colas.por_cola` / `colas.mas_viejo_seg` (staff o token infra).

Colas: `conversacion`, `masivo`, `media_encode`.

## Tabla (rellenar en un día laborable)

| Cola | Profundidad (LLEN) | Edad más viejo (s) | Fuente | Nota |
| --- | --- | --- | --- | --- |
| `conversacion` | _pendiente live_ | _pendiente live_ | | |
| `masivo` | _pendiente live_ | _pendiente live_ | | |
| `media_encode` | _pendiente live_ | _pendiente live_ | | |

Comparar con W0 (solo LLEN / «hay_pendientes»). Acuerdo: un segundo worker de `conversacion` **solo** si la edad medida no cabe; no se inventa el umbral aquí.

## Gate W2

| Criterio | Estado |
| --- | --- |
| Lectura de las tres colas con edad | Código OK (`core/analitica/colas_w2.py`, comando `medir_colas_w2`) |
| Tabla de un día laborable | **Pendiente ops** (pegar JSON aquí) |
| Sin abrir W3 | Hasta tabla + W1 setenv si aplica |

## Fuera

- Prefork concurrencia 2 (W3).
- Prender `EKI_OUTBOX_ENVIO` / campañas v2.
- Segundo entorno de conversación.
