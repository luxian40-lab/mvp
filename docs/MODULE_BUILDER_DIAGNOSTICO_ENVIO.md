# Diagnóstico de envío — texto y archivo (solo informe)

Fecha: 2026-10-11. No se cambió ningún envío.

## Dónde se arma y dónde sale

Un *listo* entrega **una sección**: `entregar_bloque_secciones_desde_paso` en `core/module_steps.py` (lo llama `entregar_paso_indice`). Dentro de la sección manda todos los pasos activos hasta una evaluación. Al final agrega la burbuja de «escriba listo».

Cada paso se parte en `partes_mensaje_paso`:

- Sin URL, o con URL pero encode `pending`/`running`, o con `media_wa_apto is False`: **solo texto**. El archivo no sale.
- Con URL usable y texto de un solo párrafo: el texto va **en el mismo bloque** que `[MEDIA:url]` (`parte_mensaje_con_media` en `core/response_templates.py`). Hay un test que lo fija: `test_paso_con_media_incluye_texto_en_mismo_bloque_que_media`.
- Si el texto tiene salto de línea, la primera línea va con el archivo y el resto va **después** de `[DELAY:5]`, en otro mensaje.
- Sin texto de autor: el archivo va solo. El título del paso y el de la sección no se usan como pie (`core/tests_caption_media_sin_titulo.py`).

Dentro de la sección, el orden de envío no es solo el `orden` del builder. `_batch_pasos_desde_indice` reordena: primero texto sin archivo, luego texto con archivo, luego archivo solo. Siguen siendo mensajes distintos. No fusiona dos pasos en uno.

Si el vídeo del paso está en «enlace» (`video_entrega=enlace`), `reescribir_videos_en_mensaje` (`core/video_links.py`) sustituye `[MEDIA:…]` por el texto «Para ver el video» y el enlace corto. Ahí no hay adjunto.

El webhook (`core/views/webhook_twilio.py`) parte `[MULTI_MSG]` por `[SEP]`, saca `[MEDIA:url]` y llama a `_enviar_mensaje_twilio_segmentado` (`core/views/twilio_transporte.py`) con `body` y `media_url` **juntos** en el primer segmento. Los segmentos siguientes van sin archivo. El cuerpo se corta con `TWILIO_MAX_BODY_CHARS` (default 1500).

Ese transporte, en producción de cursos, es **Twilio** (`client.messages.create` con `body` + `media_url`). `core/media_entrega.py` no cambia el formato: si Twilio responde 63019, 63021 o 63005, reintenta el mismo adjunto. Si el `create` ya lanza uno de esos códigos, el transporte **quita el adjunto y reintenta solo el texto**.

`core/sandbox_canal.py` deja escrito que los cursos de producción (WABA Twilio) no pasan por ahí. `enviar_meta` solo entra si el turno es sandbox Meta (`sandbox_meta_activo`).

## Por qué en el celular no se ve el texto pegado al video o a la imagen

El código **sí intenta** mandarlos juntos cuando un mismo paso tiene texto y URL usable. No hay un filtro que borre el pie en el caso feliz. Lo que separa o hace desaparecer una de las dos cosas:

1. **El paso no tiene las dos cosas.** Subir un archivo (`replace_media` / `add_micro`) no exige texto. El archivo sale solo. Un mensaje de texto vecino es otro paso y sale en otra burbuja (y, por el reorden del lote, el texto solo va antes que el archivo).
2. **`media_wa_apto is False`.** El archivo se omite. Queda el texto, si había.
3. **Vídeo aún en encode** (`pending` / `running`). Igual: se omite el archivo y, si había texto, sale solo.
4. **63021 (y 63019 / 63005).** 63021 es códec o formato de vídeo (hace falta H.264 + AAC y faststart; un remux no arregla HEVC). 63019 es descarga, MIME o URL. Si el alta a Twilio falla con esos códigos, el reintento es **solo texto**. El estudiante ve el texto y no el archivo, o no ve el archivo con su pie.
5. **Tope de vídeo 16 MB** (`WHATSAPP_VIDEO_MAX_BYTES`, settings, default 16 MiB). Por encima, el gate local marca el MP4 no apto y no se adjunta. Imagen: tope `WHATSAPP_IMAGE_MAX_BYTES` (default 5 MiB) al subir. Audio: `WHATSAPP_AUDIO_MAX_BYTES` (default 16 MiB).
6. **Entrega por enlace.** El vídeo deja de ser adjunto. El texto del paso y el enlace quedan como texto, no como pie de un vídeo.
7. **Párrafo largo.** Twilio parte el cuerpo. Solo el primer trozo viaja con el archivo.

El modo legacy del módulo (sin pasos) es otro camino: el comentario en `response_templates.py` dice que el vídeo del módulo se manda **después** del texto, en otra parte. No es el camino del builder de pasos.

## ¿El pie de foto de Meta Cloud API serviría?

En el sender que ya existe, `enviar_meta` (`core/sandbox_canal.py`), si hay URL:

- El tipo sale de la extensión: vídeo (`.mp4`, `.mov`, `.3gp`, `.webm`), audio, documento (`.pdf`, Office, `.zip`) o, si no, imagen.
- Los primeros 1024 caracteres del texto van en `caption` del objeto de imagen, vídeo o documento.
- Lo que pasa de 1024 se manda en un mensaje de texto aparte.

Eso coincide con el esquema de Cloud API: imagen, vídeo y documento aceptan `caption` (tope 1024). El audio **no** tiene caption; el código igual se lo pone, y Graph puede rechazar ese mensaje.

Ese sender **no** es el de los cursos en producción. Hoy el curso sale por Twilio, donde el `body` del mensaje con `media_url` es el pie, con los fallos de arriba. Hacer que producción use el pie de Cloud API sería cambiar el envío. Este informe no lo hace.

Conclusión para la UI: tratar «un mensaje = una sola cosa» es una decisión de pantalla. No hace falta tocar `module_steps` ni el transporte para dejar de pedir un texto acompañante. Los pasos que ya tienen texto y archivo siguen saliendo como hoy (un bloque `[MEDIA]` con pie, salvo que uno de los puntos 2–7 los separe).
