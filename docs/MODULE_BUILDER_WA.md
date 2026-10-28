# Module Builder WA — contrato técnico legado

> Este documento conserva el comportamiento que hay que proteger mientras se retira la
> interfaz actual. No define el producto futuro. El plan vigente es
> `docs/PLAN_CONSTRUCTOR_CURSOS_EKI.md`.

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
- Tonos **Cielo / Marca / Oscuro** (todo el admin, icono `palette`; keys `manana`/`tarde`/`noche`)
- Superusuario puede forzar con `?builder=1` si el flag está OFF
- Admin clásico del módulo sigue disponible (enlace “Admin clásico”)
- Desde ficha del módulo (guía): enlace “Abrir Module Builder” si allowlist/flag ON

Acciones: + sección, + micro (texto y/o archivo con gate WA), ↑↓, **drag con rieles**
(micros solo dentro de su sección; secciones enteras), desactivar.
Tonos UI: Cielo / Marca / Oscuro. Persistidos en `localStorage`.
**No envía WhatsApp.**

### Cómo entrar

1. Admin → Módulos → ficha del módulo → enlace **Abrir Module Builder** (si flag ON).
2. URL directa: `/admin/module-builder/<modulo_id>/`

Edita `SeccionModulo` + `PasoModulo` (materiales WA).  
El calendario global (`Modulo.habilitado_desde`) solo se escribe en un guardado explícito que traiga la clave. No reescribe el texto legacy `Modulo.contenido` por su cuenta.

## Interfaz nueva (apagada)

`EKI_MODULE_BUILDER_UI_V2` sale en False. Con False, la página es la de hoy.

Un superusuario puede ver la interfaz nueva en una petición con `?ui=v2` (junto con `?builder=1` si el curso no está en la puerta beta). Un usuario staff que no es superusuario sigue viendo la página de hoy aunque ponga `?ui=v2`.

Pestañas: Contenido, General, Calendario y drip. En pantallas estrechas, Vista previa. Guardar desde Contenido o General no envía `modulo_habilitado_desde`. Solo «Guardar calendario» lo envía.

El botón «Publicar en WhatsApp» de la interfaz nueva abre `/admin/core/modulo/<id>/publicar/confirmar/`. El GET muestra el checklist y no publica. El POST, con CSRF, publica. La ruta `core_modulo_publicar` no cambia y la interfaz de hoy la sigue usando. Esa ruta antigua se retira después, cuando la de hoy también pase por la confirmación.

La subida con progreso de la interfaz nueva usa `static/js/media-uploader/` y `core/media_upload_servicio.py`. El POST sigue siendo `replace_media`. Ver `docs/MEDIA_UPLOADER.md`. No hay subida directa a S3: el diseño está en `docs/MEDIA_UPLOADER_5B_PROPUESTA.md`.

