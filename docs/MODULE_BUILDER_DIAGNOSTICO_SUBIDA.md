# Diagnóstico de subida — Module Builder (solo informe)

Fecha: 2026-10-11. No se cambió la subida.

## Cómo sube hoy

No hay `fetch` de progreso. El archivo va en un **formulario** `multipart/form-data`:

- Añadir paso: `action=add_micro`, campo `media_file`, clase `eki-mb__add-micro`.
- Reemplazar: `action=replace_media`, `paso_id`, `media_file`, clase `eki-mb__upload-replace`.

El navegador hace un POST normal. La página espera la respuesta completa. No hay barra de porcentaje en el tramo navegador → servidor.

`module_builder.js`, si hay cambios sin guardar, pide confirmación, clona los campos de texto al formulario y, en reemplazo, no clona el título del módulo ni las secciones. Luego el formulario se envía igual (navegación completa).

La vista lee `request.FILES['media_file']` y llama a `guardar_upload_admin_media_resultado` (`core/admin/_common.py`):

1. Lee el archivo entero en memoria (`uploaded_file.read()`).
2. Si es `.mp4` / `.m4v` / `.mov` y Celery no está en eager (`use_async_media_encode`): valida que los primeros bytes tengan `ftyp`, sube el original a S3 en `…/incoming/…` (`subir_video_incoming`) y devuelve `async_encode: true`, `media_wa_apto: null`. La vista guarda esa URL temporal en el paso y encola `encode_paso_modulo_media`. El worker comprime (H.264, AAC, faststart, ancho ~720) y recién ahí fija la URL final y `media_wa_apto`.
3. Si no es vídeo, o el encode async está apagado: `guardar_bytes_admin_media_resultado` procesa en el request y `default_storage.save` sube a S3. Ruta: `{carpeta}/{año}/{mes}/{prefix}_{timestamp}_{filename}`. En el builder, carpeta `modulos/pasos` y prefijo `modulo_<id>`. Vídeo recomprimido: carpeta `modulos/pasos/wa_safe` y nombre con `_h264_main_faststart.mp4`.

Quien sube a S3 es el storage de Django (`default_storage`), no el navegador.

## Tamaños

| Tramo | Límite | Dónde |
|-------|--------|--------|
| Nginx del EB | `client_max_body_size 200M` | `.platform/nginx/conf.d/custom.conf` y `.ebextensions/nginx.config` |
| ALB | idle 1200 s | `.ebextensions/options.config` (`IdleTimeout: '1200'`) |
| Gunicorn | `--timeout 900` | `scripts/run_web.sh` |
| Django en producción | `DATA_UPLOAD_MAX_MEMORY_SIZE` = 110 MB; `FILE_UPLOAD_MAX_MEMORY_SIZE` = 10 MB (el resto a disco temporal) | `mvp_project/settings_production.py` |
| Django en `settings.py` (local sin el módulo de producción) | no está definido: el default de Django es 2,5 MB por request | |
| Vídeo apto para WhatsApp | 16 MB tras el gate (`WHATSAPP_VIDEO_MAX_BYTES`) | settings, default 16 MiB |
| Imagen al subir | 5 MB (`WHATSAPP_IMAGE_MAX_BYTES`) | |
| Audio al subir | 16 MB (`WHATSAPP_AUDIO_MAX_BYTES`) | |
| PDF / documento | `_rechazar_si_supera_tope_meta` no les pone tope de Cloud API. Los frena el tope del request (110 MB en prod, 200 MB en nginx). | `core/admin/_common.py` |

Un vídeo grande se acepta en S3 `incoming` y el worker lo comprime. Si después de comprimir sigue sobre 16 MB o el códec no sirve, el paso queda `media_wa_apto=False` y el encode en `error`. El request de subida, en el camino async, termina al dejar el archivo en `incoming`; no espera a ffmpeg.

## Tiempos de espera

- Nginx: `client_body_timeout`, `proxy_read_timeout` y `proxy_send_timeout` = **1200 s**.
- Gunicorn: **900 s**. El worker muere antes que nginx si la subida o el encode síncrono se alarga.
- ALB: **1200 s**.
- Cloudflare: `docs/INFRAESTRUCTURA_EKI_PARA_CLOUDFLARE.md` no fija un timeout verificado del proxy. Si `admin` pasa por el proxy naranja, el límite publicado de Cloudflare para HTTP en planes que no son Enterprise es **100 s** (respuesta 524). Por debajo de nginx, gunicorn y el ALB. No está comprobado en este repo si el admin va con proxy naranja. Conviene medirlo antes de la Fase 5B.
- ffprobe en el camino síncrono: 45 s. Un frame de ffmpeg: 60 s. La compresión de vídeo en `twilio_media.py` puede usar hasta 600 s **dentro del worker**, no del request, cuando el encode es async.

Para la Fase 5A (el mismo POST, con progreso en el navegador): el porcentaje real cubre solo navegador → Django. El tramo Django → S3 sigue siendo «Guardando», sin eventos. Un vídeo que entre en el tope de 110 MB / 200 MB puede completar el POST; uno mayor, no. Si el admin está detrás de Cloudflare con el corte de 100 s, un archivo lento falla aunque nginx aguarde 1200 s. Eso se confirma en staging antes de proponer otra cosa. No se aplica ninguna solución aquí.

## Qué devuelve `encode_status`

POST `action=encode_status`. No escribe. JSON:

```json
{
  "ok": true,
  "pasos": [
    {"id": 1, "status": "pending", "error": "", "media_url": "…", "media_wa_apto": null}
  ]
}
```

`status`: vacío (no hay job), `pending`, `running` o `error`. `error` es texto, como máximo 500 caracteres. **No hay porcentaje ni bytes procesados.** Lo arma `estado_encode_paso` (`core/media_encode_async.py`) desde cache, reconciliado con la URL del paso: si la URL sigue en `/incoming/` y `media_wa_apto` es null → `pending`; si es false → `error`.

El JS, si hay un badge `.eki-mb__badge--warn`, vuelve a pedir este JSON cada 20 s, hasta 12 veces. El botón «Refrescar estado» lo pide una vez.

## Cómo se calcula `media_wa_apto`

Tres estados: `True`, `False`, o `null` (aún no se sabe).

Vídeo, camino síncrono o worker (`evaluar_mp4_listo_whatsapp` en `core/twilio_media.py`):

- Sin caja `ftyp` → no apto (`cabecera_mp4_invalida`).
- Menos de 64 KB → no apto.
- Más de `WHATSAPP_VIDEO_MAX_BYTES` → no apto.
- Bitstream ilegible, sin pista de vídeo, o códec distinto de H.264 + AAC en perfil aceptado → no apto.
- Si pasa: apto. Faststart se remuxa antes; no alcanza para dar por bueno un HEVC.

Imagen, audio y PDF que pasan el tope de subida se guardan con `media_wa_apto=null`. No pasan por el gate de MP4. En el envío, `media_wa_apto is False` es lo que **omite** el archivo. `null` no lo omite: se intenta mandar la URL.

Al reemplazar o borrar, se limpia el cache de encode. Borrar deja `media_wa_apto` en null y la URL vacía. Una subida de staff que deja URL llama a `activar_paso_por_subida_staff`: el paso (y su sección, si estaba inactiva) pasa a activo.
