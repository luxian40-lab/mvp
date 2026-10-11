# Subida con progreso

Componente de la interfaz nueva del Module Builder. No cambia las rutas de S3.

## Piezas

| Pieza | Rol |
|---|---|
| `static/js/media-uploader/uploader.js` | Cola, progreso, cancelar, reintentar. No importa el Builder ni Unfold. |
| `static/js/media-uploader/uploader.css` | Solo variables `--eki-mu-*`. |
| `core/media_upload_servicio.py` | Tipo y tamaño desde settings. No escribe. |

`core/services.py` ya es el módulo de campañas. Por eso el validador no vive en una carpeta `core/services/`: en Python no pueden coexistir el archivo y la carpeta, y partir campañas no es este trabajo.

## Contrato

El anfitrión pasa `url`, `campos` (el mismo POST de hoy: `action=replace_media`, `paso_id`, `csrfmiddlewaretoken`, `video_entrega`, `media_file`), `validar`, `colaMax` y `despues`.

Eventos sobre el elemento objetivo: `upload:progress`, `upload:done`, `upload:error`, `upload:cancel`.

Etapas: Subiendo (porcentaje del tramo navegador a servidor, «X de Y MB», tiempo restante), Guardando, Preparando (si `despues` lo dice; `encode_status` no trae porcentaje, así que el texto es actividad y tiempo), Listo (apto o no, con motivo).

El permiso lo decide la vista que recibe el POST. El componente no elige el bucket.

## Apagar

`EKI_MODULE_BUILDER_UI_V2` en False, y sin `?ui=v2` de superusuario. La interfaz de hoy sigue enviando el formulario como antes.
