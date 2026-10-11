# Module Builder — contrato de interfaz (Fase 0)

Fecha: 2026-10-11. Describe la UI y el POST **actuales**. No cambia comportamiento.

Fuente de verdad del POST: `core/views_module_builder.py` → `module_builder_view`.
Persistencia de campos: `core/module_builder_config.py` → `persistir_builder_desde_post`.
Estructura: `core/module_builder.py`.
Cliente: `static/admin/js/module_builder.js` (plantilla `core/templates/admin/module_builder.html`).

La plantilla ya extiende `admin/eki_ops_base.html`, que extiende `admin/base_site.html` de Unfold. La URL no cambia: `/admin/module-builder/<modulo_id>/`.

## Puerta de acceso

Staff (`@staff_member_required`) y, dentro de la vista, `module_builder_habilitado_para_curso`:

- `EKI_MODULE_BUILDER_BETA` encendido, o
- superusuario con `?builder=1` (GET o POST `builder=1`), o
- el curso está en `EKI_MODULE_BUILDER_CURSOS` (id, subcadena del nombre, o `*` / `all` / `todos`).

Si el usuario es staff y no pasa la puerta: `PermissionDenied` (HTTP 403).
Quien no es staff no llega a esa excepción: el decorador lo manda al login (302).

## Lo que el JavaScript usa

Si un reskin quita o renombra alguno de estos, el JS actual deja de guardar, ordenar o quitar media. El interruptor `EKI_MODULE_BUILDER_UI_V2=False` debe seguir sirviendo este HTML.

### Ids

| Id | Uso |
|----|-----|
| `eki-mb-shell` | Raíz. Si falta, busca `.eki-mb-shell`. |
| `eki-mb-csrf` | Token CSRF. Si falta, `[name=csrfmiddlewaretoken]` o cookie. |
| `eki-mb-builder-flag` | Si existe, el fetch añade `builder=1`. |
| `eki-mb-habilitado-fecha` | `input` fecha del drip. |
| `eki-mb-habilitado-hora` | `input` hora del drip. |
| `eki-mb-habilitado` | Hidden `name="modulo_habilitado_desde"`. El JS escribe aquí `YYYY-MM-DDTHH:MM`. |
| `eki-mb-habilitado-clear` | Botón que vacía la fecha. |
| `eki-mb-save-state` | Texto de estado (barra inferior). |
| `eki-mb-save-state-top` | El mismo texto arriba. |
| `eki-mb-publicar` | Enlace a publicar. Con cambios sin guardar recibe `eki-mb-sticky__pub--disabled`. |
| `eki-mb-sections` | Contenedor Sortable de secciones. |
| `eki-mb-panel` | Panel del paso. |
| `eki-mb-panel-placeholder` | Se oculta al elegir un paso. |
| `paso-<id>` | Fila del paso, para quitar media. |

`sessionStorage` clave `eki-mb-selected`: id del paso abierto. No es un campo POST.

### Clases que el JS lee o escribe

`eki-mb-shell`, `eki-mb__row`, `eki-mb__step-num`, `eki-mb__add-micro`, `eki-mb__upload-replace`, `eki-mb__add-sec`, `eki-mb__inline-form`, `eki-mb-save-trigger`, `eki-mb-track-dirty`, `eki-mb__activo-check`, `eki-mb__activo-hint`, `eki-mb__media-url`, `eki-mb-save-one`, `eki-mb__prob-link`, `eki-mb__row--highlight`, `eki-mb__sec`, `eki-mb__drag-handle--sec`, `eki-mb__sec--ghost`, `eki-mb__list`, `eki-mb__drag-handle--micro`, `sortable-ghost`, `eki-mb__badge`, `eki-mb__badge--warn`, `eki-mb__badge--bad`, `eki-mb__badge--ok`, `eki-mb-refresh-state`, `eki-mb-wa-preview__body`, `eki-mb-wa-preview__media`, `eki-mb__row-preview`, `eki-mb__row-preview--muted`, `eki-mb__row--selected`, `eki-mb__row-edit`, `is-panel-active`, `is-saving`, `eki-mb-preview-src`, `eki-mb__thumb`, `eki-mb-delete-media`, `eki-mb-sticky__pub--disabled`.

### data-*

| Atributo | Dónde |
|----------|--------|
| `data-paso` | Fila `.eki-mb__row`. Valor = id del paso. |
| `data-seccion` | `section.eki-mb__sec` y `ul.eki-mb__list`. |
| `data-paso-id` | Botones guardar uno, quitar archivo. |
| `data-paso-select` | Botón que abre el panel. |
| `data-paso-edit` | Bloque `.eki-mb__row-edit`. |
| `data-wa-preview` | Vista previa del paso. |
| `data-eki-mb-draft-clone` | Hiddens que el JS clona al enviar un formulario con cambios sucios. |
| `data-eki-mb-bypass` | El JS lo pone en `1` para no reentrar al submit. |
| `data-eki-mb-dirty` | En el shell: `1` si hay cambios sin guardar. |
| `data-publicar-url`, `data-n-problemas`, `data-publicado` | Están en el shell. El JS de hoy no los lee. |
| `data-step-type`, `data-preview` | Están en el HTML. El JS no lee el valor. |

### name de campos

El JS copia al POST todo `name` que empiece por `modulo_`, `seccion_` o `paso_`, con estas reglas:

- Checkbox: si está marcado manda su `value` (o `1`); si no, manda `0`.
- Radio: solo el marcado.
- `type=file` no se copia al fetch (el archivo va en el formulario multipart).
- En `replace_media` con cambios sucios: no copia `modulo_titulo`, no copia secciones, y los `paso_<id>_` solo del paso subido. Si hay cambios sucios añade `persist_general=1`.
- En añadir sección, añadir micro, duplicar o desactivar con cambios sucios: no copia `modulo_titulo`. Copia general solo si la página está sucia (`persist_general=1`).

Campos generales que el JS trata como bloque (`GENERAL_MODULO_FIELDS`):

`modulo_descripcion`, `modulo_modo_entrega`, `modulo_duracion_dias`, `modulo_habilitado_desde`, `modulo_facilitador_checkpoint`, `modulo_publicado_wa`, `modulo_examen_obligatorio`, `modulo_puntaje_minimo_aprobacion`.

Además, en cada guardado ajax (`save_modulo`): `modulo_titulo`, `seccion_<id>_titulo`, `paso_<id>_titulo`, `paso_<id>_contenido`, `paso_<id>_tipo_ui`, `paso_<id>_entrega`, `paso_<id>_activo`, `paso_<id>_clear_media`.

El guardado ajax **siempre** manda `modulo_habilitado_desde`, armado desde fecha + hora (hora por defecto `08:00`). Vacío si no hay fecha. Eso es el cliente de hoy: no hay pestañas, así que guardar el módulo también manda el calendario que está en la misma página.

Otros `name` de los formularios clásicos (no del fetch de guardar): `action`, `ajax`, `csrfmiddlewaretoken`, `builder`, `paso_id`, `seccion_id`, `orden`, `titulo`, `contenido`, `plantilla` (`mensaje` | `lectura` | `quiz`), `media_file`, `video_entrega` (`whatsapp` | `enlace`), `direction` (`up` | `down`, action `move_micro`; el HTML de hoy no tiene botones ↑↓, el arrastre usa `reorder_*`).

## Acciones

Todas son POST a la misma URL. `action` vacío o desconocida: mensaje «Acción no reconocida.» y redirect. No escribe.

Salvo que se indique JSON, la respuesta es **302** al builder (conserva `?builder=1` si venía en GET o POST). Errores de validación con `ajax=1`: JSON `{"ok": false, "error": "..."}` HTTP 400. Excepción no prevista con `ajax=1`: HTTP 500 y «No se pudo completar la acción. Revise los datos e intente de nuevo.»

| Action | Qué envía el cliente de hoy | Respuesta | Qué cambia en la base |
|--------|------------------------------|-----------|------------------------|
| `save_modulo` | Ajax: título, secciones, general (incluido drip), pasos. Opcional `paso_id` para limitar micros. | Ajax: `ok`, `partes`, `habilitado_desde`, `habilitado_desde_fecha`, `habilitado_desde_hora`. | Título si `modulo_titulo` viene y no está vacío (vacío con este action: error «El nombre del módulo no puede quedar vacío.»). Secciones `seccion_<id>_titulo`. General según claves presentes. Micros `paso_<id>_*`. |
| `save_modulo_meta` | Mismos campos que el guardado (la vista no lo distingue salvo el mensaje si no hubo partes). El JS de hoy no llama esta action; llama `save_modulo`. | Igual que `save_modulo`. Si no hubo partes: «Nombre del módulo actualizado». | Igual que `save_modulo`. |
| `rename_seccion` | `seccion_id`, `titulo`. **Return temprano:** no llama a `persistir_builder_desde_post`. | 302. Título vacío: «Escriba un nombre para la sección.» | Solo `SeccionModulo.titulo` (máx. 200). No toca drip ni micros. |
| `add_seccion` | `titulo`. Si la página está sucia, el JS clona el resto y `persist_general=1`. | 302 «Sección … creada.» | Nueva `SeccionModulo`. Antes, persiste pasos y títulos de sección; el título del módulo no; el general solo con `persist_general=1`. |
| `add_micro` | `seccion_id`, `titulo`, `contenido`, `plantilla` opcional, `media_file` opcional, `video_entrega` si hay video. | 302. Sin texto ni archivo: «Escriba texto o suba un archivo.» No crea el paso. | Nuevo `PasoModulo` al final de esa sección, orden contiguo. Plantilla `mensaje`/`lectura`/`quiz` sin texto ni archivo: borrador (`activo=False`) con texto de relleno. Con archivo: sube a S3 (`modulos/pasos`, prefijo `modulo_<id>`). Video async: `media_wa_apto` queda null hasta el worker. |
| `update_micro` | `paso_id`, `titulo`, `contenido`, `activo` opcional. El botón «guardar este paso» del JS **no** usa esta action: usa `save_modulo` con `paso_id`. | 302 «Micro guardado.» | Solo ese paso: título, contenido y, **si la clave `activo` viene**, el booleano. Activar sin texto ni `media_url`: no guarda y responde «Para activar el micro escriba texto o suba media (admin clásico / + contenido).» |
| `replace_media` | Multipart: `paso_id`, `media_file`, `video_entrega` opcional. El JS, si hay cambios sucios, clona solo el paso subido y puede añadir `persist_general=1`. No manda el título del módulo ni las secciones. | 302. Sin archivo: «Elegí un archivo para subir.» | `media_url`, `media_wa_apto` y, si es video, `video_entrega`. La subida de staff activa el paso. No pisa `Modulo.titulo` ni títulos de sección (`include_modulo_titulo=False`, `include_secciones=False`). Otros pasos no se tocan. |
| `delete_media` | `paso_id`. El JS manda `ajax=1`. | Ajax: `{ok, paso_id, media_url: ""}`. | Vacía `media_url` y `media_wa_apto`. El `contenido` queda. Limpia el cache de encode. |
| `set_video_entrega` | `paso_id`, `video_entrega` (`enlace` o cualquier otro → `whatsapp`). | 302. | Solo `PasoModulo.video_entrega`. |
| `move_micro` | `paso_id`, `direction` = `up` o `down`. No hay botón en el HTML actual. | 302. En el extremo: «Sin cambio (ya está al extremo).» Si el intercambio intercalaría secciones, revierte y error. | Intercambia `orden` con el vecino del módulo. |
| `reorder_micros` | `seccion_id`, `orden` = ids separados por coma, `ajax=1` desde el arrastre. | Ajax: `{ok: true, orden: {id: orden}}`. Si el conjunto de ids no es el de los activos de esa sección: HTTP 400. | Reordena solo dentro de la sección y renumera el módulo en bloques contiguos. Inactivos al final. |
| `reorder_secciones` | `orden` = ids de secciones activas, `ajax=1`. | Igual que el anterior. Conjunto distinto: HTTP 400. | Reordena secciones; los micros de cada una viajan juntos. |
| `deactivate_micro` | `paso_id`. | 302 «Micro desactivado (ya no se envía).» | `activo=False`. No borra el paso. |
| `duplicate_micro` | `paso_id`. | 302. | Copia justo después, `activo=False`, título con « (copia)». Mismo texto, media y entrega. |
| `encode_status` | `ajax=1`. | JSON `{ok: true, pasos: [{id, status, error, media_url, media_wa_apto}]}`. | **No escribe.** `status` es `pending`, `running`, `error` o vacío. No hay porcentaje. |

### Reglas que las pruebas fijan

1. **Drip.** `habilitado_desde` solo se escribe si el POST trae la clave `modulo_habilitado_desde` **y** la action es `save_modulo` o `save_modulo_meta`, o viene `persist_general=1`. Un POST sin esa clave no lo borra. Fecha ilegible con la clave presente: error y no se guarda el valor nuevo.
2. **Activo.** `paso_<id>_activo` ausente: ese paso no cambia de activo/inactivo. Presente y en `1`/`on`/`true`/`True`: activo. Otro valor (el JS manda `0` si el checkbox está apagado): inactivo.
3. **Activar** con `activo` verdadero, sin `contenido` y sin `media_url`: error, sin `save`.
4. **Orden.** Los activos quedan en bloques por sección. `reorder_micros` rechaza ids de otra sección. No se intercalan.
5. **`replace_media`** no cambia el título del módulo ni el de las secciones, aunque el POST los traiga.
6. **Action desconocida:** «Acción no reconocida.»
7. **Puerta:** staff sin flag, sin allowlist y sin `?builder=1` → 403.

Checkbox de publicado y examen: la clave tiene que venir. Si no viene, no se apaga. El JS de guardar siempre las manda (`1` o `0`).

`paso_<id>_entrega`: `manual` → `requiere_listo_para_avanzar=True`; `automatico` → `False`. Si la clave no viene, no cambia.

`paso_<id>_tipo_ui`: `quiz` pasa el paso a evaluación abierta si no lo era; `mensaje` devuelve una evaluación abierta a contenido. El resto de tipos no se toca.

`paso_<id>_clear_media=1` vacía media en el guardado de campos (además existe la action `delete_media`).

## Inventario de la página de hoy

### Encabezado

Nombre del módulo (`modulo_titulo`, id `eki-mb-modulo-titulo`). Curso y cliente en texto. Estado «Sin cambios / Sin guardar / Guardando… / Guardado». Botones Guardar (arriba y barra sticky) → `save_modulo` ajax. Enlace Publicar (`id="eki-mb-publicar"`) → `admin:core_modulo_publicar`, ruta `/admin/core/modulo/<id>/publicar/`.

Ese enlace es un GET que **publica en el acto** (`publicado_wa=True` si pasa el checklist). No abre una pantalla intermedia y no envía WhatsApp. En el guion de navegador no se sigue ese enlace sobre un curso real.

También: configuración avanzada, ficha del curso, admin clásico, archivos del módulo, Course Engine si hay curso.

### General (el `<details id="eki-mb-general">`, abierto)

| Campo en pantalla | name | Se guarda cuando |
|-------------------|------|------------------|
| Descripción | `modulo_descripcion` | Clave presente en `save_modulo` / `save_modulo_meta` / `persist_general=1` |
| Modo de entrega | `modulo_modo_entrega` | Igual, y el valor está en `Modulo.MODOS_ENTREGA` |
| Publicado en WhatsApp | `modulo_publicado_wa` | Solo si la clave viene |
| Duración (días) | `modulo_duracion_dias` | Si es un entero ≥ 0 |
| Checkpoint facilitadora | `modulo_facilitador_checkpoint` | Si el valor está en las choices del modelo |
| Examen obligatorio | `modulo_examen_obligatorio` | Solo si la clave viene |
| Puntaje mínimo | `modulo_puntaje_minimo_aprobacion` | Entero 0–100 |

### Calendario y drip (mismo panel, no es pestaña)

1. **Fecha del módulo.** Editable. Hidden `modulo_habilitado_desde`. Inputs de fecha y hora sin `name` (el JS compone el hidden). Vacío borra la fecha solo en guardado explícito. Texto de ayuda: antes de esa fecha nadie recibe el módulo al avanzar.
2. **Ritmo del curso.** Solo lectura: `curso.dias_espera_entre_modulos` («N día(s) después de listo» o «Inmediato con listo») y enlace a la ficha del curso.
3. **Drip de la empresa del curso.** Solo si existe `HabilitacionModuloDripCliente` activo para el cliente del curso, el curso y el módulo. Muestra una fecha. No lista otras organizaciones.
4. Enlaces: ficha del cliente («Habilitación por cliente»), `/admin/drip-estudiantes/?cliente=<id>`, y avanzado.

No hay buscador de estudiante ni conteo de `HabilitacionModuloEstudiante`. Esas capas, en la Fase 3, necesitan contexto de solo lectura en la vista. Hoy no está en el template.

### Estructura

Secciones con arrastre (manija `.eki-mb__drag-handle--sec`) y campo `seccion_<id>_titulo`. Lista de pasos: número de orden, tipo (`paso_builder_ui`: Video, Mensaje WA, Quiz, Lectura), entrega («Espera respuesta» / «Automático»), borrador, semáforo de media, duplicar, desactivar. Arrastre de pasos solo dentro de su lista (`pull: false`).

Añadir: «+ Mensaje», «+ Lectura», «+ Quiz» (plantillas, quedan inactivas) o formulario con título, texto y archivo. Vídeo nuevo: radios `video_entrega` whatsapp (marcado) o enlace. «Añadir sección».

`paso_builder_ui` no distingue Imagen, Audio ni Documento: imagen y archivo salen como «Lectura». Esa función está en `core/module_builder.py` (no se toca en este reskin). La etiqueta nueva puede calcularse en la plantilla a partir de la URL, manteniendo `data-step-type` si el CSS lo usa.

### Editor del paso (panel)

Título interno, texto, radios tipo mensaje/quiz, radios entrega automática/manual, miniatura y URL, checkbox quitar archivo, formulario reemplazar archivo, radios de entrega de vídeo si ya hay vídeo, checkbox activo, «Guardar este paso» (`save_modulo` + `paso_id`), «Refrescar estado» (`encode_status`). Vista previa local: el texto del textarea; si hay archivo, la nota de media. No envía WhatsApp.

Avisos de la página: problemas de media (enlace al paso), secciones intercaladas, borradores, y el diagnóstico de estructura.

## Choques con el diseño pedido (no improvisar)

1. **Unfold 0.102.0.** El repo fija `django-unfold==0.91.0` (`requirements.txt`). La regla de admin pide no subir de 0.91.x mientras Elastic Beanstalk siga en Python 3.11. La Fase 1 puede heredar el shell 0.91 que ya usa la página. Subir a 0.102.0 es un cambio de plataforma, no de esta plantilla.
2. **Publicar.** `#eki-mb-publicar` apunta a `admin:core_modulo_publicar` (`/admin/core/modulo/<id>/publicar/`). El GET muestra el checklist y el botón. El POST, con CSRF, es el que pone `publicado_wa=True` si el checklist pasa. No envía WhatsApp.
3. **Guardar General sin calendario.** El servidor ya no toca el drip si falta la clave. El JS de hoy **siempre** la envía, porque fecha y general están en la misma página. Las pestañas nuevas tienen que omitir `modulo_habilitado_desde` al guardar solo General. No hace falta cambiar la vista.
4. **Texto junto al archivo.** El ensamblado de un paso (`partes_mensaje_paso`) sí mete el texto del paso como pie del mismo `[MEDIA:]` cuando el paso tiene las dos cosas. Ver `docs/MODULE_BUILDER_DIAGNOSTICO_ENVIO.md`. La UI nueva puede dejar de ofrecer «texto que acompaña» sin cambiar ese envío. Los pasos viejos con texto y archivo se conservan.
5. **Capas de drip que la página no lee.** Lista de organizaciones y personas habilitadas a mano no están en el contexto. Hace falta un OK para pasarlas en solo lectura desde `views_module_builder.py`.
6. **`move_micro`** existe y se prueba. La página de hoy ordena con arrastre (`reorder_micros` / `reorder_secciones`). Los botones subir/bajar de la Fase 2 pueden llamar a `move_micro` sin action nueva.
7. **`encode_status` no trae porcentaje.** La Fase 5A, en «Preparando», tiene que mostrar actividad y tiempo, no un porcentaje inventado.

## Consultas de la página (antes)

Medido con el cliente de pruebas, módulo de 10 secciones y 2 mensajes cada una (20 pasos), curso sin organización, staff, flag encendido: **8 consultas** en el GET (`test_get_diez_secciones_once_consultas`). No hay una consulta por paso ni por sección. Si el curso tiene cliente, la vista suma una: `HabilitacionModuloDripCliente` de esa empresa. El «después» se mide cuando exista la UI nueva, con el mismo caso.

## Fase 1 (interruptor)

`EKI_MODULE_BUILDER_UI_V2` sale apagado. Apagado: el HTML de siempre, `module_builder.css` y `module_builder.js`, sin botones de mover y con la etiqueta de `paso_builder_ui`. Encendido: el mismo shell Unfold, la hoja `module_builder_v2.css` (variables `--color-primary-*` y `--color-base-*`, que Cielo, Marca y Oscuro ya reescriben), la etiqueta de pantalla Texto / Imagen / Video / Audio / Documento (el `data-step-type` sigue saliendo de `paso_builder_ui`) y botones Subir / Bajar que hacen POST `action=move_micro` con `direction=up|down`.

Con el interruptor encendido el GET añade, en solo lectura, `drip_organizaciones`, `drip_personas_conteo` y `drip_orgs_lista_blanca`. Apagado, esas claves no están y el GET de 10 secciones sigue en 8 consultas.

## Fase 2 (tres paneles)

Con el interruptor encendido la página muestra la ruta Cursos › curso › módulo, las pestañas Contenido, General y Calendario y drip, la estructura a la izquierda, el editor y la vista previa a la derecha. En pantallas estrechas aparece la pestaña Vista previa.

Guardar (Contenido o General) no envía `modulo_habilitado_desde`. Solo el botón Guardar calendario lo envía. El JS mira la clase `eki-mb-shell--v2`: apagado, el guardado sigue mandando la fecha como hoy.

`+ Texto antes` y `+ Texto después` hacen POST `add_micro` con plantilla mensaje. `agregar_micro` siempre inserta al final de la sección; no hay posición en esa action. La persona lo deja al lado con Subir o Bajar. Un mensaje que ya tiene texto y archivo no se parte: se muestra la etiqueta «Texto + archivo» y, en la vista previa, dos burbujas.

## Fase 3 (calendario, solo lectura)

La pestaña Calendario muestra la fecha del módulo (la única que guarda este editor), la fecha por organización, el conteo de personas habilitadas a mano y el ritmo del curso. «Probar con una persona» es un GET: busca por nombre, organización o teléfono, nunca por cédula, y no escribe. El veredicto dice «Hoy recibe este módulo» o «Hoy no recibe este módulo», nombra la capa que ya decidió `modulo_disponible_por_calendario` y muestra el texto de `mensaje_bloqueo_avance_siguiente_modulo` si hoy escribiera listo.

## Puerta ?ui=v2

Con `EKI_MODULE_BUILDER_UI_V2` en False, la interfaz nueva solo entra si el usuario es superusuario y la URL trae `ui=v2`. Staff sin ser superusuario no puede activarla.

## Publicar con confirmación

La interfaz nueva apunta a `admin:core_modulo_publicar_confirmar` (`/admin/core/modulo/<id>/publicar/confirmar/`). GET no escribe. POST con CSRF publica. `core_modulo_publicar` queda igual para la interfaz de hoy y se retira después.

## Subida

La interfaz nueva manda el mismo multipart `replace_media`, con progreso en el navegador. Componente: `static/js/media-uploader/`. Validación de tipo y tamaño: `core/media_upload_servicio.py` (no está en `core/services/` porque ese archivo ya es el de campañas). Contrato: `docs/MEDIA_UPLOADER.md`.
