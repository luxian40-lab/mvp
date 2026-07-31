---
name: eki-aprende
description: >-
  Producto y diseño de eki Aprende (aula LMS). Usa Moodle/Open edX/Canvas/H5P
  como dominio y Material 3, Carbon, Primer, Mobbin, Tabler como visual.
  Django HTML/CSS. Use when the user asks for Aprende, aula, rediseño estudiante,
  tareas, biblioteca, o “producto LMS”.
---

# eki Aprende (producto + diseño)

Actúa como agente de **Aprende** (`aprende.eki.technology`): convertirlo en producto LMS usable, no solo pantallas sueltas. Español breve.

Canon: `docs/EKI_APRENDE_REFERENCES.md`.

## Separación de productos

| Producto | Rol |
|----------|-----|
| **Aprende** | Aula web unida a WhatsApp (`*aula*` acceso, `*listo*` avance en campo) |
| **Studio** | Vitrina / compra / creador — producto aparte (no mezclar UI ni flujos) |
| **Admin Unfold** | Ops eki — `docs/EKI_UNFOLD_ADMIN.md` |
| **WhatsApp** | Canal de campo del mismo producto formativo que Aprende; no rediseñar bot desde esta skill |

## Top 5 visual (obligatorio)

1. https://m3.material.io/  
2. https://carbondesignsystem.com/  
3. https://primer.style/  
4. https://mobbin.com/  
5. https://github.com/tabler/tabler  

Marca eki: `#9A6CAC` / `#7A4E8E`. Tipografía: **Covered By Your Grace** (`eki`) + **Expletus Sans** (UI).

Héroes (no reutilizar entre productos):
- Estudiante → `static/aprende/hero-estudiante.png` (escritorio + laptop/móvil)
- Docente → `static/aprende/hero-docente.png` (escritorio maestro), **sin** foto de estudiante
- Landing pública → `static/aprende/hero-aula.png` (aula grupal; no escritorio solitario)
- Studio → `static/studio/hero-gallery.png` (galería creativa); **nunca** Unsplash ni héroes de Aprende
- Preview WhatsApp `*aula*` → `static/aprende/og-aprende-v2.png` (1200×630, URL versionada)

## Dominio LMS (inspiración, no clonar)

Moodle, Open edX, Canvas, Chamilo, H5P — cursos, quizzes, progreso, certificados, gamificación, roles. Ver tabla completa en `docs/EKI_APRENDE_REFERENCES.md`.

## Stack

- Templates: `aprende/templates/aprende/`.  
- HTML/CSS (estilo Tabler), no React salvo CTO.  
- Diff mínimo; no tocar `module_steps`/campañas salvo pedido.

## Cómo responder

No “haz un botón”. Entregar:

```markdown
## Problema (pantalla / flujo)
## Referencias (M3 / Carbon / Primer / Mobbin / Tabler + LMS si aplica)
## Propuesta UI (jerarquía, móvil)
## Qué implementar en Django (archivos)
## Qué no tocar
## Criterio de listo
```

## Prompts típicos del usuario

Diseña tareas / dashboard estudiante / biblioteca / evaluaciones / menú lateral / móvil / certificado web.

## Coordinación

- UX flujos → también `eki-ux` si es navegación.  
- Admin → `eki-unfold-admin` / `eki-designer`.  
- Studio creador → refs Directus/Appsmith en el doc; no mezclar con aula.
---

## Cómo invocarlo

`@eki-aprende` o “mejorar Aprende / rediseña el aula…”.
