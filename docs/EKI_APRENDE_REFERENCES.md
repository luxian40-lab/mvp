# eki Aprende — referencias de producto y diseño

Canon para convertir **Aprende** (`aprende.eki.technology`) en un **producto LMS** de verdad: aula, tareas, ranking, biblioteca, evaluaciones — unido a **WhatsApp** (`*aula*` / `*listo*`), no un SSO aislado.  
**Studio** (`studio.eki.technology`) = vitrina / creador, **producto aparte**. No fusionar UI ni flujos Studio↔Aprende.

Complementa: `docs/EKI_STUDIO.md`, `docs/GUIA_PLATAFORMA_EKI.md`, `docs/EKI_UNFOLD_ADMIN.md` (solo admin).

Última actualización: 2026-07-31.

---

## 1. LMS open source / docs (aprendizaje de dominio)

Usar para **qué** construir (cursos, quizzes, competencias, certificados, gamificación, roles, learning paths, analytics) — no para copiar el stack.

| Fuente | Docs / código | Qué aprender |
|--------|---------------|--------------|
| **Moodle** ★★★★★ | https://docs.moodle.org/ · https://moodledev.io/ · https://github.com/moodle/moodle | Cursos, quizzes, competencias, certificados, gamificación, roles, plugins, learning paths, analytics |
| **Open edX** ★★★★★ | https://docs.openedx.org/ · https://github.com/openedx/edx-platform | Arquitectura LMS, sequences, blocks, progress, authoring |
| **Canvas LMS** ★★★★★ | https://canvas.instructure.com/doc/ · https://github.com/instructure/canvas-lms | UX LMS, flujos estudiante/profesor |
| **Chamilo** ★★★★★ | https://docs.chamilo.org/ · https://github.com/chamilo/chamilo-lms | LMS más simple que Moodle |
| **Sakai** ★★★★ | https://github.com/sakaiproject | Enfoque universidad |
| **H5P** ★★★★★ | https://h5p.org/documentation · https://github.com/h5p | Contenido interactivo |
| **LearnDash** ★★★★★ | https://learndash.com/support/ | Docs funcionales (no FOSS completo) |
| **TalentLMS** ★★★★★ | https://help.talentlms.com/ | Docs funcionales B2B |

### Documentación / knowledge (organizar contenido del producto)

| Fuente | URL |
|--------|-----|
| GitBook | https://github.com/GitbookIO |
| BookStack | https://github.com/BookStackApp/BookStack |
| Docusaurus | https://github.com/facebook/docusaurus |

---

## 2. Studio — creador / builder (no el aula)

Referencias para panel creador, formularios, permisos, editor visual:

| Proyecto | URL |
|----------|-----|
| Directus | https://github.com/directus/directus |
| Appsmith | https://github.com/appsmithorg/appsmith |
| Budibase | https://github.com/Budibase/budibase |
| NocoDB | https://github.com/nocodb/nocodb |

Aprenden: constructor, formularios, permisos, editor, builder.

---

## 3. Diseño visual — top 5 (obligatorias para el agente)

Si solo se pueden usar cinco fuentes para pantallas de Aprende:

1. **Material Design 3** — https://m3.material.io/ — layout, cards, nav, inputs, tabs, empty/loading, tablas, mobile/desktop  
2. **IBM Carbon** — https://carbondesignsystem.com/ — enterprise, dashboards, data tables, analytics  
3. **GitHub Primer** — https://primer.style/ — interfaces limpias, tablas, formularios  
4. **Mobbin** — https://mobbin.com/ — pantallas reales (Coursera, Duolingo, Canvas, Notion…)  
5. **Tabler** — https://github.com/tabler/tabler — dashboards HTML/CSS implementables  

### Otras fuentes fuertes

| Fuente | URL | Uso |
|--------|-----|-----|
| Microsoft Fluent 2 | https://fluent2.microsoft.design/ | Accesibilidad, paneles, formularios |
| Atlassian Design | https://atlassian.design/ | Apps complejas (Jira/Confluence-like) |
| shadcn/ui | https://ui.shadcn.com/ | Componentes (inspiración visual; stack eki = Django HTML/CSS) |
| Flowbite | https://flowbite.com/ · https://github.com/themesberg/flowbite | Pantallas / HTML |
| Tailwind UI | (referencia comercial) | LMS / dashboards / settings |
| Relume | https://www.relume.io/ | Layouts |
| Pageflows | https://pageflows.com/ | Flujos completos, no solo pantallas |
| Landbook / Lapa Ninja | https://land-book.com/ · https://www.lapa.ninja/ | Landings |
| HTML5 UP | https://github.com/ajlkn/html5up | HTML/CSS limpio |
| Bootstrap examples | https://github.com/twbs/examples | Ejemplos |
| AdminLTE | https://github.com/ColorlibHQ/AdminLTE | Dashboards |
| CoreUI | https://github.com/coreui/coreui | Admin UI |

---

## 4. Identidad eki (no copiar Notion/Linear a ciegas)

- Marca: **eki** minúsculas; accent `#9A6CAC` / `#7A4E8E`.
- Aprende = académico / territorio / B2B; sobrio, legible, móvil primero (3G mental model).
- Implementación: **Django templates + HTML/CSS** (como Tabler), no reescribir en React salvo decisión CTO.
- WhatsApp sigue siendo el canal de avance en campo; Aprende = estudio, tareas, reconsulta.

---

## 5. Cómo pedirle al agente (prompts útiles)

- Diseña una pantalla de tareas para Aprende.  
- Rediseña el dashboard del estudiante.  
- Mejora la biblioteca del curso.  
- Haz el flujo de evaluaciones.  
- Diseña un certificado moderno (página verify / PDF aparte).  
- Propón un mejor menú lateral.  
- Optimiza la experiencia móvil.

Respuesta esperada: propuesta con referencias M3/Carbon/Primer/Mobbin/Tabler **adaptadas a eki**, HTML/CSS viable en `aprende/templates/`.

---

## 6. Skills / reglas en el repo

| Pieza | Ruta |
|-------|------|
| Skill agente Aprende | `.cursor/skills/eki-aprende/SKILL.md` |
| Regla al tocar templates Aprende | `.cursor/rules/eki-aprende-product.mdc` |
| Skill diseñador (admin + marca) | `.cursor/skills/eki-designer/SKILL.md` |

---

## 7. Prioridad de producto (PM)

| # | Prioridad | Superficie Aprende | Estado |
|---|-----------|-------------------|--------|
| **A** | P1 | Shell estudiante: home Continuar, nav, empty, puente WA | Hecho |
| **B** | P1 | Flujo tareas (lista → entrega → 3 estados) | Hecho |
| **C** | P1 | Módulo de consulta legible + *listo* | Hecho |
| **D** | P2 | Profesor: entregas/calificaciones tipo tabla | Hecho (entregas) |
| **E** | P2 | Biblioteca + ranking polish / empty | Hecho |
| **F** | P3 | Quiz web + ruta + H5P embed | Hecho (práctica; *listo* sigue en WA) |
| — | P1 visual | Landing + login (auth WA intacta) | Hecho |

Deploy de UI Aprende: solo con pedido explícito; no mezclar WIP Celery/WhatsApp.
