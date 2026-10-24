---
name: eki-refactor-motor
description: >-
  Refactor y modularidad de eki_mvp: partir _procesar_twilio_webhook_cuerpo y
  get_response_for_intent, separar línea (puertas, menú, perfil) de motor de
  curso, ordenar core por dominios y agregar funciones sin romper la línea
  principal ni la línea 2. Use when the user asks for refactor, espagueti,
  modularidad, partir el cuerpo, motor de curso, Turno, PerfilLinea, nueva
  línea de WhatsApp, o cualquier fase de docs/PLAN_MODULARIDAD_EKI.md.
---

# eki Refactor del motor

Plan canon: `docs/PLAN_MODULARIDAD_EKI.md`. Mapa del cuerpo, líneas y orden: [reference.md](reference.md).

## Antes de tocar código

1. Leer la fase del plan y `docs/REFACTOR_VIEWS.md` (reglas de movimiento y `patch()`).
2. Ubicar el cambio en el modelo de dos líneas (reference.md §1). Si afecta a una sola línea, es una capacidad del perfil, no un `if`.
3. Mostrar el plan de archivos. Esperar visto bueno si el bloque toca el cuerpo.
4. `.cursor/refactor_motor.json` dice qué estados del cuerpo están autorizados. Si `cuerpo_autorizado` es `false`, el cuerpo no se toca: solo se envuelve desde afuera.

## Extraer un estado del cuerpo (fase D)

```
- [ ] Test de caracterización del estado en verde ANTES de mover (fase A)
- [ ] python scripts/variables_libres_rama.py <estado>  -> lista de entradas (el script nace en D1)
- [ ] Mover la rama a core/conversacion/estados/<estado>.py como manejar(ctx) -> str | None
- [ ] El cuerpo llama al handler en el mismo punto; mismo orden, mismos returns
- [ ] Commit solo con el movimiento
- [ ] ruff check --select F821 core/ ; manage.py check ; caracterización ; contratos de línea
- [ ] python scripts/ratchet_complejidad.py --actualizar --aceptar-movimiento
- [ ] Informe de gate (formato en el plan §4)
```

`--aceptar-movimiento` solo acepta funciones grandes nuevas si el total de líneas en funciones grandes no sube. Si sube, el movimiento duplicó código: revisar.

## Reglas que no se negocian

- Mover y cambiar comportamiento van en commits distintos.
- Ningún `es_modo_twilio()` / `es_solo_cursos()` nuevo. Capacidad del perfil, apagada por defecto.
- Función nueva: puerta, handler de estado o agente. Nunca dentro del cuerpo, `dispatch_sandbox_menu` ni `get_response_for_intent`.
- Nada de marcadores de texto nuevos ni `enviar_*` nuevos fuera del Sender. Nada de reemplazar atributos de módulos en runtime.
- Ninguna función nueva de más de 150 líneas.
- El motor de curso no importa menú ni asesores. `core` no importa `portal`, `aprende`, `studio`, `formulario`.
- Contratos de la línea principal y de la línea 2 verdes en cada commit.
- `patch()` apunta al módulo donde el caller busca el nombre. Al mover una función parcheada, avisar y actualizar el target.
- No bajar el listón: si el freno o un contrato falla, se arregla el código, no el baseline ni el test.

## Freno de complejidad

```
python scripts/ratchet_complejidad.py                 # compara contra el baseline
python scripts/ratchet_complejidad.py --archivo RUTA  # solo un archivo
python scripts/ratchet_complejidad.py --actualizar    # baja el baseline; nunca lo sube
```

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «Muevo y de paso limpio» | Dos commits. Un bug mezclado con un movimiento no se localiza. |
| «Es solo para la línea 2, un if y listo» | Capacidad del perfil. El `if` número 15 es el que rompe la principal. |
| «El estado nunca se usa, lo borro» | Primero el conteo en producción (fase A). Después commit aparte. |
| «Subo el baseline, es un caso especial» | El baseline solo baja. Partir la función. |
| «La caracterización la hago después» | Sin red no se mueve. |

## Salida

Informe de gate del plan §4, con la salida del freno y de los contratos de línea.
