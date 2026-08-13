# Referencias UX admin eki

Complemento de `SKILL.md`. No duplicar en cada respuesta; consultar al diseñar.

## Unfold (oficial)

- Docs índice: https://unfoldadmin.com/docs/
- Settings: https://unfoldadmin.com/docs/configuration/settings/
- ModelAdmin options: https://unfoldadmin.com/docs/configuration/modeladmin-options/
- Custom pages: https://unfoldadmin.com/docs/configuration/custom-pages/
- Dashboard callback: https://unfoldadmin.com/docs/configuration/dashboard/
- Components: https://unfoldadmin.com/docs/components/introduction/
- Demo: https://demo.unfoldadmin.com/
- Formula (código demo): https://github.com/unfoldadmin/formula

### Flags útiles ModelAdmin Unfold

- `compressed_fields` — formularios más densos
- `warn_unsaved_form` — evita perder cambios
- `list_fullwidth` / scrollbar horizontal — tablas anchas
- Inlines con `tab=True` — varias tablas sin scroll eterno
- Fieldsets `collapse` — avanzado oculto

## Dashboards (Carbon)

- https://carbondesignsystem.com/data-visualization/dashboards/
- Priorizar KPI por importancia; whitespace; menos paneles sueltos.
- Presentación vs exploración: CE “Hoy” = presentación; “Más datos” = exploración.

## eki paths

| Pieza | Path |
|-------|------|
| UNFOLD | `mvp_project/unfold_admin.py` |
| CSS | `static/admin/css/eki_admin_unfold.css` |
| Tonos Cielo/Marca/Noche | `static/admin/css/eki_admin_tones.css` + `eki_admin_tones.js` |
| Ops base | `templates/admin/eki_ops_base.html` |
| Inicio hub | `templates/admin/partials/eki_panel_exec.html` |
| Saludo Inicio | `core/templatetags/eki_admin.py` → `eki_admin_saludo` |
| CE body | `portal/templates/portal/partials/centro_exito_body.html` |
| Guía | `docs/EKI_UNFOLD_ADMIN.md` |

## Inicio + palette (canon UX)

Picker **Cielo / Marca / Oscuro** (skins; keys internas manana/tarde/noche). Saludo Inicio por hora local, tono empresa. Ver Diseñador `reference.md` § tonos.
