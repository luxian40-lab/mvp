# Module Builder — checklist QA (gate obligatorio)

**Última actualización:** 2026-09-01  
**Prod actual:** `builder-drip-v23-20260901-112850`  
**Rollback:** `builder-calendario-v21-20260901-104404`

## Regla

Cualquier cambio en Builder / drip / General → **QA_FAIL** si no pasan P0 (auto + manual).

**QA_PASS** requiere los tres bloques:

1. pytest `core.tests_module_builder_ui` + `core.tests_module_builder_wa` verdes  
2. `node --check static/admin/js/module_builder.js` OK (o `test_module_builder_js_syntax_valid`)  
3. Al menos **un caso manual drip** documentado (fecha → Guardar → Ctrl+F5)

## P0 — JS health (bloqueante)

- [x] `test_module_builder_js_syntax_valid` — `node --check` en CI/precheck
- [x] `scripts/eb_precheck_main.ps1` sección 6 — gate antes de deploy
- [ ] **Manual:** consola browser sin errores al cargar Builder (`?v=23`)

## P0 — Drip y calendario (bloqueante)

- [x] `test_save_modulo_persiste_habilitado_desde` — guardar y limpiar fecha
- [x] `test_save_modulo_sin_campo_drip_no_borra_habilitado_desde` — POST parcial no wipe
- [x] `test_add_micro_no_pisa_general_sin_persist_flag` — subida no pisa drip
- [x] `test_add_micro_no_renombra_modulo_ni_seccion_default` — subida no pisa nombres
- [x] `test_save_modulo_post_then_get_muestra_drip` — banner + inputs tras GET
- [ ] **Manual:** fecha en calendario → Guardar → Ctrl+F5 → misma fecha/hora + banner
- [ ] **Manual:** Limpiar → Guardar → sin fecha
- [ ] **Manual:** sin alerta «No se pudo guardar» al guardar solo drip

## P0 — Persistencia micros / nombres

- [x] Subida no renombra módulo/sección (`test_add_micro_no_renombra_*`, `test_replace_media_solo_toca_paso_subido`)
- [x] `replace_media` no pisa otros pasos
- [x] Reorder AJAX (`test_reorder_micros_ajax_json`)

## P1 — UX General

- [x] Sección «Calendario y drip» visible (`test_builder_muestra_general_y_avanzado`)
- [x] General abierto por defecto (`general_abierto=True`)
- [x] Enlace «Ir a General y drip» en hero
- [x] Enlaces drip cliente / estudiante / avanzado en HTML
- [ ] Confirmación dirty al subir (manual)
- [ ] Drag reorder dirty (manual)

## Regresión automática

```bash
python manage.py test core.tests_module_builder_ui core.tests_module_builder_wa -v 0
node --check static/admin/js/module_builder.js
```

Objetivo: **52+ tests UI OK** antes de deploy.

## Smoke WA (con autorización teléfono QA)

- [x] Impulso M1,M8,M9,M10,M11 videos → 3026480629 (2026-09-01)

## Evidencia manual (plantilla)

```
Módulo: /admin/module-builder/<id>/
Fecha probada: YYYY-MM-DD HH:MM
Tras Ctrl+F5: OK / FAIL
Banner «Drip guardado»: sí / no
Consola JS: sin errores / (pegar error)
Veredicto: QA_PASS | QA_FAIL
```

```
QA_PASS solo si P0 auto + P0 manual + JS health verdes
```
