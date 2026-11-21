# Informe bloque 6.1 — retiro de reexports `canal` (parcial)

Fecha: 2026-11-21. Solo movimiento. Sin deploy. Sin setenv.
Rama: `slice/bloque-6-1-canal`.

## Hecho

| Stub retirado | Commit |
| --- | --- |
| `core/meta_templates.py` | `8a6bdab8` |
| `core/twilio_timeout.py` | `d3bdb714` |
| `core/linea_registrados.py` | `30c9ad4b` |
| `core/wa_reply_context.py` | `a396e145` |
| `core/twilio_puerta.py` | `599286b3` |
| `core/meta_inbound.py` | `7e9c5e76` |
| (sesión previa) `wa_canal`, `meta_estados`, `models_meta_webhook`, `webhook_evento`, `meta_token`, … | ver `git log` |
| `core/planes_linea.py` | `abfe1a82` |
| `core/twilio_media.py` | `24cca8ef` |
| `core/whatsapp_service.py` | `ee7e16f0` |
| `core/utils_telefono.py` | `c8a54328` |

Callers y `patch()` apuntan a `core.canal.*`. Imports relativos `..twilio_media` en `views/twilio_transporte.py` también retargeteados.

## Tests de área (esta tanda)

- `core.tests_planes_linea` (+ oferta/cursos_linea): OK
- `core.tests_twilio_media`: OK (28)
- `core.tests_sender` + habeas + sandbox_canal_meta: OK
- `core.tests_campana_telefonos` + meta_inbound + excel + documento: OK

## Nota (no introducida por utils_telefono)

`core.tests_lineas_cortes.test_enviar_meta_vive_en_lineas` falla por orden: tests de `EntregaMarcadaTests` dejan `core.sandbox_canal.enviar_meta` como MagicMock (stub `sys.modules`). Se reproduce con el stub de `utils_telefono` aún presente. Aislado OK. Tratar al retirar `sandbox_canal`.

## Queda en raíz (`canal`)

`sandbox_canal`, `utils` → `envios`, `meta_waba`.

## Siguiente

Retirar `sandbox_canal` (cuidado con patches) o `meta_waba` / `utils`, un stub por commit. Sin deploy hasta pedido.
