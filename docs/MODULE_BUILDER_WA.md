# Module Builder WA — contrato (Fase 0)

**Scope:** solo admin módulos (`SeccionModulo` / `PasoModulo`).  
**Fuera:** Studio, portal, Aprende, certificados, envíos WhatsApp de prueba.

## Contrato de estructura

```
Curso → Módulo → N secciones → N micros (texto y/o media)
Un *listo* = una sección completa (todos sus pasos)
Prohibido: pasos de la sección A intercalados en medio de B
```

N puede ser 1 o 20. Lo crítico es **orden contiguo por sección** (una sección no “reaparece” después de otra).

## Contrato de media (upload nuevo)

1. Al subir MP4/MOV/M4V desde admin → validar + **comprimir** (H.264 Main, AAC, faststart, máx. ancho ~720).
2. Si tras comprimir sigue **> 16 MB** (límite práctico Meta/WhatsApp) → **rechazar** el upload con mensaje claro.
3. URL resultante preferible bajo path `wa_safe/`; `PasoModulo.media_wa_apto=True` si pasó el gate.
4. Videos ya publicados en cursos vivos **no** se reprocesan en lote automáticamente.

## Guardrails cursos vivos

- Feature UI builder (cuando exista) detrás de flag; admin actual sigue.
- Validación anti-intercalado avisa / bloquea **guardados nuevos**; no migra datos masivos sola.
- QA de esta iniciativa: **sin envío Twilio** (tests unitarios + auditoría lectura).

## Builder UI (Fase 3–4)

- URL: `/admin/module-builder/<modulo_id>/`
- Flag: `EKI_MODULE_BUILDER_BETA` (local ON; prod OFF salvo `=1`)
- Allowlist: `EKI_MODULE_BUILDER_CURSOS` — default `*` (todos). Tokens: id, subcadena de nombre, o `*`/`all`/`todos`
- Tras crear/guardar módulo (sin “continuar” / “añadir otro”) → redirect al Builder si está habilitado
- Entrada visible: columna **Builder** + botón detalle + enlace en guía Clase
- Tonos Mañana / Tarde / Noche: barra fija abajo-derecha en **todo** el admin
- Superusuario puede forzar con `?builder=1` si el flag está OFF
- Admin clásico del módulo sigue disponible (enlace “Admin clásico”)
- Desde ficha del módulo (guía): enlace “Abrir Module Builder” si allowlist/flag ON

Acciones: + sección, + micro (texto y/o archivo con gate WA), ↑↓, **drag con rieles**
(micros solo dentro de su sección; secciones enteras), desactivar.
Tonos UI: mañana / tarde / noche (ojos). Persistidos en `localStorage`.
**No envía WhatsApp.**

### Cómo entrar

1. Admin → Módulos → ficha del módulo → enlace **Abrir Module Builder** (si flag ON).
2. URL directa: `/admin/module-builder/<modulo_id>/`

Edita `SeccionModulo` + `PasoModulo` (materiales WA).  
No mueve drip / `habilitado_desde` / agentes. No reescribe solo el texto legacy `Modulo.contenido`.

