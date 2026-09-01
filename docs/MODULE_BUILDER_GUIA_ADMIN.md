# Module Builder — guía rápida admin (1 página)

**Camino principal:** `/admin/module-builder/<modulo_id>/`

## Qué editar dónde

| Necesidad | Dónde |
|-----------|--------|
| Micros (texto, PDF, imagen, video), secciones, orden | **Module Builder** |
| Nombre del módulo, descripción, modo entrega, publicado WA, examen, calendario global | Builder → **General y entrega** |
| Drip por cliente/empresa, habilitación por estudiante | Admin **Cliente** → inlines drip |
| Course Engine (tier, voz IA, video módulo) | **Configuración avanzada** (`?avanzado=1`) |
| Quizzes / evaluación por opciones, tipo de paso | **Configuración avanzada** → inline Pasos |
| Media legacy (`ArchivoModulo`) | Enlace **Media legacy** en Builder o avanzado |
| Pestaña Clase (flujo antiguo Aprende) | Solo avanzado — no usar en paralelo con Builder |

## Guardar

1. **Guardar módulo** — nombre, secciones, general, todos los micros.
2. **+ Añadir contenido** / **Subir archivo** — suben media; **también guardan** lo que tengas escrito en pantalla (módulo, secciones, general y micros). Si hay cambios sin guardar, pedirá confirmación.
3. **Arrastrar** para reordenar — guarda orden por AJAX (sin recargar toda la página); con cambios pendientes, confirma antes.
4. **Guardar este micro** — atajo para un solo paso (+ resto visible si aplica).

## Publicar WhatsApp

Sticky inferior → **Publicar** cuando el checklist esté verde. Requiere micros activos y media OK.

## Calendario y drip (3 capas)

eki aplica **la fecha más restrictiva** según contexto del estudiante:

| Capa | Dónde se configura | Alcance | Prioridad |
|------|-------------------|---------|-----------|
| **Global módulo** | Builder → General → «Disponible desde» | Todos los estudiantes del módulo | Base |
| **Por empresa/cliente** | Admin Cliente → Habilitación drip módulo | Solo estudiantes de ese cliente | **Sustituye** global para ese cliente |
| **Por estudiante** | Admin → drip por estudiante | Un estudiante | **Máxima** (override individual) |

**Importante:**

- El banner «Drip guardado» en Builder refleja solo la capa **global** (`Modulo.habilitado_desde`).
- Si hay drip por empresa activo, el estudiante puede no recibir el módulo aunque el banner global diga otra cosa.
- Ritmo entre módulos (`dias_espera_entre_modulos` en el curso) es **adicional** al calendario global.

**Legacy:** `/admin/core/modulo/<id>/change/?avanzado=1` → pestaña «Más opciones» → `habilitado_desde` (mismo campo que Builder).

## Atajos

- Desde listado módulos: acción **Module Builder**.
- Abrir módulo en admin → redirige al Builder salvo `?avanzado=1` o `?legacy=1`.

*Canon técnico: `docs/MODULE_BUILDER_WA.md` · Deuda: `docs/MODULE_BUILDER_AUDIT_DEBT.md`*
