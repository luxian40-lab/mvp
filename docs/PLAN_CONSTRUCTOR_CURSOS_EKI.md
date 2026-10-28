# Plan — Constructor de cursos eki

**Estado:** decisión de producto y plan de ejecución.  
**Fecha:** 27 de octubre de 2026.  
**Alcance inicial:** admin interno. Portal B2B después de estabilizar el flujo interno.  
**Canal principal:** Meta WhatsApp Cloud API. Twilio no define el diseño nuevo.

## 1. Decisión

Module Builder seguirá existiendo como concepto, pero dejará de ser el editor frágil de un
solo módulo. Se convertirá en el **constructor oficial de cursos de eki**.

No se continúa el reskin ni se agregan funciones sobre la pantalla actual. El constructor
nuevo reutiliza los modelos y contratos de negocio existentes, pero nace como una superficie
nueva, detrás de un interruptor separado. El Builder actual queda como legado temporal hasta
retirar sus cursos y operaciones.

La alternativa de usar únicamente formularios de Django Admin se conserva como contingencia,
no como producto destino: es más barata a corto plazo, pero mantiene fragmentada la creación,
no representa la conversación de WhatsApp y obligaría a construir otra experiencia distinta
cuando la autoría llegue al portal.

## 2. Qué producto construye

eki forma por WhatsApp en conectividad limitada. El constructor no crea páginas de un LMS:
crea una secuencia conversacional que el motor puede entregar, evaluar, calendarizar y
certificar.

Vocabulario de producto:

- **Curso:** programa completo.
- **Módulo:** una idea o resultado de aprendizaje.
- **Bloque de entrega:** lo que llega después de un `Continuemos` / `listo`. En los modelos
  actuales corresponde a `SeccionModulo`.
- **Mensaje:** texto, imagen, video, audio, documento o evaluación dentro del bloque. En los
  modelos actuales corresponde a `PasoModulo`.

Regla recomendada: un `Continuemos` entrega un bloque. Un módulo simple tiene un bloque; uno
complejo puede tener varios. Una evaluación detiene la secuencia hasta recibir respuesta.
Esta regla coincide con `core/module_steps.py` y sus contratos actuales. La documentación que
afirma que un solo `listo` entrega todo el módulo debe corregirse antes de implementar.

## 3. Responsabilidad del constructor

El constructor administra:

- identidad, objetivo y estructura del curso;
- módulos, bloques y mensajes;
- texto y media apta para Meta;
- evaluaciones y feedback;
- orden y vista previa real de WhatsApp;
- calendario y disponibilidad del contenido;
- estado borrador, validación y publicación;
- integración de Course Engine como generador de borradores;
- prueba controlada con el número interno.

El constructor no administra estudiantes, grupos, campañas, conversaciones, analítica ni
agentes de asesoría. Puede enlazar esas superficies, pero termina al producir una versión de
curso válida y publicable.

## 4. Principios no negociables

1. Una tarea primaria por pantalla.
2. Cada acción guarda un objeto explícito; no existe un “Guardar todo” ambiguo.
3. Guardar contenido nunca publica ni envía WhatsApp.
4. Una versión publicada no cambia silenciosamente: las ediciones posteriores son borrador.
5. La vista previa usa el mismo ensamblador que el motor; no imita el resultado solo con JS.
6. Course Engine genera borradores y nunca publica automáticamente.
7. Meta y 3G definen tamaños, formatos y ritmo.
8. Admin primero. Portal solo reutiliza servicios y permisos ya estabilizados.
9. Un slice vertical y un cambio de comportamiento por commit.
10. Contratos de línea principal y línea 2 verdes en cada slice que toque entrega.

## 5. Superficies del administrador

### Curso

- organización, propósito y audiencia;
- módulos ordenados;
- estado por módulo: borrador, con problemas, listo o publicado;
- resumen de calendario, certificado y preparación;
- acción principal única: continuar construyendo.

### Módulo

- bloques de entrega;
- mensajes del bloque seleccionado;
- vista previa de teléfono;
- acciones explícitas para texto, imagen, video, audio, documento y evaluación;
- subir/bajar como respaldo estable; drag solo después de tener contratos de navegador.

### Revisar y publicar

- media compatible con Meta;
- mensajes y evaluaciones completos;
- orden y calendario válidos;
- diferencias entre borrador y versión publicada;
- prueba interna;
- publicación explícita con confirmación.

## 6. Fases

### Fase 0 — Contrato de producto

Duración estimada: **2–3 días hábiles**.

- confirmar vocabulario y regla de avance;
- corregir contradicciones entre código y documentación;
- inventariar cursos activos que usan modo clásico, secciones/pasos o Course Engine;
- fijar criterios observables de éxito.

Gate: un ejemplo de curso se puede describir de punta a punta sin ambigüedad sobre qué recibe
el estudiante en cada `Continuemos`.

### Fase 1 — Contención del Builder legado

Duración estimada: **2–4 días hábiles**.

- congelar nuevas funciones y reskins;
- definir un solo camino operativo por curso;
- impedir que ops alterne Builder y admin clásico sin advertencia;
- conservar el legado para cursos existentes y rollback;
- medir los flujos que deben migrarse.

Gate: ningún curso nuevo depende de dos superficies de edición simultáneas.

#### Mitigación del admin nativo — 28 de octubre de 2026

Contención aplicada antes del constructor nuevo:

- una estructura heredada intercalada no bloquea guardar cambios ajenos a los mensajes
  (reto, calendario u otros campos del módulo);
- si se edita el inline de mensajes, la validación anti-intercalado sigue siendo obligatoria;
- “Clase rápida” queda en solo lectura cuando el módulo ya tiene más de un mensaje, para
  impedir que esa superficie modifique únicamente el primer `PasoModulo`;
- el resumen superior de errores y las guardas de tabs Unfold se conservan.

Esto no convierte el admin clásico en el constructor futuro. Solo lo deja como respaldo más
seguro durante la transición. Contratos:
`core.tests_admin_modulo_guardar_reto` y `core.tests_modulo_alta_micro`.

### Fase 2 — Constructor mínimo vertical

Duración estimada: **10–15 días hábiles**.

- lista de módulos de un curso;
- módulo con bloques y mensajes de texto;
- crear, editar, activar, ordenar y recargar sin pérdida;
- vista previa desde el ensamblador real;
- borrador y publicación explícitos;
- pruebas de navegador del camino feliz y de errores.

Fuera de esta fase: media, IA, portal, drag complejo y todas las configuraciones avanzadas.

Gate: una persona nueva construye y publica en un piloto un curso de texto sin usar el admin
clásico ni preguntar dónde guardar.

### Fase 3 — Curso completo para producción

Duración estimada: **15–25 días hábiles**.

- imagen, video, audio y documentos;
- evaluaciones A–D y abiertas;
- validaciones y procesamiento de media Meta;
- calendario y drip;
- certificado y checklist de preparación;
- prueba al número interno;
- migración asistida de cursos elegidos;
- retiro del Builder legado como camino por defecto.

Gate: curso mixto completo probado en las dos líneas Meta, sin fallos nuevos frente al baseline.

### Fase 4 — Course Engine integrado

Duración estimada: **10–15 días hábiles**.

- documentos y brief producen una propuesta de módulos, bloques y mensajes;
- video, infografía y podcast entran directamente como borradores;
- origen, costo, estado y `run_id` visibles;
- revisión humana obligatoria;
- regenerar una pieza no pisa el resto del curso.

Gate: un paquete generado llega a borrador y se publica sin copiar URLs manualmente.

### Fase 5 — Autoría en portal

Duración estimada: **20–30 días hábiles**.

- permisos y aislamiento por organización;
- cliente crea borradores y sube materiales;
- comentarios, envío a revisión y devolución;
- eki aprueba calendario y publicación;
- cliente nunca modifica una versión viva ni envía campañas por este flujo.

Gate: pruebas de tenancy, auditoría y aprobación; ninguna escritura cruza organizaciones.

## 7. Tiempo total realista con vibecoding

Supuestos: una persona dueña del producto, trabajo secuencial, reutilización de modelos, sin
reescribir el motor y con QA de navegador en cada slice.

- Primer constructor interno utilizable, Fases 0–2: **3–5 semanas**.
- Reemplazo operativo del Builder para cursos completos, Fases 0–3: **6–9 semanas**.
- Constructor con Course Engine integrado, Fases 0–4: **8–12 semanas**.
- Admin más portal con revisión, Fases 0–5: **12–18 semanas**.

Vibecoding acelera plantillas, servicios, tests y migraciones mecánicas. No elimina el tiempo
de decidir el contrato pedagógico, probar media real, validar Meta, proteger cursos vivos ni
hacer QA de navegador. Prometer el reemplazo completo en dos o tres semanas repetiría el patrón
de parches que dañó el Builder actual.

## 8. Cómo ayuda la refactorización actual

Ya reduce el riesgo:

- el motor está separado por estados en `core/conversacion/estados/`;
- línea principal y línea 2 tienen contratos;
- existen `Turno`, `PerfilLinea`, `Respuesta` tipada e interfaz `Sender`;
- los modelos están separados por dominio;
- el parser de mensajes es único;
- Celery tiene rutas preparadas para trabajo LLM y media.

No está terminado:

- quedan funciones grandes en intents;
- el ciclo de imports sigue alto;
- existen imports de negocio dentro de modelos;
- la generación y publicación de Course Engine todavía tienen pasos manuales;
- el Builder actual sigue acoplado a nombres de campos, DOM y múltiples acciones POST.

Consecuencia: el constructor nuevo debe llamar servicios de autoría y previsualización; nunca
debe importar el webhook ni reutilizar el JavaScript del Builder legado.

## 9. Gate para comenzar

Antes de código, PM y Content aprueban:

1. un `Continuemos` entrega un bloque;
2. un módulo simple puede tener un único bloque;
3. publicar crea una versión estable;
4. Course Engine solo produce borradores;
5. portal queda fuera hasta que la Fase 3 tenga QA_PASS.

Canon técnico temporal del legado: `docs/MODULE_BUILDER_WA.md` y
`docs/MODULE_BUILDER_UI_CONTRATO.md`.
