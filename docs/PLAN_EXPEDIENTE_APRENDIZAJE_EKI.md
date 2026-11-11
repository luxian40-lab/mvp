# Expediente de aprendizaje — eki

Qué significa “completó el curso”. Corte paralelo al camino a 5.000. No abre el padrón. No espera al constructor. No se mezcla en el mismo commit con bandeja, outbox, sleeps ni G3.

Se trabaja un corte a la vez. Cada corte cierra con el informe de gate y espera «continúa».

Auditoría del 10 de noviembre de 2026: `ProgresoEstudiante.completado` es un booleano. El portal, el admin y el diploma lo tratan como la verdad del aprendizaje. Lo encienden varios sitios y no quieren decir lo mismo. El caso más claro: al llegar a la pregunta abierta final, el curso ya queda completado, antes de que la persona responda. El certificado nace de esa bandera (`signals_certificados.py`). Sin preguntas, la nota es 100. El cierre presencial marca módulos que el chat no recorrió y el portal lo cuenta igual.

## De dónde sale

| Plan | Qué ya decidió | Qué no manda este corte |
| --- | --- | --- |
| Camino a 5.000, bloques 0–2 | Bandeja, outbox, Redis, workers. Eso sigue siendo el frente. | El significado de “completó”. |
| `docs/PLAN_CONSTRUCTOR_CURSOS_EKI.md` | Autoría versionada (bloque 4) y constructor (bloque 5). | El diploma y el cierre. |
| `docs/PLAN_MODULARIDAD_EKI.md` | Estados del chat partidos. | El contrato del aprendizaje no se partió con ellos. |
| Mitigación 7 del maestro | No gastar los meses en constructor, ciclo &lt;30 ni otra flota antes de 0–1–2 verdes. | Este expediente sí se puede cortar en paralelo: no crea app Django, no abre workers, no sube RDS. |

El Sender del bloque 2 **no entra aquí**. El motor que llama a un enviador es otro frente. Meterlo en el diploma es el PR que rompe las dos cosas.

## Camino a 8 (canvas del 10 de noviembre de 2026)

Programa de CTO: subir cada eje de solidez a **8**. El 10 no se programa (evidencia de meses y revisión externa). No sustituye el camino a 5.000. Es la misma fila de trabajo, puntuada.

| Bloque del canvas | Ejes a 8 | Dónde vive | Cómo convive |
| --- | --- | --- | --- |
| A. Expediente | Expediente, diploma, un motor | Este plan (cortes 1–5). El “un motor” (aula y WhatsApp la misma función) espera a que el escritor exista; no es el corte 1. | Paralelo al bloque 2. Un commit no mezcla diploma con outbox. |
| B. Sender en la lección | Canal Meta | Bloque 2: el *listo* hoy llama `enviar_meta`, no `sender_de_linea`. | No desplegar A y B en el mismo paquete. |
| C. Aislamiento en aula y API | Aislamiento | Bloque 7. El test ZZB de portal ya existe; falta Aprende y `/api/`. | Después del padrón. |
| D. Esos contratos en el PR | CI que frena | Checklist de `.github/workflows/ci.yml`. | Cada corte de A/B/C mete su test corto al checklist, no la suite nocturna. |
| E. La caja no es el broker | Operación | Bloque 2: `EKI_REDIS_FAIL_CLOSED` (apagado) y el mapa de workers. | Flag apagado no cambia producción. |

Listo de A (nota 8): una función escribe el avance; un test falla si otro archivo de producto asigna `completado`; llegar a la pregunta final no crea certificado; sin preguntas la nota de un certificado **nuevo** queda vacía; el portal puede separar cierre presencial y recorrido. Los PDF ya emitidos no se reimprimen. Quien ya tiene diploma no se descompleta.

El canvas pide que A cierre antes de abrir B. En git se pueden cortar en paralelo. En **deploy**, A y B no salen juntos.

`learning/` puede seguir sin ser dueño de las tablas. IQ Rural, otro agente u otra pantalla no cierran este hueco.

## Lo que no se hace

- Cambiar el significado de `completado` en el mismo campo para que pase a querer decir “aprendió”. El booleano se queda como “el recorrido de chat (o la operación) se dio por cerrado”. El diploma sale de reglas. El portal, más adelante, distingue origen.
- Descompletar a quien ya está en la pregunta abierta final con `completado=True` y certificado. Eso es un incidente de datos.
- Reimprimir PDF ya emitidos con nota 100 y sin examen.
- Un grep que falle por `formulario.Sesion.completado`: es otro modelo.
- Fusionar los cuatro cortes de abajo en un solo commit.
- Tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`.

## Cortes

Cada corte de comportamiento lleva interruptor con el default actual, salvo el 1 (solo tests) y el 2 (mismo comportamiento, otro sitio).

### Corte 1 — Caracterizar lo de hoy

Tests que fijan, no el diseño nuevo:

- Al elegir la pregunta abierta final, `completado` ya es verdadero y hay `fecha_completado` (`response_templates.py`, `continuar_leccion.py`, `estados/modulo.py`).
- `selector_curso.py` marca completo y no guarda fecha: el signal puede no disparar.
- `cerrar_curso_si_tramo_final` completa módulos desde el actual hasta el último y enciende la misma bandera.
- `calcular_calificacion_curso` devuelve 100.0 si no hay preguntas respondidas.
- `exigir_nota_minima_certificado` apagado, o sin calificaciones, deja emitir.

**Gate:** los tests fallan si alguien cambia ese momento sin querer. El estudiante no nota nada. Cero migraciones.

### Corte 2 — Un solo escritor, mismo significado

Una función escribe `completado` / `fecha_completado` / `fecha_ultimo_avance`. Los sitios de producto dejan de asignar `completado = True` a `ProgresoEstudiante`. Un test rojo si aparece otro escritor de producto (no fixtures, no `formulario`).

**Gate:** mismos mensajes, misma fecha, mismo signal. Contratos de ambas líneas verdes. Si un contrato que no estaba en el baseline falla, se para; no se cambia el test para ocultarlo.

### Corte 3 — El diploma lee reglas

El `post_save` deja de ser el emisor. Se emite a propósito, con reglas, detrás de un interruptor apagado: default = lo de ahora (bandera + fecha). Con el interruptor prendido: módulos publicados recorridos; evaluación respondida si existía; llegar a la pregunta final no crea certificado.

**Gate:** con el flag apagado, un cierre de hoy sigue generando el diploma igual. Con el flag prendido, llegar a la pregunta abierta final no crea fila de `Certificado`.

### Corte 4 — Origen del cierre (expand)

Migración aparte: columna de origen (`chat` / `operacion` / `presencial`). El cierre presencial escribe `operacion` o `presencial`. El KPI viejo `completado=True` no se redefine en silencio. El portal lo muestra cuando haya pantalla; hasta entonces no se tocan listados calientes (mitigación 6).

**Gate:** `makemigrations` solo añade columna. Un cierre presencial queda distinguible en base. Nadie pierde `completado`.

### Corte 5 — Nota vacía en emisiones nuevas

Con interruptor apagado, `calcular_calificacion_curso` sigue devolviendo 100. Con el interruptor prendido, sin preguntas la nota del **certificado nuevo** queda vacía (no 100). Los PDF ya emitidos no se tocan.

**Gate:** un curso sin preguntas, flag apagado: 100 como hoy. Flag prendido: el certificado nuevo no lleva 100. Un PDF viejo sigue igual.

## Cómo convive con el bloque 2

El frente sigue siendo bandeja / outbox / Redis / sleeps. Un commit de expediente no lleva archivos de workers. Un commit de outbox no lleva `signals_certificados.py`. Si hay que elegir un solo frente en la sesión, gana el bloque 2.

## Informe de cada corte

`git status`, archivos nuevos trackeados, `python manage.py check`, `python manage.py makemigrations --check --dry-run` si el corte tocó modelos, y las pruebas del área en PostgreSQL (certificado, contratos de línea si se tocó el momento del cierre). Deploy solo con pedido explícito.
