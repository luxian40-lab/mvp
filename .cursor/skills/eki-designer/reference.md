# Referencias diseño visual eki

## Sistemas

| Sistema | URL | Uso eki |
|---------|-----|---------|
| Unfold | https://unfoldadmin.com/docs/ | Admin |
| Carbon dashboards | https://carbondesignsystem.com/data-visualization/dashboards/ | KPI / CE / Learning |
| Material 3 | https://m3.material.io/ | Aprende (con Tabler) |
| Primer | https://primer.style/ | Densidad / patrones |
| Tabler | https://tabler.io/ | Aprende UI kit |
| Mobbin | https://mobbin.com/ | Inspiración flujos (no copiar) |

## Tipografía marca

- Covered By Your Grace → solo palabra `eki`
- Expletus Sans → títulos UI de producto
- Admin Unfold: tipografía del tema + contraste en `eki_admin_unfold.css`

## Color

```
--eki-accent: #9A6CAC
--eki-accent-deep: #7A4E8E
--eki-accent-ink: #5F3A6E
```

Alinear `UNFOLD["COLORS"]["primary"]` con estos valores; no introducir otra familia púrpura.

## Inicio (`/admin/`) y tonos mañana/tarde/noche

**Obligatorio mirar** al tocar admin visual: [`templates/admin/partials/eki_panel_exec.html`](templates/admin/partials/eki_panel_exec.html) + [`static/admin/css/eki_admin_tones.css`](static/admin/css/eki_admin_tones.css) + [`static/admin/js/eki_admin_tones.js`](static/admin/js/eki_admin_tones.js) + dropdown [`templates/unfold/helpers/eki_tone_switch_dropdown.html`](templates/unfold/helpers/eki_tone_switch_dropdown.html).

Estado actual (canon UI):

| Label UI | Key CSS | Skin |
|----------|---------|------|
| **Cielo** | `manana` | Azul operativo: reescribe `--color-primary-*` Unfold + fondo `#dceef8` |
| **Marca** | `tarde` (default) | Lavanda eki `#9A6CAC` + fondo `#f0eef3` |
| **Oscuro** | `noche` | Carbón + Unfold `dark` |

Cielo ≠ Marca: si Cielo no pisa `--color-primary-*`, Unfold queda morado y los dos skins se ven iguales.

Saludo Inicio: formal por **hora local** (`Buenos días/tardes/noches, {nombre}`); subtítulo operativo (no frases motivacionales casuales). Ver `core/templatetags/eki_admin.py`.

No inventar 4ª paleta. No volver a labels Mañana/Tarde/Noche.

## Assets fijos

| Producto | Hero / OG |
|----------|-----------|
| Aprende estudiante | `static/aprende/hero-estudiante.png` |
| Aprende docente | `static/aprende/hero-docente.png` |
| Aprende landing | `static/aprende/hero-aula.png` |
| Studio | `static/studio/hero-gallery.png` |
| OG aula WA | `og-aprende-v2.png` 1200×630 |

## Certificados

Preferir `modo_plantilla=diseno_eki` (`core/certificado_diseno_eki.py`).  
Comando: `manage.py asegurar_plantilla_certificado_default`.
