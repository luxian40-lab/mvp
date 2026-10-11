# Guion de navegador — Module Builder (manual)

No hay Playwright en el proyecto (búsqueda en dependencias y docs, 2026-10-11). Este guion se corre a mano en local o staging, con la copia del curso, nunca en producción.

No envía WhatsApp. El enlace Publicar **sí escribe** `publicado_wa` si se abre: el paso 12 no lo abre.

Interruptor: para este guion, `EKI_MODULE_BUILDER_UI_V2` ausente o `False` (la pantalla de hoy). Cuando exista la UI nueva, repetir el mismo guion con `True`.

Preparación: staff, `EKI_MODULE_BUILDER_BETA=1`, curso de la copia (no el de producción). Anotar `MODULO_ID`.

## Pasos

1. **Abrir.** Ir a `/admin/module-builder/<MODULO_ID>/`. Esperado: HTTP 200, menú de Unfold, título «Module Builder», nombre del módulo en `#eki-mb-modulo-titulo`, secciones visibles. Si el flag está apagado y el usuario no es superusuario con `?builder=1`, esperado 403. No seguir.

2. **Renombrar sección.** En el campo `Sección` de la primera tarjeta, cambiar el nombre. Pulsar «Guardar módulo» (`#eki-mb-save-top` o `#eki-mb-save-all`). Esperado: el estado pasa a «Guardado» sin recargar en blanco; al recargar, el nombre nuevo sigue. En la base, solo cambió `SeccionModulo.titulo` de esa sección (y lo demás que el guardado completo persiste: ver contrato).

3. **Agregar sección.** En «Añadir sección», escribir un nombre y enviar. Esperado: redirect al builder y la sección nueva al final, sin pasos.

4. **Mensaje de texto.** En una sección, «+ Mensaje». Esperado: un paso inactivo (borrador) con el texto de relleno. Abrirlo en la lista (botón de la fila). En el panel, borrar el relleno, escribir una frase, marcar «Activo» y «Guardar este paso». Esperado: «Guardado». Recargar: el texto y activo se conservan.

5. **Activar vacío (control negativo).** Duplicar ese mensaje, dejar la copia sin texto y sin archivo, intentar activarla y guardar. Esperado: mensaje «Para activar el micro escriba texto o suba media (admin clásico / + contenido).» y la copia sigue inactiva.

6. **Imagen.** En «Añadir paso» de la misma sección, elegir un JPG o PNG menor de 5 MB y enviar el formulario (con o sin texto). Esperado: el paso muestra miniatura o la leyenda de archivo, y «archivo subido». Recargar: `media_url` sigue.

7. **Vídeo y estado.** Subir un MP4 pequeño. Esperado: aviso de vídeo recibido / procesando, badge «Procesando video…» si el encode es async. Pulsar «Refrescar estado» en el panel. Esperado: el badge sigue en procesando, pasa a «Listo para WhatsApp» o a «Video no apto para WhatsApp». No hay porcentaje. Se puede recargar; el estado sale de `encode_status`.

8. **Entrega del vídeo.** En el panel del vídeo, elegir «enlace» (`video_entrega=enlace`) y enviar ese formulario. Esperado: mensaje «Video por enlace eki.» Volver a «whatsapp» y enviar. Esperado: «Video adjunto en WhatsApp.»

9. **Mover.** Arrastrar un mensaje dentro de su sección (manija de puntos). Esperado: el número de orden cambia sin alerta y sin recarga completa; el mensaje no salta a otra sección. Arrastrar la sección nueva por su manija. Esperado: el bloque entero cambia de lugar y sus mensajes siguen juntos.

10. **Desactivar y duplicar.** En la fila, ✕ desactivar (confirmar). Esperado: badge borrador, el paso sigue en la lista. Duplicar (ícono de copia). Esperado: una copia inactiva justo debajo, título con «(copia)».

11. **General y calendario.** En «General, entrega y calendario (drip)», cambiar la descripción. No tocar la fecha. Guardar. Esperado: la descripción nueva; la fecha de drip que había sigue igual en «Drip guardado» (el JS de hoy igual manda la fecha que ya está en los inputs; no debe borrarla). Luego poner una fecha y hora, guardar, recargar. Esperado: «Drip guardado» con esa fecha. Limpiar con «Limpiar», guardar, recargar. Esperado: sin fecha. Anotar el valor anterior si el curso de la copia lo necesitaba y restaurarlo al terminar.

12. **Llegar a publicar, sin publicar.** Localizar `#eki-mb-publicar`. Leer el `href`: debe ser `/admin/core/modulo/<MODULO_ID>/publicar/`. Se puede abrir: el GET muestra el checklist y no escribe. **No pulsar el botón** de esa pantalla. El POST es el que publica. No envía WhatsApp. Fin del guion.

## Qué anotar si algo falla

URL, texto del aviso, si la página recargó, y el id del paso. No reintentar Publicar. No subir el resultado a git si incluye datos de estudiantes.

## Plan mínimo de Playwright (sin instalar)

Dependencia solo de desarrollo, fuera de `requirements.txt` de Elastic Beanstalk. Un archivo `core/tests_browser/test_module_builder_humo.py` con `pytest-playwright`, contra el servidor local y un superusuario de prueba.

1. Abrir `/admin/module-builder/<id>/` con `EKI_MODULE_BUILDER_UI_V2=1` y comprobar que «Módulos» queda resaltado.
2. Renombrar la sección, agregar un mensaje de texto y ver la etiqueta «Texto».
3. Pulsar «Subir mensaje» y comprobar que el orden cambió dentro de la sección.
4. Leer el `href` de `#eki-mb-publicar` y no seguirlo.

No se instala hasta que haya OK. El guion de arriba sigue siendo la prueba manual.
