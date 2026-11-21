# Informe bloque 6.1 — retiro de reexports `canal` (parcial)

Fecha: 2026-11-20. Solo movimiento. Sin deploy. Sin setenv.

## Hecho en esta sesión

| Stub retirado | Commit |
| --- | --- |
| `core/meta_templates.py` | `8a6bdab8` |
| `core/twilio_timeout.py` | `d3bdb714` |
| `core/linea_registrados.py` | `30c9ad4b` |
| `core/wa_reply_context.py` | `a396e145` |
| `core/twilio_puerta.py` | `599286b3` |
| `core/meta_inbound.py` | `7e9c5e76` |

Callers y `patch()` apuntan a `core.canal.*`.

## Freno (medir local, sin `--actualizar`)

| Métrica | Antes de 6.1 (misma main) | Después de estos 6 stubs |
| --- | ---: | ---: |
| `ciclo_mayor` | 233 | **230** |
| `archivos_sueltos_core` | 234 | **228** |

El baseline de CI sigue en 211 / 231: el ratchet ya estaba rojo en main; este corte **bajó** el actual. No se subió el baseline.

## Queda en `canal` (stubs aún en raíz)

Entre otros: `sandbox_canal`, `utils_telefono`, `utils`/`envios`, `twilio_media`, `meta_token`, `meta_waba`, `planes_linea`, `whatsapp_service`, `webhook_evento`, `wa_canal`, `meta_estados`, `models_meta_webhook`, `twilio_balance`, `twilio_content_preview`, `twilio_inbound_media`, `twilio_webhook_security`.

Siguiente: seguir retirando stubs chicos de `canal` (mismo patrón), un stub por commit.
