# eki × django-unfold — guía admin

Documento de referencia para **mejoras y cambios solo del admin** (`admin.eki.technology`).  
No aplica a WhatsApp, portal B2B, Studio ni Aprende salvo que el cambio sea una plantilla bajo `/admin/`.

## Fuente oficial

Documentación Unfold (índice):

**https://unfoldadmin.com/docs/**

Secciones usadas con frecuencia:

| Tema | URL |
|------|-----|
| Settings / `UNFOLD` | https://unfoldadmin.com/docs/configuration/settings/ |
| Site dropdown | https://unfoldadmin.com/docs/configuration/site-dropdown/ |
| Custom pages | https://unfoldadmin.com/docs/configuration/custom-pages/ |
| Dashboard | https://unfoldadmin.com/docs/configuration/dashboard/ |
| ModelAdmin options | https://unfoldadmin.com/docs/configuration/modeladmin-options/ |
| Tabs / inlines / filters / actions | índice en docs |
| Components (Card, Chart, Table, Tracker…) | https://unfoldadmin.com/docs/components/introduction/ |
| Demo | https://demo.unfoldadmin.com/ |

Regla Cursor (auto al tocar archivos admin): `.cursor/rules/eki-unfold-admin.mdc`.

## Dónde está en eki

| Pieza | Ruta |
|-------|------|
| Config `UNFOLD` | `mvp_project/unfold_admin.py` |
| CSS marca / cajas | `static/admin/css/eki_admin_unfold.css` |
| Jump sticky módulos | `static/admin/js/eki_modulo_jump.js` |

### Invariante P0 — tabs Unfold vs jump JS

Unfold muestra los **fieldsets** solo con Alpine `activeTab == 'general'`. Los tabs de fieldset (`classes: ['tab']`, p. ej. «Clase») usan `activeFieldsetTab`, **no** el `activeTab` del body.

Si `eki_modulo_jump.js` pone `activeTab = 'clase'`, el alta/edición queda **en blanco** (intro + Grabar, sin campos). Regla: primary = `general` | slug de inline (`pasos`, …). Failsafe CSS: `eki_admin_unfold.css` (`:has([data-eki-modulo-add])`). Test: `test_jump_js_no_pone_active_tab_clase_como_primary`.

| Pieza | Ruta |
|-------|------|
| CSS módulo WhatsApp bloques | `static/admin/css/modulo_whatsapp_bloques.css` |
| Alta módulo (plantilla) | `sembrar_plantilla_modulo` en `core/admin/cursos.py` — 1 bloque + N microcontenidos inactivos; default modo Pasos; inlines con `tab=True` (Estructura / Microcontenidos / Multimedia legacy / Examen) |
| **Module Builder WA** | `/admin/module-builder/<id>/` · flag `EKI_MODULE_BUILDER_BETA` (local ON; prod OFF salvo `=1`) · allowlist `EKI_MODULE_BUILDER_CURSOS` default `*` · vista `core/views_module_builder.py`, lógica `core/module_builder.py`, template `core/templates/admin/module_builder.html`, CSS/JS `static/admin/{css,js}/module_builder.*` · `docs/MODULE_BUILDER_WA.md` |
| Entradas al Builder | Columna **Builder** + botón detalle + enlace guía Clase + **redirect tras crear/guardar módulo** |
| Drag Builder (rieles) | SortableJS: micros solo dentro de su sección + reordenar secciones enteras; POST `reorder_micros` / `reorder_secciones`; valida anti-intercalado (`core/module_structure.py`). ↑↓ como respaldo |
| Drag orden inlines (clásico) | `ordering_field = "orden"` en Secciones/Pasos/Multimedia; `save_formset` + `core/orden_bloques.py` (temp + renúmero 1..n). ↑↓ siguen como respaldo |
| **Tonos admin** (Cielo / Marca / Oscuro) | Dropdown `palette` en el nav: `templates/unfold/helpers/eki_tone_switch_dropdown.html`; estilos `static/admin/css/eki_admin_tones.css`; lógica `static/admin/js/eki_admin_tones.js` (`html[data-eki-tone]`, persiste `localStorage`). Keys: manana / tarde / noche. Cielo **no** recolorea todos los `<a>`. |
| **Campañas** (lanzar curso) | `CampanaAdmin` en `core/admin/campanas.py`; tabs con lenguaje de producto (**Mensaje inicial** / **Plantilla** / **Resultados**, no “Twilio”); ficha resumen arriba `templates/admin/core/campana/change_form.html` |
| **Certificados** (biblioteca) | `PlantillaCertificadoAdmin` en `core/admin/certificados.py`; listado con **miniatura** + **Usada en**; **Duplicar** (acción lista + `actions_detail`); **Generar certificado de prueba** (descarga PNG, ruta `prueba-descarga/`); preview lateral en `templates/admin/learning/plantillacertificado/change_form.html` |
| Base ops (Volver + shell) | `templates/admin/eki_ops_base.html` |
| Switcher tema en header | `templates/unfold/helpers/userlinks.html` (Light/Dark/System de Unfold + `palette` de tonos eki) |
| ModelAdmin Unfold | `core/admin/_common.py` |
| Infra monitor (ejemplo custom page) | `core/templates/admin/infra_monitor.html` → `/admin/infra/` |
| Infra advisor (reglas + email ACTUAR) | `core/infra_monitor.py` (`build_infra_advisor`) · task `core.tasks_infra.revisar_infra_advisor` cada 30 min |

## Plataforma

- Prod EB: `eki-prod-final`, **Python 3.11**.
- Pin: **django-unfold 0.91.x** (versiones nuevas pueden pedir ≥3.12).
- Theming nativo: `COLORS`, `BORDER_RADIUS`, light/dark/auto. Sin galería Jazzmin.
- “Unfold Studio” en la web de Unfold es un **plugin comercial de theming** — no confundir con **eki Studio** (`studio.eki.technology`).

## Cómo mejorar el admin (orden preferido)

1. Leer la doc oficial del feature (tabs, filters, custom pages, components).
2. Cambiar `unfold_admin.py` y/o template/CSS admin — no el monolito de envío.
3. Pantallas custom → heredar `eki_ops_base` / shell Unfold; UI tipo cards + datos claros (ej. infra).
4. Tests: `core.tests_unfold_admin_*`, `core.tests_infra_monitor`, listados, etc.
5. Deploy solo con pedido explícito; no mezclar WIP Celery/`module_steps`.

## Roles

- **UX** (`.cursor/skills/eki-ux`): flujos y navegación admin.
- **Diseñador** (`.cursor/skills/eki-designer`): tipografía, color, cajas.
- **CTO** (`.cursor/skills/eki-cto`): pin de versión, no reescritura.
- **Dev** implementa; **QA** smoke admin si toca más que CSS.

## Operación vigente (1 octubre 2026)

Deploy en prod: `main-agentes-fallback-20261001-171500`. El mapa de producto (planes, menú, agentes, ficha) está en `docs/GUIA_PLATAFORMA_EKI.md` §26. Aquí solo está **dónde se toca en el admin**.

### Cliente — plan de la línea Meta

`Cliente.plan_linea_meta` está en el bloque **Datos y logo** (siempre visible, no en una pestaña escondida) y es columna del listado.

| Valor | Producto |
|-------|----------|
| vacío | Usa el plan del servidor (`LINEA_META_PLAN_DEFAULT`, hoy OP1) hasta que se asigne uno. |
| `curso_asesor` | OP1: 1 curso al mes y 30 preguntas al asesor. |
| `cursos` | OP2: 2 cursos al mes, sin asesor. |
| `asesor` | OP3: solo asesor, 60 preguntas al mes. |

### Grupo — el mismo cliente con planes distintos

`GrupoEstudiantes.plan_linea_meta` está en **Información del Grupo**, en el listado y en el filtro. Vacío = plan del cliente. Si la persona está en dos grupos con plan, gana el más nuevo (`fecha_creacion`, luego id). Un grupo inactivo no pisa al cliente. La suscripción vencida del cliente también apaga el plan del grupo.

Override por una sola persona: Sesiones menú sandbox → `plan`. Ese gana sobre el grupo.

### Curso — carrusel de Formación

En **Datos del curso**, checkbox **En el menú de Formación** (`catalogo_menu`), también filtro del listado.

- Curso general (`cliente` vacío) nuevo: queda marcado al crearlo.
- Para sacarlo del carrusel: desmarcar. No hace falta deploy.
- Cursos de un cliente no salen en el carrusel de todo el mundo.
- Máximo 10 tarjetas por mensaje de WhatsApp. Del 11 en adelante sale un segundo carrusel.
- La imagen es la portada https del primer módulo. Si no hay, una imagen fija de respaldo.

Los cursos generales creados antes de esta regla hay que revisarlos una vez en el listado (filtro del checkbox) y marcar los que deban verse.

### Insignias de racha

Admin → insignias, tipo **RACHA**, activas. Hitos sembrados: 3, 7, 14, 21 y 30 días. El texto de la insignia **no lleva emoji**. El 🔥 lo pone el sistema solo en la línea de la racha, dentro del primer mensaje del día en la línea Meta. Twilio no acumula esa racha.

### Entrenar agentes

Conocimiento de agentes: lo **aprobado** entra al prompt de Nat, Lina, Profe IA o Ventas sin deploy. Una conversación puede dejar una fila **sugerida**; no se usa hasta aprobarla. No pegar teléfonos ni correos en el texto.

### Ficha Preserva (formulario GEI)

Formularios → tipo de formulario → `meta_flow_id`.

- Vacío: al iniciar la ficha en Meta se intenta publicar el Flow y guardar el id.
- Con id: se reutiliza ese formulario de WhatsApp.
- Para republicar después de cambiar preguntas: borrar el id y volver a disparar la ficha.
- Hoy en el servidor **falta** `WHATSAPP_BUSINESS_ACCOUNT_ID`, así que el botón *Llenar ficha* no se publica y la persona responde en el chat. El chat es el respaldo, no un error del tipo de formulario.

### Inicio

El panel (`templates/admin/partials/eki_panel_exec.html`) titula **Ecosistema eki**. Studio y Aprende se dibujan como productos aparte. El saludo usa el nombre del staff.

## Cambios recientes (2026-08-07 · deploy `main-20260807-185849`)

Desplegado a `eki-prod-final` (Health Green, `/health/` 200). Sin migración de datos salvo el campo aditivo `PasoModulo.media_wa_apto` (migración `0131`).

- **Campañas** — lenguaje de producto (Mensaje inicial / Plantilla / Participantes / Resultados) + ficha resumen del lanzamiento arriba del change form. Mismo motor de envío (Content SID / Twilio interno).
- **Certificados** — biblioteca: miniatura en lista, “Usada en X cursos”, Duplicar y Generar certificado de prueba (descarga). Preview lateral intacto; se distingue **plantilla** (diseño) de **certificado emitido**.
- **Module Builder WA** — allowlist prod default `*` (todos los cursos) aunque `EKI_MODULE_BUILDER_BETA` siga OFF. Tras crear/guardar módulo se abre el Builder. El admin clásico sigue disponible. Drag con rieles + miniaturas de media.
- **Tonos admin** — Cielo / Marca / Oscuro en el nav (icono `palette`), aplican a todo Unfold; Oscuro = carbón + Unfold `dark`. Cielo pisa primary a azul **sin** recolorear todos los links (contraste sidebar/CTAs).

**Restringir Builder en prod:** `EKI_MODULE_BUILDER_CURSOS=impulso joven rural` (coma-sep) o allowlist vacía + beta OFF. Superusuario: `?builder=1`.

Última actualización: 2026-10-01.
