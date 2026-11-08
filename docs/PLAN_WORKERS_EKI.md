# Plan de workers — eki

Cómo se reparte el trabajo entre las dos cajas que ya existen. Sin esto el camino a 5.000 deja el mensaje de un estudiante compitiendo con un video o con una campaña, y eki sigue siendo un monolito que a veces responde.

No es un plan de producto en AWS. No sube la clase de la instancia, no abre una tercera caja y no vende capacidad. Eso queda para otro documento, después de que este plan y los bloques 0, 1 y 2 del camino a 5.000 estén verdes.

Se trabaja un corte a la vez. Cada corte cierra con el informe de gate y espera «continúa».

## De dónde sale

| Plan | Qué ya decidió | Qué no dice |
| --- | --- | --- |
| `docs/PLAN_MODULARIDAD_EKI.md` | G3: las pausas pasan a tareas con `countdown`. G4: el LLM va a la cola `llm`, flag apagado. | En qué máquina corre cada cola. |
| Camino a 5.000, bloque 2 | Un worker de conversación, concurrencia 1 hasta que no quede `time.sleep`, un solo beat, Redis gestionado, sin caer a `127.0.0.1`. Prohibido abrir otro entorno de worker de conversación antes de que los bloques 0, 1 y 2 estén verdes. | El mapa de las dos cajas que ya corren. |
| `docs/PLAN_ESCALABILIDAD_EKI.md` P3 | Roles web, worker y beat, colas, pool y el paso manual de ElastiCache. | Sigue escrito como si el worker general y el de IA fueran una sola decisión pendiente. |
| `docs/EKI_AI_WORKERS_SETUP.md` | Decisión del 31 de agosto de 2026: `eki-ai-workers` en `t3.small` para encode, RAG y Course Engine. Beat solo en `eki-prod-final`. | No es el plan de operación de hoy. El rollback de ese doc vuelve a Redis local; este plan no lo hace. |

## Cómo está hoy (4 de noviembre de 2026)

| Caja | Qué arranca | Colas |
| --- | --- | --- |
| `eki-prod-final` | `Procfile`: web, worker, worker de RAG y beat | El worker general (`scripts/run_worker.sh`) escucha por defecto `conversacion,masivo,celery,media_encode,llm,certificados`, concurrencia 1, prefork. El nombre del proceso es `fast@`. |
| `eki-ai-workers` | `Procfile.ai`, copiado cuando `EKI_EB_ROLE=ai_workers` | `media_encode`, `rag_index`, `course_engine`. Sin beat. `run_worker.sh` en esta caja hace `sleep infinity`: no lee `conversacion` ni `masivo`. |

Un `listo` y un MP4 que se comprime pueden caer en el mismo proceso de `eki-prod-final`, porque `media_encode` sigue en el default de `run_worker.sh`. `eki-ai-workers` también escucha `media_encode`. Si las dos cajas consumen esa cola, el encode no tiene dueño único.

Redis de producción todavía puede caer a `127.0.0.1` si falta `REDIS_URL`. El doc de agosto ya pedía ElastiCache. El bloque 2 del camino a 5.000 lo vuelve a pedir. No está cerrado.

Siguen `time.sleep` en `core/conversacion/`, `core/lineas/` y `core/avisos/`. Con concurrencia 1, una pausa ocupa el único worker de mensajes.

## Reglas que este plan no afloja

- La concurrencia del worker de conversación se queda en 1 hasta que no quede `time.sleep` en ese camino. No se sube para tapar la pausa.
- Un solo beat, en `eki-prod-final`. `eki-ai-workers` no lo prende.
- Otro worker de `conversacion` solo si la latencia de cola, medida, no cabe. Antes de esa cifra no se abre.
- No se sube la clase de RDS ni de la instancia web para este plan.
- Meta sigue siendo el canal de producto. Twilio no gana una cola propia.
- Nada de este plan se despliega solo. Hace falta el pedido y el gate del corte.

## Corte W0 — Inventario

Sin cambiar máquinas ni variables. Se anota lo que hay y se compara con la tabla de arriba.

- Qué proceso vive en cada caja (`ps` o el equivalente de `eb`) y qué valor tiene `CELERY_QUEUES` en cada entorno.
- Que `eki-ai-workers` no tenga beat y no lea `conversacion` ni `masivo`.
- Si `media_encode` lo consume una caja o las dos.
- Las tres cifras que el camino a 5.000 pide antes del bloque 1: tasa de duplicados, latencia de cola, cantidad de `INCIERTO` abiertos. Salen en Inicio cuando esa pantalla exista. En este corte bastan anotadas en el informe.
- Dónde está Redis: `REDIS_URL` presente, o el proceso hablando con `127.0.0.1`.

**Gate:** una tabla de caja, proceso, colas y Redis, con fecha. Si `media_encode` tiene dos consumidores, el informe lo dice y el corte W1 no arranca hasta decidir cuál se queda.

## Corte W1 — Dueño de cada cola

Esto es el bloque 2 del camino a 5.000, más la regla de las dos cajas. No abre flota.

- Cero `time.sleep` en `core/conversacion/`, `core/lineas/` y `core/avisos/`. Las pausas siguen siendo tareas con `countdown`, como ya dice la modularidad (G3).
- En producción, sin `REDIS_URL` el proceso no arranca. El broker usa `noeviction`. Caché y locks van en otra base lógica, para que el caché no expulse un lock.
- `conversacion` solo la escucha `eki-prod-final`. `media_encode`, `rag_index` y `course_engine` solo las escucha `eki-ai-workers`.
- `masivo` (campañas, avisos, recordatorios) no comparte el cupo de un `listo` cuando el corte W3 lo separe. Hasta entonces se anota si sigue en el mismo proceso. No se mueve en este corte si eso deja una cola sin consumidor.
- La concurrencia de `conversacion` sigue en 1.

**Gate:** un pico de varios `listo` no deja al worker ocupado en una pausa. Un encode corre en `eki-ai-workers` y no en `fast@`. Arranque de prod sin `REDIS_URL` falla. Web y las dos cajas ven el mismo broker.

## Corte W2 — Medir antes de crecer

No se prende otro worker. Se deja la cifra que decidiría prenderlo.

- Edad del mensaje más viejo de `conversacion` y profundidad de esa cola. La misma lectura para `masivo` y `media_encode`.
- Esas cifras se comparan con las de W0.
- Un segundo consumidor de `conversacion` solo se discute si la edad medida no cabe en el acuerdo de este corte. El acuerdo se escribe en el informe de W0, no se inventa aquí.

**Gate:** el informe trae las tres edades (conversación, masivo, encode) de un día laborable. Sin esa tabla, W3 no abre.

## Corte W3 — Después del padrón

Solo con «continúa» y con W1 y W2 verdes. Sigue sin subir la clase de la instancia.

- Prefork con concurrencia 2 en el worker de conversación solo si, tras web, worker y beat, queda memoria libre de sobra (la regla de 1,2 GiB está en P3 de escalabilidad). `threads` no se usa para tapar un hilo colgado: en hilos el `time_limit` de Celery no mata el hilo.
- `masivo` sale del proceso de `conversacion` si W2 mostró que la campaña empuja la edad de la cola de mensajes.
- Alarma de `CPUCreditBalance` de la instancia T, antes de hablar de cambiar el tipo. El env guardado y `.ebextensions` no dicen hoy el mismo tamaño; el informe lo deja en una línea.

**Gate:** con la concurrencia nueva, dos entregas de la misma correlación no salen dos veces (eso lo cierra el outbox del bloque 2). La edad de `conversacion` no empeora respecto de W2.

## Qué queda fuera

- Plan de producto en AWS: más organizaciones, costo por estudiante, staging que no comparta la base, cuándo la capacidad se vende sin comprar otra caja. Documento aparte. No se abre mientras W0–W2 y los bloques 0, 1 y 2 sigan abiertos.
- Segundo entorno de worker de `conversacion`.
- Subir RDS o la instancia web.
- Microservicios o una app Django nueva.
- IQ Rural, constructor y el ciclo de imports por debajo de 30.

## Informe de cada corte

`git status`, archivos nuevos trackeados, `python manage.py check`, `python manage.py makemigrations --check --dry-run` si el corte tocó código, y las pruebas del área en PostgreSQL. Si el corte es solo inventario, el informe es la tabla y no hay diff de comportamiento. Deploy solo con pedido explícito.
