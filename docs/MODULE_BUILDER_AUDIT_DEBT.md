# Module Builder — auditoría de deuda técnica (ago 2026)

**Clasificación:** informe interno QA + PM + Dev  
**Trigger:** renombrar módulo “rompe” contenido; PDF bloqueado; confusión guardar vs subir; drip no persistía  
**Estado post-fix v23:** drip Builder reparado (JS syntax, backend guard, General abierto). Pendiente: unificar Legacy como solo avanzado en práctica operativa.

---

## 1. PM — qué reportó el usuario y qué era

| Síntoma percibido | Causa raíz |
|-------------------|------------|
| “No puedo cambiar el nombre del módulo” | El Builder **no tenía campo** para `Modulo.titulo`; solo se veía en el H1. Había que ir a legacy `?legacy=1`. |
| “Cada vez que guardo se daña” | Bug: **Guardar módulo** trataba checkbox `activo` ausente como **desactivar** → micros activos podían quedar inactivos al guardar solo texto/título. |
| “No puedo elegir PDF” | Bug: formulario «+ Añadir contenido» tenía `accept` sin PDF (corregido en deploy anterior). |
| “Guardar no sube archivo” | Comportamiento correcto mal explicado: archivos van por **Añadir contenido** / **Subir archivo**, no por Guardar módulo. |

---

## 2. QA — bugs confirmados y fixes

| ID | Severidad | Bug | Fix |
|----|-----------|-----|-----|
| MB-1 | **P1** | `save_modulo` desactivaba pasos si `paso_*_activo` no venía en POST | JS envía `0`/`1`; backend solo cambia `activo` si la clave existe |
| MB-2 | **P1** | Sin UI para renombrar módulo | Form «Nombre del módulo» + `save_modulo_meta` |
| MB-3 | **P2** | Sin UI para renombrar sección | Form «Renombrar sección» + `rename_seccion` |
| MB-4 | **P1** | PDF no en accept add_micro | `application/pdf` (deploy previo) |
| MB-5 | **P2** | Activar micro vacío → ValueError críptico | Mensaje existente; UX: no marcar Activo sin texto/media |

**Tests:** `core/tests_module_builder_ui.py` (+ meta, rename, activo explícito).

**Fuera de scope QA inmediato:** envío WA real de PDF (smoke Twilio manual).

---

## 3. Dev — deuda técnica estructural

### 3.1 Dos caminos duplicados (principal deuda)

| Camino | Superficie | Modelos |
|--------|------------|---------|
| **A — Module Builder** | `/admin/module-builder/` | `SeccionModulo`, `PasoModulo` |
| **B — Admin legacy** | `/admin/core/modulo/…?legacy=1` | Mismo + `ModuloAdminForm` pestaña Clase + inlines |

- GET módulo **redirige al Builder** → operador no ve pestaña Clase salvo legacy.
- `aplicar_clase_simple_desde_form` sincroniza 1er paso desde admin Clase; **Builder no usa esa ruta**.
- Riesgo: cambios en uno no se reflejan en UX del otro.

**Recomendación PM:** Builder = camino único para micros; legacy solo avanzado (quiz, drip, CE).

### 3.2 Guardado fragmentado

| Acción | Qué guarda |
|--------|------------|
| Guardar módulo | Texto/título/activo de **todos** los micros visibles |
| Guardar este micro | Igual pero un paso (fetch) |
| Guardar nombre | Solo `Modulo.titulo` |
| Renombrar sección | Solo `SeccionModulo.titulo` |
| + Añadir contenido / Subir | Crea paso o media (multipart) |

**Deuda:** un solo “Guardar todo” inteligente o wizard más claro.

### 3.3 JS panel lateral

- Mover DOM del editor al panel puede confundir (forms anidados conceptualmente).
- Sortable dispara POST + reload en cada drag (aceptable pero frágil en 3G admin).

### 3.4 Media async

- Video: Celery en `eki-ai-workers`; badge Procesando.
- PDF/imagen: síncrono a S3; OK.

---

## 4. CTO — decisión arquitectónica

| Pregunta | Respuesta |
|----------|-----------|
| ¿Reescribir en React? | **No** ahora. Django + JS cumple; deuda es producto/UX, no stack. |
| ¿Sacar Builder a app.eki? | **Fase 2** (borrador cliente → revisión eki). Admin primero. |
| ¿Prioridad vs EkiA? | **P1 Module Builder estable** = ingresos y entrega WA hoy. |
| ¿Deploy? | Fixes P1 → QA_PASS tests → deploy `eki-prod-final`. |

---

## 5. Checklist operativo post-fix

- [ ] Hard refresh admin (`Ctrl+F5`) tras deploy
- [ ] Un solo **Guardar módulo** (nombre + secciones + general + micros)
- [ ] General y entrega: modo WA, publicado, examen, calendario global
- [ ] Drip por cliente / Course Engine / quiz → **Configuración avanzada** (`?avanzado=1`)
- [ ] PDF: + Añadir contenido o Subir archivo
- [ ] Guía: `docs/MODULE_BUILDER_GUIA_ADMIN.md`

---

## 6. Backlog P1/P2 (Module Builder)

| P | Item | Estado |
|---|------|--------|
| P1 | Guardado unificado + fix activo | **Hecho** |
| P1 | Panel General (entrega, drip global, examen) | **Hecho** — drip por cliente sigue en admin Cliente |
| P1 | Link Configuración avanzada (`?avanzado=1`) | **Hecho** |
| P1 | Panel lateral sin mover DOM | **Hecho** |
| P1 | Guía admin 1 página | **Hecho** `MODULE_BUILDER_GUIA_ADMIN.md` |
| P1 | Smoke QA PDF + video piloto | QA checklist `MODULE_BUILDER_QA_S4_CHECKLIST.md` |
| **S4** | Persistencia completa en subida/reorder + aviso dirty | **Hecho** (pendiente deploy + QA) |
| **S4** | Reorder AJAX sin reload + preview fila + hint activo | **Hecho** |
| **S4** | Drip/calendario Builder (v23) | **Hecho** — ver §7 |
| P3 | Portal preview (solo lectura) | producto |

---

## 7. Drip / calendario (cerrado v23)

| ID | Severidad | Bug | Fix v23 |
|----|-----------|-----|---------|
| DRIP-1 | **P0** | JS syntax error → Guardar no ejecutaba | `parseJsonResponse` cerrado; `node --check` en precheck |
| DRIP-2 | **P0** | POST parcial borraba drip | `_debe_aplicar_calendario_desde_post` |
| DRIP-3 | **P1** | General colapsado → drip invisible | `general_abierto=True` + anchor en hero |
| DRIP-4 | **P1** | Mensaje verde sin confirmar drip | `messages` incluye «Drip guardado: …» |

**Gobernanza:** `docs/MODULE_BUILDER_QA_S4_CHECKLIST.md` — QA_PASS exige pytest + JS parse + manual drip.

---

*Actualizar tras cada deploy Builder. Canon técnico: `docs/MODULE_BUILDER_WA.md`.*
