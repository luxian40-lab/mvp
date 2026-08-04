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
| Drag orden inlines | `ordering_field = "orden"` en Secciones/Pasos/Multimedia; `save_formset` + `core/orden_bloques.py` (temp + renúmero 1..n). ↑↓ siguen como respaldo |
| Base ops (Volver + shell) | `templates/admin/eki_ops_base.html` |
| Switcher tema en header | `templates/unfold/helpers/userlinks.html` |
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

Última actualización: 2026-07-31.
