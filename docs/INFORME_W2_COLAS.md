# Informe W2 — medir antes de crecer

Fecha: 2026-11-19. Código en `slice/bloque-2-gate`; primera muestra live por SSH a `eki-prod-final`.

Fuente: `docs/PLAN_WORKERS_EKI.md` corte W2. Antecedentes: W0, W1.

## Cómo medir

En una caja con el mismo broker que prod (o SSH a `eki-prod-final`):

```text
python manage.py medir_colas_w2 --json --settings=mvp_project.settings_production
```

(Tras desplegar bloque 2.) Mientras tanto, LLEN vía Redis desde la caja web.

También saldrá en `health_deep` → `colas.por_cola` / `colas.mas_viejo_seg` (staff o token infra).

Colas objetivo: `conversacion`, `masivo`, `media_encode`.

## Tabla

| Cola | Profundidad (LLEN) | Edad más viejo (s) | Fuente | Nota |
| --- | --- | --- | --- | --- |
| `conversacion` | 0 | 0 | SSH Redis 2026-11-19 ~13:15 Bogotá | vacía |
| `masivo` | 0 | 0 | idem | vacía |
| `media_encode` | 0 | 0 | idem | vacía |

Extras (mismo instante): `celery`/`llm`/`certificados`/`rag_index` también LLEN 0.

Outbox (Django en la caja): `INCIERTO=0`, `ENVIANDO=0`, `ENVIADO=88`, `ERROR=0`.

Comparar con W0 (solo «hay_pendientes» anotado). Acuerdo: un segundo worker de `conversacion` **solo** si la edad medida no cabe; no se inventa el umbral aquí.

## Gate W2

| Criterio | Estado |
| --- | --- |
| Lectura de las tres colas con edad | Código OK en rama; live vía Redis OK |
| Tabla de un día laborable | **Muestra 1** (19 nov ~13:15, vacías). **Muestra 2** (19 nov ~23:16 noche, no pico, LLEN 0). **Muestra 3** (20 nov ~11:00 Bogotá, mañana laborable, LLEN 0 en `conversacion`/`masivo`/`media_encode`/`celery`/`llm`/`certificados`/`rag_index`, rol `web`). Día laborable sí; carga de cola no. **Muestra 4** (21 nov tarde Bogotá, día laborable **no pico**: `conversacion`/`masivo`/`media_encode` LLEN 0; extras en 0; rol `web`). Sin profundidad &gt;0 no autoriza separar `masivo` |
| Sin abrir W3 | Hasta pico + dueño RAG (W1) |

## Fuera

- Prefork concurrencia 2 (W3).
- Segundo entorno de conversación.
