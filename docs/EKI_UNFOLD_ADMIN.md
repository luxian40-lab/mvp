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
| CSS módulo WhatsApp bloques | `static/admin/css/modulo_whatsapp_bloques.css` |
| Alta módulo (plantilla) | `sembrar_plantilla_modulo` en `core/admin/cursos.py` — 1 bloque + N microcontenidos inactivos; default modo Pasos; inlines con `tab=True` (Estructura / Microcontenidos / Multimedia legacy / Examen) |
| **Module Builder WA** | `/admin/module-builder/<id>/` · flag `EKI_MODULE_BUILDER_BETA` (local ON, **prod OFF** salvo env `=1`) · vista `core/views_module_builder.py`, lógica `core/module_builder.py`, template `core/templates/admin/module_builder.html`, CSS/JS `static/admin/{css,js}/module_builder.*` · `docs/MODULE_BUILDER_WA.md` |
| Entradas al Builder | Columna **Builder** en listado Módulos + botón detalle **Module Builder** (`actions_detail` Unfold en `ModuloAdmin`) + enlace en guía pestaña Clase |
| Drag Builder (rieles) | SortableJS: micros solo dentro de su sección + reordenar secciones enteras; POST `reorder_micros` / `reorder_secciones`; valida anti-intercalado (`core/module_structure.py`). ↑↓ como respaldo |
| Drag orden inlines (clásico) | `ordering_field = "orden"` en Secciones/Pasos/Multimedia; `save_formset` + `core/orden_bloques.py` (temp + renúmero 1..n). ↑↓ siguen como respaldo |
| **Tonos admin** (Mañana/Tarde/Noche) | Dropdown `palette` en el nav: `templates/unfold/helpers/eki_tone_switch_dropdown.html`; estilos `static/admin/css/eki_admin_tones.css`; lógica `static/admin/js/eki_admin_tones.js` (`html[data-eki-tone]`, persiste `localStorage`). Noche = carbón cálido (ojos) |
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

## Cambios recientes (2026-08-07 · deploy `main-20260807-185849`)

Desplegado a `eki-prod-final` (Health Green, `/health/` 200). Sin migración de datos salvo el campo aditivo `PasoModulo.media_wa_apto` (migración `0131`).

- **Campañas** — lenguaje de producto (Mensaje inicial / Plantilla / Participantes / Resultados) + ficha resumen del lanzamiento arriba del change form. Mismo motor de envío (Content SID / Twilio interno).
- **Certificados** — biblioteca: miniatura en lista, “Usada en X cursos”, Duplicar y Generar certificado de prueba (descarga). Preview lateral intacto; se distingue **plantilla** (diseño) de **certificado emitido**.
- **Module Builder WA** — código en prod pero **OFF** (`EKI_MODULE_BUILDER_BETA` no seteado ⇒ `False` en `settings_production`). Los módulos vivos siguen en el admin clásico; el Builder no reescribe cursos existentes. Añade drag con rieles + miniaturas de media.
- **Tonos admin** — Mañana / Tarde / Noche en el nav (icono `palette`), aplican a todo Unfold; Noche pensado para descanso visual.

**Encender el Builder en prod (piloto):** setear env `EKI_MODULE_BUILDER_BETA=1` en EB, o `?builder=1` como superusuario. Recomendado solo tras QA en 1–2 módulos no críticos.

Última actualización: 2026-08-07.
