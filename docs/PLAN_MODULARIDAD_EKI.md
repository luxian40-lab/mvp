# PLAN_MODULARIDAD_EKI — Limpiar el espagueti y crecer por líneas

Cómo usarlo: «Lee @docs/PLAN_MODULARIDAD_EKI.md y ejecuta la fase X siguiendo el protocolo». La skill que lo aplica es `.cursor/skills/eki-refactor-motor/`. Las reglas permanentes siguen en `.cursor/rules/eki.mdc`.

Medición base: 24 de octubre de 2026, rama `feat/admin-inicio` (`b0ac750c`).

## 0. Contexto

eki es un monolito Django. El problema no es solo una función grande: `core` es un monolito dentro del monolito.

| Medida | Valor base |
|---|---|
| `core` | 114.000 líneas, 435 archivos. 232 sueltos en la raíz (68.000 líneas) |
| Ciclo de imports más grande | 183 módulos que se importan en círculo |
| `core/models.py` importa lógica de negocio | 16 módulos (`module_steps`, `rag_manager`, `planes_linea`…) |
| `core` importa apps de arriba (`portal`, `aprende`, `studio`, `formulario`) | 45 aristas |
| `_procesar_twilio_webhook_cuerpo` | 3.226 líneas, 450 ramas, 436 variables locales |
| `get_response_for_intent` | 1.761 líneas, 274 ramas |
| `except Exception` / `except:` en código de producto | 896 |
| `es_modo_twilio()` / `es_solo_cursos()` | 14 en 6 archivos; 6 fuera de `core/lineas/` |
| Copias del parser `[MULTI_MSG]` / `[SEP]` | 12 |
| Reemplazos de atributos de módulos en runtime | 11; 2 son de `twilio.rest.Client` (`sandbox_canal.py`, `twilio_transporte.py`) |

Los valores exactos que vigila CI están en `scripts/complejidad_baseline.json`.

Las apps de dominio (`learning`, `agents_*`, `analytics`, `integrations`) son cascarones. La semilla buena es `core/lineas/`: módulos chicos, Meta primero, el curso llama esos nombres sin abrir el webhook.

## 1. Modelo de producto: dos líneas, un motor de curso

Las dos líneas son de Meta (WhatsApp Cloud API). Twilio queda para demo, HSM históricos y el código de *aula*.

| | Línea principal (`uso = completa`) | Línea 2 (`uso = solo_cursos`, «curso lineal») |
|---|---|---|
| Entrada | Campaña con plantilla Meta | Campaña con plantilla Meta (WABA propia) |
| Antes del curso | Habeas, cédula, menú según plan OP1/OP2/OP3 | Habeas, cédula, directo al curso |
| Oferta | Formación (carrusel, 1 o 2 cursos al mes) y Asesoría (Nat, Coach, Profe IA, Ventas, Finanzas, con cupo) | Solo el curso de la campaña. Pedir un asesor responde «esta línea es solo del curso» |
| Dentro del curso | Módulos, pasos, drip, *listo*, Formador y Compañero, evaluación, certificado | Lo mismo |
| Después del curso | Vuelve al menú | Certificado y cierre. Otra campaña puede inscribir el siguiente curso |

El motor de curso es compartido. La línea 2 es casi solo el motor: si el motor se rompe, la línea 2 se queda sin producto.

Decisiones de producto (24 de octubre de 2026):

1. Una persona puede estar en las dos líneas a la vez. No es común, pero pasa. El estado del curso tiene que ser por persona y línea, no por teléfono.
2. En la línea 2 una persona termina un curso y después puede recibir otra campaña con otro curso. Cursos en serie, no a la vez.
3. Vendrán más líneas, quizá una por cliente. El perfil de línea vive en la base, editable en el admin. `META_LINEAS` queda de respaldo.

## 2. Arquitectura destino

```
Entrada (firma, idempotencia, encolar)
  -> Turno (una vez por mensaje: línea, perfil, cliente, estudiante, sesión, plan, cursos y agentes permitidos)
  -> Puertas en orden (opt-out, habeas, cédula, certificado pendiente, aula)
  -> Perfil de la línea
       completa      -> Menú, carrusel, asesores -> Motor de curso
       curso lineal  -> Motor de curso
  -> Respuesta tipada -> Sender de la línea (phone id + WABA)
```

- `PerfilLinea`: capacidades explícitas (menú, carrusel, varios cursos, asesores, planes, agentes en curso, certificado, aula, campañas). La principal las tiene todas. La línea 2: agentes en curso, certificado, campañas. Una línea nueva es un perfil nuevo, no código nuevo.
- `Turno`: contexto del mensaje. Se calcula una vez y viaja a todos los pasos.
- Puertas: lista ordenada de `manejar(turno) -> Respuesta | None`. El perfil decide cuáles corren.
- Motor de curso: un handler por estado en `core/conversacion/estados/`. No pregunta por la línea; consulta el perfil cuando el comportamiento difiere.
- Sender por línea: sin reemplazo global de `twilio.rest.Client`.

Dirección de dependencias: modelos abajo, servicios en el medio, puertas, menú, admin, tareas y webhooks arriba. El motor no importa el menú ni los asesores. `core` no importa `portal`, `aprende`, `studio` ni `formulario`.

## 3. Reglas para agregar funciones sin romper la otra línea

1. Nada de `es_modo_twilio()` / `es_solo_cursos()` nuevos. Lo que cambie por línea es una capacidad del perfil, apagada por defecto en todas las líneas.
2. Una función nueva entra como puerta, handler de estado o agente. Nunca dentro de `_procesar_twilio_webhook_cuerpo`, `dispatch_sandbox_menu` ni `get_response_for_intent`.
3. Cada línea tiene su suite de contrato. Las dos quedan verdes en cada commit.
4. Nada de marcadores de texto nuevos (`[MULTI_MSG]`, `[MEDIA:]`, `[DELAY:]`…). Lo nuevo devuelve `Respuesta`.
5. Nada de `enviar_*` nuevos fuera del Sender. Nada de reemplazar atributos de módulos en runtime.
6. Ninguna función nueva de más de 150 líneas. `except Exception` solo con `logger.exception` y motivo.
7. Flags y umbrales por línea en settings o en la base, con la fecha de verificación (regla 14).

El freno de CI (`scripts/ratchet_complejidad.py`) mide las reglas 1, 4, 5 y 6. Sus números solo pueden bajar.

## 4. Protocolo

Rama por fase. Un cambio por commit. Mover y cambiar comportamiento son commits distintos. Al cerrar cada bloque:

```
BLOQUE: <fase.bloque>
Commits: <hashes + mensajes>
Archivos tocados / nuevos y estado en git: <lista>
Migraciones nuevas: <lista, reversibles o no>
Resultado: check / makemigrations --check / tests del área / ratchet
Contratos de línea: principal <ok|n/a>, línea 2 <ok|n/a>
Riesgos o dudas: <lista>
```

Esperar «continúa» antes del siguiente bloque. Deploy solo con pedido explícito.

## 5. Fases

| Fase | Qué | Cambia comportamiento | Línea que protege |
|---|---|---|---|
| 0 | Guardianes: skills, hooks, freno de CI | No | Ambas |
| 1 | Tronco único | No | Ambas |
| A | Contratos de línea y caracterización | No | Ambas |
| B | Canal seguro | Sí, con flag | Ambas |
| C | Turno y perfil de línea | No, salvo C4 | Ambas |
| D | Motor de curso | Solo movimiento | Línea 2 |
| E | Estado por persona y línea | Sí, con flag | Ambas |
| F | Puertas y menú | Solo movimiento | Principal |
| G | Protocolo de respuesta | Sí, con flags | Ambas |
| H | Dominios de `core` | Solo movimiento | Ambas |
| I | Escalabilidad | Sí | Ambas |

### Fase 0 — Guardianes

- 0.1 Plan, skill `eki-refactor-motor` y ajustes a `eki-dev`, `eki-code-review`, `eki-tdd`, `eki-incremental`.
- 0.2 Freno de complejidad: `scripts/ratchet_complejidad.py`, `scripts/complejidad_baseline.json`, `core/tests_ratchet_complejidad.py` en CI.
- 0.3 Hooks de Cursor: proteger el cuerpo, medir tras editar, revisar antes de `eb deploy`.

### Fase 1 — Tronco único

Hecho el 24 de octubre de 2026. Producción: `main-lineas-meta-20261024-142853`, commit `3c317d73`. `main` local = `010424b2`, mismo árbol, con los 5 commits de `origin/main` registrados (ya estaban en producción por cherry-pick).

- `.ebignore` deja fuera `.env*`, `*.pem`, credenciales y `.cursor/`: la CLI comprime la carpeta en disco.
- `docs/CONTINUAR_EKI.md` y `.cursor/rules/continuar-eki.mdc`: deploy desde un worktree limpio de `main`, sin cherry-pick.
- [MANUAL] `git push origin main` (fast-forward, sin `--force`).

### Fase A — Contratos de línea

Tests contra PostgreSQL (Docker local: `postgres:15`, `redis:7`). Envíos capturados en el borde (Graph y Twilio), sin red.

- A1 Arnés: fábrica de payloads Meta firmados por línea (phone id), captura de envíos, reloj fijo.
- A2 Contrato principal: campaña, habeas, cédula, menú por plan, carrusel, curso, *listo*, asesor con cupo, fin de curso vuelve al menú.
- A3 Contrato línea 2: campaña, habeas, cédula, curso directo, módulos, Formador y Compañero, evaluación, certificado. Pedir asesor responde «solo curso». Una segunda campaña inscribe el siguiente curso.
- A4 Persona en las dos líneas: las sesiones no se mezclan. Documenta el comportamiento actual del estado compartido (es el caso que corrige E).
- A5 Caracterización de los 13 estados del motor. Cobertura de ramas del cuerpo.
- A6 Duración por estado y por línea, medida desde el wrapper.
- [MANUAL] Contar en producción estudiantes con `estado_onboarding` en `esperando_respuesta_tutor_ia`, `esperando_respuesta_progreso`, `esperando_respuesta_recuperacion`.

### Fase B — Canal seguro

- B1 `Client` permanente que decide el canal por `ContextVar`, instalado una vez. Reemplaza los dos reemplazos globales. Flag con default que no cambia el comportamiento.
- B2 Interfaz `Sender` (`MetaSender`, `TwilioSender` legado) con phone id y WABA de la línea.

Desbloquea hilos y concurrencia en el worker.

### Fase C — Turno y perfil de línea

- C1 `Turno` en `core/conversacion/turno.py`. Lee lo que hoy se calcula en cada sitio. Sin cambio de comportamiento.
- C2 `PerfilLinea` con capacidades, derivado de `LineaMeta.uso`.
- C3 Reemplazar los 14 `es_modo_twilio()` por capacidades. Un archivo por commit.
- C4 Modelo de línea en la base (phone id, número, WABA, cliente, perfil), admin Unfold. `META_LINEAS` y las variables actuales quedan de respaldo. Migración expand.

### Fase D — Motor de curso

Requiere levantar la regla «no tocar el cuerpo» en `eki.mdc` y `.cursor/refactor_motor.json`.

- D1 `Contexto` y `Respuesta` en `core/conversacion/`.
- D2 Un estado por commit hacia `core/conversacion/estados/`, de chico a grande: cédula, curso finalizado, recuperación, progreso, tutor IA, asistente, confirmación, pregunta final, reto, módulo, selección de curso. Solo movimiento.
- D3 El cuerpo queda como despachador `{estado: handler}`.
- D4 Borrar ramas muertas, en commits aparte, con el conteo de producción de la fase A.

### Fase E — Estado por persona y línea

- E1 Expand: tabla de estado por (estudiante, línea): `estado_chat`, `estado_onboarding`, `contexto`. Nullable, sin reescribir filas.
- E2 Escritura doble detrás de flag.
- E3 Lectura desde la tabla nueva vía `Turno`, detrás de flag. Contrato A4 pasa a exigir estados separados.
- E4 Contract en un bloque posterior: dejar de escribir los campos viejos. No se borran columnas en el mismo deploy.
- `contexto_temporal = None` deja de borrar claves ajenas: se limpian solo las claves del estado que sale.

### Fase F — Puertas y menú

- F1 Puertas compartidas fuera de `sandbox_menu.py`: opt-out, habeas, cédula, confirmación, aula.
- F2 Menú, carrusel y asesores de la línea principal en su paquete.
- F3 `dispatch_sandbox_menu` queda como despachador por perfil.

### Fase G — Protocolo de respuesta

- G1 Un solo parser de marcadores (las 12 copias llaman a uno).
- G2 `Respuesta` tipada; los marcadores quedan como formato legado de entrada.
- G3 Delays como tareas Celery con `countdown`, sin `time.sleep` en el worker.
- G4 LLM en la cola `llm` con respuesta diferida.
- G5 `print` a `logger`; `except Exception` con `logger.exception`.
- G6 Tabla explícita de transiciones de estado.
- G7 `get_response_for_intent` por el mismo camino que el cuerpo.

### Fase H — Dominios de `core`

- H1 `core/models.py` pasa a paquete `core/models/` (misma app, sin migraciones). Se quitan los imports de negocio de los modelos.
- H2 Archivos sueltos a paquetes por dominio, solo movimiento, con reexport en la ruta vieja: canal, conversación, curso, agentes, campañas, certificados, gamificación, analítica, vistas admin. Primero los menos acoplados.
- H3 Cortar los imports de `core` hacia `portal`, `aprende`, `studio`, `formulario`.

### Fase I — Escalabilidad

- I1 Colas por tipo: `conversacion`, `llm`, `certificados`, `masivo`, `audio`.
- I2 Tope de mensajes por segundo por línea (cada WABA tiene su límite en Meta), claim e `INCIERTO` del P4 de `PLAN_ESCALABILIDAD_EKI.md`.
- I3 Resúmenes diarios e índices (P7).
- I4 Carga sintética por línea: pico de las 08:00 de la línea 2 y asesores de la principal.

## 6. Definición de terminado

- Contratos de las dos líneas en verde y obligatorios en CI.
- `_procesar_twilio_webhook_cuerpo` por debajo de 400 líneas. Ninguna función de `core/conversacion/` pasa de 300.
- Cero `es_modo_twilio()` fuera de `core/lineas/`. Cero reemplazos globales de `Client`. Un solo parser.
- Estado de curso por persona y línea.
- Una línea nueva se da de alta desde el admin sin deploy.
- Ciclo de imports más grande por debajo de 30 módulos. `core` no importa apps de arriba.
