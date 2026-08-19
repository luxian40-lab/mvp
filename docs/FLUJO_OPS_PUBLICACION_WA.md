# Flujo ops — publicación WA por dominio admin

Guía para staff eki **después del commit publicación WA** (`publicado_wa`, gate runtime, semáforos).  
**Sin deploy a prod** hasta autorización explícita + migración `0134_modulo_publicado_wa`.

## Resumen en una línea

**Captar** no lanza sin M1 publicado · **Enseñar** publica módulo a módulo · **Retener** mide y certifica solo sobre lo publicado · **Capital Humano / Clases** no pasa por gate WA.

---

## Captar

| Pieza | Qué hace |
|-------|----------|
| Bloqueo campaña | No se puede lanzar campaña de curso si **M1 no está `publicado_wa`** |
| Chip Inicio | **Módulos borrador (N)** — atajo al listado filtrado |
| Manual | §**Publicación WA** en `/admin/instrucciones/` |
| Command palette | `borrador`, `publicar`, `manual` (Ctrl+K) |

**Checklist antes de campaña**

1. Curso → semáforo verde en M1 (o publicar desde Module Builder).
2. Inicio: chip borradores = 0 para ese curso (o revisados a propósito).
3. Campaña → guardar; si M1 borrador, error claro en admin (no error Twilio al estudiante).

---

## Enseñar

Flujo recomendado:

```
Curso (semáforo) → Module Builder → Publicar módulo → [opcional] drip encima
```

| Estado | Estudiante WA | Admin |
|--------|---------------|-------|
| Módulo borrador | Mensaje amable tipo drip (“contenido en preparación”); **no** media Twilio | Badge borrador, botón Publicar |
| Módulo publicado | Avance normal; media si pasos OK | Semáforo verde |
| Drip activo | Ventana horaria/día encima de publicación | Sin cambio en gate |

**Reglas de avance**

- Orden **estricto** M1 → M2 → … — no saltar M2 borrador para llegar a M3.
- `% avance` y métricas usan solo módulos **publicados**.
- Retos/checkpoints y cierre certificado: solo módulos publicados.

**Module Builder**

- Crear/editar contenido en borrador.
- Publicar cuando QA interno OK (media, pasos, examen).

---

## Retener

| Pieza | Estado |
|-------|--------|
| Mapa cobertura | Leaflet arreglado (`fitBounds`, `invalidateSize`) — Inicio + `/admin/cobertura/` |
| Certificados pend. WA | Insight Inicio + envío masivo `/admin/envio-certificados/` |
| Fallidos / 63019 | Command palette: `63019`, `fallido` → WhatsappLog / EnvioLog filtrados |
| Estudiantes sin progreso | Palette: `sin progreso` |

---

## Capital Humano / Aprende (modo Clases)

- Cursos con **`es_modo_clases()`** → **exentos** del gate `publicado_wa`.
- Flujo aula Aprende **sin cambio**; publicación WA es concepto WhatsApp curso.
- Certificados presenciales / Capital Humano siguen su servicio (`certificado_presencial_service`).

---

## Command palette (Ctrl+K / barra sidebar)

Atajos útiles:

| Escribir | Va a |
|----------|------|
| `manual` | Instrucciones ops |
| `borrador` | Módulos sin publicar WA |
| `publicar` | Manual §Publicación WA |
| `63019` / `63021` | WhatsappLog media |
| `certificado` | Envío certificados |
| Teléfono (≥7 dígitos) | Conversación + ficha estudiante |
| Nombre estudiante | Hasta 5 resultados |

**Fix búsqueda (local, pendiente deploy):** `search_models` acotado a modelos core ops — antes `True` escaneaba todo el admin y podía devolver **500** (p. ej. modelos Aprende), dejando la palette “muerta” al escribir.

---

## Backlog P2 / P3 (sin implementar)

### P2 — alto impacto ops

| Idea | Beneficio |
|------|-----------|
| Wizard “¿Cuántos módulos?” al crear curso | Evita cursos vacíos / drip sobre shell |
| % Inicio panel con `publicado_wa` | KPI honesto vs borradores |
| Alerta campaña programada + borradores | Push antes del disparo |
| Filtro curso “listo para campaña” | M1 publicado + ≥1 paso con media OK |
| Bulk “Publicar M1…Mn” desde curso | Menos clics Module Builder |
| Notificación Slack/email módulo borrador en curso activo | Ops proactivo |

### P3 — confort / escala

| Idea | Beneficio |
|------|-----------|
| Login SSO (Google workspace eki) | Menos fricción staff |
| Sidebar search: resultados recientes por rol | Captación vs Retención |
| Semáforo media WA en listado pasos | Prevenir 63019 antes de publicar |
| Diff “qué cambió al publicar” | Auditoría pedagógica |
| Integración Meta outbound (ver MD Meta) | Costo + media nativa |
| QA automático pre-publicar | Script: pasos, media HEAD S3, plantilla |

---

## QA antes de deploy

```bash
python manage.py test core.tests_modulo_publicacion core.tests_qa_publicacion_wa_completo core.tests_admin_mejoras_onda3 core.tests_admin_p2_ops
python scripts/_qa_smoke_publicacion_wa.py
```

Migraciones prod: `0134_modulo_publicado_wa`, `0135_modulo_publicacion_event`.

---

*Ver también: `docs/META_WHATSAPP_MIGRACION.md`, `docs/MODULE_BUILDER_WA.md`, `docs/EKI_UNFOLD_ADMIN.md`.*
