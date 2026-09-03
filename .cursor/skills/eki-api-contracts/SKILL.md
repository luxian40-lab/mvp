---
name: eki-api-contracts
description: >-
  API and interface contracts for eki_mvp. POST/ajax boundaries, error
  semantics, Hyrum's Law for Module Builder and webhooks. Use when adding
  or changing endpoints, ajax actions, or Twilio handlers.
---

# eki API Contracts

Contratos explícitos entre JS, Django views y clientes externos.

## Cuándo usar

- Nueva `action` en `views_module_builder.py`.
- Respuesta `JsonResponse` ajax.
- Webhooks Twilio (raw body, firma).
- Cambio de nombres de campos POST.

## Principios

1. **Hyrum's Law** — Cualquier campo que expongas será consumido; no romper sin versión.
2. **Errores explícitos** — `400` + `{"ok": false, "error": "..."}`; nunca fallo silencioso.
3. **Éxito explícito** — `{"ok": true, ...}` con campos que el JS necesita para sync UI.
4. **Webhooks** — bytes crudos → `hmac.compare_digest` → parse (ver `eki-sec`).

## Contrato Module Builder `save_modulo` (ajax=1)

**Request:** `action=save_modulo`, `ajax=1`, `modulo_titulo`, `modulo_habilitado_desde` (ISO o vacío), …

**Response 200:**
```json
{
  "ok": true,
  "partes": ["nombre", "configuración"],
  "habilitado_desde": "2032-03-20T09:15",
  "habilitado_desde_fecha": "2032-03-20",
  "habilitado_desde_hora": "09:15"
}
```

**Response 400:** `{"ok": false, "error": "<mensaje>"}`

Test canónico: `test_save_modulo_ajax_json_ok`

## Anti-racionalización

| Excusa | Respuesta |
|--------|-----------|
| «El front ya sabe leer HTML redirect» | Ajax path debe tener contrato JSON testeado. |
| «Solo agregué un campo opcional» | Documentar en test; el JS puede depender de él mañana. |
| «ValueError alcanza» | Mapear a JSON 400 para que el JS muestre error, no alerta genérica. |

## Verificación (no negociable)

- [ ] Test `Client().post(..., HTTP_ACCEPT='application/json')` con asserts de shape.
- [ ] JS maneja `ok: false` (usuario ve mensaje).
- [ ] Sec revisado si endpoint público o upload.

## Cómo invocarlo

`@eki-api-contracts` o “define contrato ajax para esta action”.
