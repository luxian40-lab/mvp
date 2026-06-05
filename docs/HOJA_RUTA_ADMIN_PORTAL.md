# Hoja de ruta — Ordenar Admin (tú) y Portal (empresas)

**Objetivo:** Que el día a día sea claro sin migrar a Unfold.  
**Quién usa qué:**

| Espacio | Usuario | URL base |
|---------|---------|----------|
| Admin Jazzmin | Solo eki (tú) | `/admin/` |
| Portal B2B | Clientes / cooperativas | `/portal/` |

**Lo que más abres hoy (núcleo operativo):**

1. Dashboard  
2. Clientes  
3. Campañas  
4. Cursos  
5. Módulos  

---

## Principios (no negociables)

1. **Un solo inicio en admin:** siempre `/admin/dashboard/` (dashboard unificado).  
2. **Portal = lo que el cliente puede ver/hacer solo.** Admin = cargas, envíos, configuración técnica, debugging.  
3. **Menú por frecuencia de uso**, no por cómo está el código.  
4. **Cambios pequeños y desplegables** — una fase por semana como máximo.

---

## Mapa rápido — Núcleo operativo

| Acción | Admin (tú) | Portal (cliente) |
|--------|------------|------------------|
| Ver KPIs globales / por cliente | `/admin/dashboard/` | `/portal/dashboard/` y `/portal/metricas/` |
| Crear/editar organización, logo, módulos portal | Admin → **Clientes** | `/portal/perfil/` (solo su logo/subtítulo) |
| Crear campaña, Excel, ejecutar envío | Admin → **Campañas** + importadores | `/portal/campanas/` (solo lectura) |
| Crear curso, orden, drip, certificados | Admin → **Cursos** | `/portal/cursos/` (lista) |
| Contenido módulo, pasos, archivos | Admin → **Módulos** (desde curso o listado) | — |
| Importar / reenganche estudiantes | Admin → Estudiantes / importar | `/portal/estudiantes/` + export Excel |
| Grupos masivos | Admin → Grupos + gestionar miembros | Filtro grupo en métricas portal |

---

## Fase 0 — Acuerdos (½ día, sin código)

**Entregable:** checklist mental fijado.

- [ ] Bookmark fijos en el navegador (5 URLs del núcleo).  
- [ ] Regla: métricas “para presentar al cliente” → portal; “para operar/corregir” → admin.  
- [ ] Regla: no abrir dashboards viejos (`dashboard-metrics`, `dashboard-gerencial`, etc.) — solo el unificado.

**Bookmarks recomendados:**

```
/admin/dashboard/
/admin/core/cliente/
/admin/core/campana/
/admin/core/curso/
/admin/core/modulo/
/admin/instrucciones/
```

---

## Fase 1 — Menú Jazzmin alrededor de tu día (1–2 días)

**Archivo principal:** `mvp_project/settings.py` → `JAZZMIN_SETTINGS`.

**Objetivo:** Sidebar que refleje este orden:

```
📊 Operación diaria
   → Dashboard unificado      (/admin/dashboard/)
   → Manual / instrucciones   (/admin/instrucciones/)

🏢 Clientes
   → Clientes
   → Grupos de estudiantes

📣 Campañas
   → Campañas
   → Plantillas
   → Calendario campañas      (/admin/calendario/)  [custom_link]
   → Importar estudiantes     (/admin/importar-estudiantes/)

📚 Cursos y contenido
   → Cursos
   → Módulos
   → Progreso estudiantes
   → Crear curso con IA       (/admin/crear-curso-ia/) [custom_link]

👥 Personas
   → Estudiantes
   → PQRS / Soporte

🌱 GEI / 🤖 Nat / 📈 Avanzado
   → (solo si los usas esa semana; links custom actuales)
```

**Tareas concretas:**

- [ ] Reordenar `order_with_respect_to` con bloques arriba.  
- [ ] Mover `custom_links` de GEI/Nat/AI Ops al final del menú o sección “Avanzado”.  
- [ ] Revisar `hide_models`: ocultar todo lo que no abriste en 3 meses.  
- [ ] Topmenu Jazzmin: solo **Dashboard** + **Instrucciones** (quitar duplicados confusos).  
- [ ] `search_model`: mantener Estudiante, Campaña; añadir Cliente si te ayuda.

**Criterio de éxito:** En 10 segundos encuentras Clientes, Campañas, Cursos sin scroll infinito.

---

## Fase 2 — Portal alineado con clientes (1–2 días, ya parcialmente hecho)

**Archivo:** Admin → Cliente → `portal_modulos` (checkboxes) + `tipo_proyecto`.

**Objetivo:** Cada cliente ve solo lo contratado.

| Módulos portal | Qué ve el cliente |
|----------------|-------------------|
| `cursos` | Dashboard, métricas, estudiantes, cursos, campañas (lectura), export reenganche |
| `gei` | Inventario GEI + export |
| `nat` | Nat, catálogo, HITL, PQRS comercial |

**Checklist por cliente nuevo:**

- [ ] Crear **Cliente** en admin.  
- [ ] Marcar **Módulos del portal** (`cursos`, `gei`, `nat` según contrato).  
- [ ] Fechas suscripción.  
- [ ] Crear usuario portal (admin o acción en ficha cliente).  
- [ ] Probar login en `/portal/login/`.

**Criterio de éxito:** Un cliente “solo cursos” no ve GEI/Nat en el menú portal.

---

## Fase 3 — Documentación viva (1 día)

**Archivo único:** `templates/admin/instrucciones.html` (fuente de verdad; comando `actualizar_manual` si aplica).

**Añadir secciones:**

1. **Mi rutina eki** — los 5 bookmarks y cuándo usar cada uno.  
2. **Portal vs Admin** — tabla como la de arriba.  
3. **Flujo campaña de curso** — cliente → curso destino → grupo → ejecutar.  
4. **Flujo reenganche** — portal export “sin módulo N” → borrar en admin → reimportar.

**Criterio de éxito:** Si vuelves en 2 meses, el manual te recuerda el flujo sin explorar el repo.

---

## Fase 4 — Limpiar ruido de dashboards (½–1 día)

**Problema:** Muchas URLs legacy redirigen al dashboard unificado (`core/urls/admin_urls.py`).

**Tareas:**

- [ ] Listar en instrucciones: “URLs obsoletas — no usar”.  
- [ ] (Opcional) Quitar enlaces del menú que apunten a rutas `-antiguo` / `dashboard-metrics`.  
- [ ] Dejar **una** pantalla de métricas globales en admin: `/admin/dashboard/`.

**No borrar redirects** hasta confirmar que no hay bookmarks viejos en Twilio/docs externos.

---

## Fase 5 — Código admin mantenible (2–4 días, cuando toque)

**Problema:** `core/admin.py` ~7.500 líneas.

**Enfoque incremental (sin cambiar comportamiento):**

```
core/admin/
  __init__.py          # registra todo como hoy
  clientes.py          # Cliente, PortalUsuario inline, etc.
  estudiantes.py
  campanas.py
  cursos_modulos.py    # Curso, Modulo, Progreso...
  soporte.py           # PQRS, logs
  _shared.py           # mixins, helpers
```

**Orden de extracción:** Clientes → Campañas → Cursos/Módulos → resto.

**Criterio de éxito:** Buscar “CampanaAdmin” abre un archivo pequeño.

---

## Fase 6 — Pulido visual Jazzmin (opcional, ½ día)

Sin Unfold:

- [ ] Revisar `static/admin/css/custom_menu.css`.  
- [ ] `JAZZMIN_UI_TWEAKS`: tema más limpio, sidebar fijo solo si te ayuda.  
- [ ] Iconos consistentes en el bloque “Operación diaria”.

**Criterio de éxito:** Se siente menos “plantilla 2018”, sin reescribir plantillas.

---

## Cronograma sugerido (4–6 semanas, ritmo tranquilo)

| Semana | Fase | Esfuerzo |
|--------|------|----------|
| 1 | Fase 0 + Fase 1 (menú) | ~1–2 días |
| 2 | Fase 2 (checklist clientes portal) + probar 1 cliente real | ~1 día |
| 3 | Fase 3 (manual) | ~1 día |
| 4 | Fase 4 (dashboards) | ½ día |
| 5–6 | Fase 5 (split admin.py) solo si te molesta buscar código | 2–4 días |
| — | Fase 6 si aún “se siente viejo” | ½ día |

---

## Qué NO está en esta hoja de ruta

- Migración Jazzmin → Unfold (bajo ROI para un solo usuario).  
- Reescribir portal (ya en buen camino CRM).  
- Nuevas features grandes (enviar campañas desde portal, etc.) — van **después** del orden.

---

## Próximo paso recomendado (cuando quieras código)

**Empezar por Fase 1:** reordenar `JAZZMIN_SETTINGS` con tu núcleo (Dashboard → Clientes → Campañas → Cursos → Módulos) y subir a prod.

Di en el chat: *“implementa Fase 1 del roadmap admin”* y se hace en un deploy acotado.

---

## Referencias en el repo

| Tema | Archivo |
|------|---------|
| Menú Jazzmin | `mvp_project/settings.py` |
| URLs admin custom | `core/urls/admin_urls.py` |
| Dashboard unificado | `core/views.py` → `dashboard_unificado` |
| Portal módulos | `portal/capabilities.py`, `portal/forms.py` |
| Arquitectura dominios | `docs/DOMAIN_ARCHITECTURE.md` |
| Rutas por dominio | `docs/ROUTE_MAP_BY_DOMAIN.md` |

*Última actualización: 2026-06-04*
