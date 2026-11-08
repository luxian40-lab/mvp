# PLAN_ADMIN_UNFOLD_CLARIDAD — Nombres claros en el admin

Cómo usarlo: «Lee @docs/PLAN_ADMIN_UNFOLD_CLARIDAD.md y ejecuta el slice X». No reemplaza `docs/PLAN_MODULARIDAD_EKI.md` ni `docs/PLAN_ADMIN_LINEAS.md`. Solo ordena lo que el staff ve en Unfold.

Escrito el 4 de noviembre de 2026. Solo lectura del repo y de la web ese día. Sin código.

El 8 de noviembre de 2026 se aplicó el **slice 0** (docs): tabla OP = `PLAN_CHOICES`, hoja Jazzmin marcada, frase líneas menú vs base. Los slices 1–3 esperan una rama limpia desde `origin/main`. **No** se ejecutan sobre `slice/bloque-1-bandeja`. E4 sigue esperando al slice 3. No plugins. No pin nuevo.

El admin no está roto. El menú, la búsqueda (Ctrl+K) y los documentos no dicen la misma cosa que el motor de las dos líneas.

## 0. Recomendación (plugins y skills)

No instalar ningún plugin ni skill ajena para esto.

| Pieza | Estrellas aprox. (nov 2026) | Qué hacer |
|---|---|---|
| [django-unfold](https://github.com/unfoldadmin/django-unfold) | ~3.700 | Ya está. Pin `django-unfold==0.91.0` en `requirements.txt` por Python 3.11 en Elastic Beanstalk. La 0.110 existe (13 de octubre de 2026). Subirla es cambio de plataforma, no arreglo de menú. |
| [formula](https://github.com/unfoldadmin/formula) | ~134 | Demo oficial. Sirve de patrón (cards, tabs, filtros) al armar una página propia. No se instala. |
| [turbo](https://github.com/unfoldadmin/turbo) | ~400 | Arranque Django + Next. No es este admin. |
| [django-unfold-extra](https://github.com/metaforx/django-unfold-extra) | 3 | Django CMS y parler. No. |
| [django-unfold-modal](https://github.com/metaforx/django-unfold-modal) | 5 | Popups de relacionados. Pide Django ≥ 5 y Unfold &lt; 0.109. No resuelve los nombres. |
| Skill `unfold-admin` en [0xDarkMatter/claude-mods](https://github.com/0xDarkMatter/claude-mods) | el repo ronda decenas de estrellas, no miles | Guía genérica para agentes. Asume el Unfold reciente y no conoce el pin 0.91, las dos líneas ni la paleta ya cableada. Instalarla pelea con `.cursor/skills/eki-ux` y con `.cursor/rules/eki-unfold-admin.mdc`. |

No hay un plugin con muchas estrellas que arregle Unfold. Lo que ya trae la 0.91 y se usa a medias:

- secciones colapsables del sidebar
- paleta con `SearchResult` (`core/admin_command_search.py`)
- `conditional_fields`
- filtros desplegables
- inlines en pestaña
- componentes Card y Table en páginas propias (`/admin/lineas/`, Inicio)

Esas piezas alcanzan para los slices de abajo. Formula se mira, no se copia como dependencia.

## 0b. Skills de diseño y de equipo (4 de noviembre de 2026)

Estrellas leídas de la API de GitHub ese día. Sirven para pensar el admin, no para rediseñarlo de cero. El admin es una herramienta de operación (Unfold, muchas horas, poca decoración). Las skills más estrelladas están hechas para landings y se cansan a la vista si se aplican aquí.

`eki-ux` y `eki-designer` siguen mandando: flujos, tokens `#9A6CAC` / `#7A4E8E` / `#5F3A6E`, un skin Unfold, sin inventar paleta. Una skill externa es un lente. No reemplaza esas dos.

### Usar, en este orden, cuando se revise una pantalla

| Orden | Repo | Estrellas | Qué tomar | Qué no tomar |
|---|---|---|---|---|
| 1 | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | 102.834 | Modo **Operate** (lo escribe para admin, tablas y ajustes: la herramienta desaparece en la tarea). Comandos `quieter`, `distill`, `clarify`, `typeset`, `layout`, `critique`, `audit`. `quieter` en Operate baja saturación, cards planas, menos color y menos motion. | `bolder`, `overdrive`, `delight`, `colorize`, `animate` en el admin. Esos suben la intensidad. |
| 2 | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) → skill `web-design-guidelines` | 33.548 el repo | Contraste, foco visible, formularios, `prefers-reduced-motion`, tema claro/oscuro, estados de error. El repo declara cientos de miles de instalaciones de esa skill. | `react-best-practices`, deploy a Vercel, composición React. El admin es Django. |
| 3 | [Owl-Listener/designer-skills](https://github.com/Owl-Listener/designer-skills) | 3.248 | El equipo, no el look: arquitectura de la información (nombres, grupos, búsqueda), interacción (formularios, navegación, leyes cognitivas), crítica visual (jerarquía y densidad). 273 skills; no se instala el paquete entero. | Research de personas, liderazgo, sprints, prototipos de producto nuevo. |
| 4 | [mastepanoski/claude-skills](https://github.com/mastepanoski/claude-skills) | 58 | Pocas estrellas, el método justo: heurísticas de Nielsen (sobre todo reconocimiento antes que memoria, consistencia, estética mínima) y auditoría de arquitectura de la información (organización, rótulos, navegación, búsqueda). | El resto del repo (gobierno de IA, seguridad). |

Cómo se encadenan, como equipo y sin instalar las 273:

1. `eki-ux` nombra la tarea de la pantalla (una sola).
2. Nielsen + arquitectura de la información preguntan si el nombre se entiende sin recordar una URL (el caso de «Líneas» y de Ctrl+K).
3. Impeccable en Operate, con `quieter` y `critique`, mira si la pantalla cansa: bordes de más, color de más, movimiento de más.
4. `eki-designer` acepta o rechaza el cambio visual contra los tokens. No entra una fuente nueva ni un acento que no sea el morado eki.
5. `web-design-guidelines` revisa contraste, foco y motion reducido antes de dar por buena la pantalla.

### No instalar en el admin

| Repo | Estrellas | Por qué no |
|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) (`frontend-design`) | 187.424 | Pide una identidad distinta y riesgo estético. Bien para una pieza de marca nueva. En el admin pelea con Unfold y con «que no canse». |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 145.239 | 79 estilos (glass, clay, brutalism, bento) y 192 paletas. Genera un sistema visual nuevo. El admin ya tiene el suyo. |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 110.080 | Dirección de arte, imágenes de referencia y páginas. No es una ficha de Django. |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | 53.569 | Oficio de motion. El admin admite dos o tres intenciones (hover, abrir un detalle), no una capa de animación. |
| [jakubkrehel/skills](https://github.com/jakubkrehel/skills) | 10.815 | Interfaces de producto nuevo. Mismo riesgo: rehacer en vez de aclarar. |
| [bencium/bencium-marketplace](https://github.com/bencium/bencium-marketplace) | 466 | Tiene un UX «controlado» útil en la idea (preguntar antes de decidir, WCAG). También un UX «innovador» de gradientes. Con 466 estrellas no gana a Impeccable, y el innovador no entra. |

Instalada el 4 de noviembre de 2026, recortada, en `.cursor/skills/eki-impeccable/`. Entran Operate y los playbooks `quieter`, `distill`, `critique` y `audit`. No entra el motor (`detect`, live-server) ni `bolder`, `overdrive`, `delight`, `colorize` o `animate`. `eki-ux` y `eki-designer` siguen mandando en nombres y tokens. El primer uso es un critique de una pantalla, sin cambiar CSS, hasta que ese critique se acepte.

## 1. Dónde está el proyecto

Handoff vivo: `docs/CONTINUAR_EKI.md`. Último deploy anotado ahí: 29 de octubre de 2026, versión `main-entrada-asesoria-20261029-220849`, commit `6bd02cd4`. La charla de entrada de asesoría está en el código con `EKI_ASESORIA_ENTRADA` apagado.

`docs/PLAN_MAESTRO_ESTABILIZACION_EKI.md` apunta a `origin/main` (`5b992fde`). El handoff de producción sigue en CONTINUAR. El maestro no manda sobre `eb status`.

`docs/HOJA_RUTA_ADMIN_PORTAL.md` habla de Jazzmin. No se usa. El canon del admin es `docs/EKI_UNFOLD_ADMIN.md` más el menú en `mvp_project/unfold_admin.py`. Ese doc está fechado el 1 de octubre de 2026 y ya no coincide con los planes del código.

Pin: `django-unfold==0.91.0`. `show_all_applications` está en falso: lo que no está en el sidebar ni en la paleta no se encuentra.

## 2. Modularidad, y qué de eso se ve en el admin

Plan: `docs/PLAN_MODULARIDAD_EKI.md`. Medición base del 24 de octubre de 2026.

| Fase | Estado el 4 de noviembre de 2026 | Se ve en el admin |
|---|---|---|
| A–D, F, G1, G2, G7, H1 | Hechas y en producción. El cuerpo quedó en unas 384 líneas. Los estados viven en `core/conversacion/estados/`. | No. |
| E1–E3 | Hechas y prendidas. El estado de conversación es por persona y línea (`EstadoLinea`). | El listado de estudiantes sigue mostrando el campo compartido `estado_chat`. Editarlo copia a todas las filas. |
| E4 | Espera. Los campos viejos se siguen escribiendo como espejo. | El espejo parece la verdad. |
| C4 | `LineaWhatsapp` existe (`core/lineas/modelo.py`, admin `core/admin/lineas.py`, migración 0190). `EKI_LINEAS_BD_ENABLED` apagado: mandan las variables, no las filas. | Menú «Líneas» abre la pantalla de solo lectura. La ficha editable no está en el sidebar. |
| Cursos por línea | Tabla hecha (0192). `EKI_CURSOS_POR_LINEA` apagado. | El campo cursos de la ficha dice que vacío = todos, y que solo cuenta con el flag. |
| H2, H3, G3–G6, I2–I4 | Pendientes. No son este plan. | No. |
| Constructor | `docs/PLAN_CONSTRUCTOR_CURSOS_EKI.md`. El Builder actual es legado temporal. | Dos editores de módulo. No se tocan aquí. |

`docs/PLAN_ADMIN_LINEAS.md` (25 de octubre) pide que el admin no pida WABA ni phone id, y que la línea se elija al crear la campaña. La ficha `LineaWhatsapp` sí pide phone id y WABA, porque es el alta en base del C4, no la pantalla de campaña. Las dos cosas conviven y el menú no las separa.

## 3. Lo ambiguo

### 3.1 «Líneas» son dos pantallas

- Sidebar Mensajería → Líneas → `/admin/lineas/` (`core/views_lineas_admin.py`). Solo lectura de las variables de entorno.
- Modelo `LineaWhatsapp`, changelist `/admin/core/lineawhatsapp/`. Ahí se cargan phone id, número, WABA, uso, cursos y cliente. No sale en el sidebar.
- La pestaña WhatsApp de la organización dice que las líneas 1 y 2 «están en Mensajería → Líneas». Eso abre la pantalla que no se edita.
- Con `EKI_LINEAS_BD_ENABLED` apagado, guardar una fila no cambia el envío. La ficha no lo dice en el título.

### 3.2 Ctrl+K abre la campaña vieja

`core/admin_command_search.py` incluye `core.Campana`. En `core/models/mensajeria.py` ese modelo se llama «Campañas». Es el lanzamiento histórico de Twilio.

No incluye `CampanaMeta` (el ítem del menú; verbose name «Campañas Meta»), ni `PlantillaMeta`, ni `LineaWhatsapp`, ni avisos de módulo, ni recordatorios de curso, ni configuración global.

Quien escribe «campaña» puede abrir el modelo que el menú ya no usa.

### 3.3 El plan de la organización no coincide con el manual

En `core/models/opciones.py`:

| Valor | Etiqueta en el formulario |
|---|---|
| `curso_asesor` | OP1 — 1 curso al mes + asesor (60 preguntas) |
| `dos_cursos` | OP2 — 2 cursos al mes + asesor (120 preguntas) |
| `asesor_60` | OP3 — asesor, 60 preguntas al mes |

`docs/EKI_UNFOLD_ADMIN.md` (sección Cliente) todavía dice `cursos` = OP2 sin asesor, `asesor` = OP3, y 30 preguntas en OP1. El formulario muestra las etiquetas del código. El manual no.

### 3.4 «Contenido» mezcla dos oficios

En el sidebar, Cursos y Módulos están junto a Conocimiento de agentes, Fichas del negocio, Derivaciones, Bandeja y Laboratorio. La skill `eki-ux` pide no mezclar aprendizaje con Nat.

### 3.5 Dos editores y dos fichas, con el interruptor apagado

- Module Builder (`EKI_MODULE_BUILDER_BETA`) y la ficha clásica de módulo.
- `ADMIN_CLIENTES_V2` elige `ClienteAdminV2`; apagado, sigue `ClienteAdmin`.
- `ADMIN_AGENTES_V2` igual, apagado salvo `?ui=v2` de superusuario.

No se prenden en este plan. El constructor nuevo es otro documento.

### 3.6 Sistema casi vacío

Con el catálogo de apps oculto, configuración global, auditoría, webhooks y PQRS solo aparecen si alguien sabe la URL. La paleta no los nombra. Infraestructura sí está en el sidebar.

## 4. Slices

Un slice por vez. Un cambio por commit. Esperar «continúa» antes del siguiente. Deploy solo con pedido explícito. Nada de webhook, cuerpo, motor, flags de línea ni flags de campaña.

### Slice 0 — Documentos que mienten

**Hecho el 8 de noviembre de 2026** (solo docs).

Solo docs.

- Corregir la tabla de planes en `docs/EKI_UNFOLD_ADMIN.md` para que coincida con `PLAN_CHOICES`.
- Marcar `docs/HOJA_RUTA_ADMIN_PORTAL.md` como historia de Jazzmin, con una línea al inicio que apunte a este plan y a `docs/EKI_UNFOLD_ADMIN.md`.
- Una frase en la guía Unfold: Líneas del menú = lectura de variables; Líneas de WhatsApp = alta en base, y hoy no manda porque `EKI_LINEAS_BD_ENABLED` está apagado.

Aceptación: quien lee el manual ve OP1/OP2/OP3 como el formulario. Ninguna pantalla cambia.

### Slice 1 — Menú y Ctrl+K

Archivos previstos: `mvp_project/unfold_admin.py`, `core/admin_command_search.py`, tests de admin Unfold que afirmen los títulos o la paleta si ya existen. Si no hay test de la paleta, uno corto que exija `CampanaMeta` y que `Campana` no sea el resultado de «campaña».

- Renombrar el ítem de solo lectura. Propuesta: «Estado de líneas». Sigue yendo a `/admin/lineas/`.
- Segundo ítem, «Líneas en base», al changelist de `LineaWhatsapp`. En la ficha, una descripción visible: con el flag apagado la fila no reemplaza a las variables.
- Paleta: sacar `core.Campana`. Meter `CampanaMeta`, `PlantillaMeta`, `LineaWhatsapp`, aviso de módulo, recordatorio de curso y configuración global. Cada atajo con una descripción de una línea. Si «campaña» tiene que mencionar la histórica, la descripción dice «Twilio, ya no se lanza».
- Partir la sección Contenido en «Cursos» (cursos, módulos) y «Asesoría» (conocimiento, fichas, derivaciones, bandeja, laboratorio).
- En Sistema, además de Infraestructura: configuración global y auditoría. El catálogo de todas las apps sigue oculto.

Aceptación:

- En el sidebar se distingue estado de líneas y alta en base.
- Ctrl+K con «campaña» abre Campañas Meta.
- «plantilla», «aviso» y «configuración» llegan a su pantalla sin conocer la URL.
- Contratos de línea: no aplican. `manage.py check` y los tests de admin Unfold que ya cubren el menú, en verde.

### Slice 2 — Organización

Archivo previsto: `core/admin/clientes.py` (fieldsets y descripciones). No registrar `ClienteAdminV2`. No migración.

- «Datos y logo» se queda en identidad: nombre, NIT, contacto, activo, logo, notas.
- El plan `plan_linea_meta` pasa a su pestaña, con la ayuda tomada de las etiquetas de `PLAN_CHOICES` (60 / 120 / solo asesor). Vacío sigue siendo el plan del servidor.
- La ayuda de WhatsApp nombra las dos pantallas del slice 1, no un solo «Líneas».
- WhatsApp avanzado sigue colapsado (phone id de la empresa, Twilio, secretos).

Aceptación: la primera pestaña no mezcla el plan OP con el logo. Un cliente vacío de plan se guarda igual que hoy.

### Slice 3 — Estudiante, solo lectura

Archivos previstos: columnas o un bloque de solo lectura en `core/admin/estudiantes.py`, más un test que no escriba estado.

- El listado muestra el estado de cada línea desde `EstadoLinea`.
- El campo compartido `estado_chat` queda etiquetado como espejo.
- No se cambia cómo se escribe el estado. E4 sigue esperando. La señal que copia a todas las filas no se toca en este slice.

Aceptación: abrir un estudiante no cambia filas. Las dos líneas se leen distintas cuando sus filas lo son.

## 5. Fuera de este plan

- Constructor de cursos y Module Builder.
- Portal, Aprende, Studio.
- Subir Unfold o cambiar el pin.
- Instalar django-unfold-extra, django-unfold-modal, la skill `unfold-admin`, o las skills de landings de la sección 0b (`frontend-design`, UI/UX Pro Max, taste-skill, motion).
- Prender `EKI_LINEAS_BD_ENABLED`, `EKI_CURSOS_POR_LINEA`, `ADMIN_CLIENTES_V2` o `ADMIN_AGENTES_V2`.
- E4 (dejar de escribir el estado viejo).
- Cualquier cambio en `_procesar_twilio_webhook_cuerpo`, puertas, campañas o envío.

## 6. Protocolo

Rama por slice desde `main`. Un cambio por commit. Al cerrar:

```
SLICE: <n>
Commits: <hashes + mensajes>
Archivos tocados / nuevos y estado en git: <lista>
Migraciones nuevas: ninguna
Resultado: check / makemigrations --check / tests del área
Contratos de línea: n/a
Riesgos o dudas: <lista>
```

Esperar «continúa» antes del siguiente slice. Deploy solo con pedido explícito.
