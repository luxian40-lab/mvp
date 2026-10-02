# Refactor de core/views.py → package core/views/

## Objetivo
Partir core/views.py (59 funciones, ~6.6k líneas, ninguna clase) en un package por
responsabilidad, SIN cambiar lógica. Es un monolito Django (eki) en producción en AWS EB;
el webhook de WhatsApp es el producto principal y no se puede romper. Un solo desarrollador.

## Regla de oro
MOVER, no reescribir. Un bloque por commit. Mover y refactorizar son commits distintos.
Nunca tocar lógica, nombres, decoradores ni orden de lógica dentro de una función.

## Estado (actualizar al cerrar cada bloque)
- [x] Package creado: core/views.py → core/views/legacy.py; __init__.py reexporta cada nombre
      EXPLÍCITO (nunca `import *`: no exporta nombres con guion bajo). Commit a0f6790e
- [x] Fix de bug previo: `redirect` faltaba en admin_panel (commit 61246259)
- [x] Bloque 1: 21 funciones de admin → core/views/admin_panel.py
- [x] Bloque 2: serve_media_proxy, stream_media, obtener_archivos_modulo_view,
      descargar_archivo_multimedia → core/views/media.py (commit ef30b232)
- [x] Bloque 3: audio.py → _audio_path_para_whisper, _transcribir_audio_twilio, _transcribir_con_vosk
- [x] Bloque 4: webhook_comercial.py → bot_comercial_webhook, _encolar_bot_comercial_si_async
- [x] Bloque 5: twilio_transporte.py → _twilio_post_plano, _es_status_callback_twilio,
      _encolar_twilio_edu_si_async, _escape_twiml, _reenviar_media_fallida_como_enlace,
      _registrar_estado_twilio_callback, _twilio_max_body_chars, _segmentar_texto_twilio,
      youtube_hace_solo_enlace_en_texto, _enviar_mensaje_twilio_segmentado
- [x] Bloque 6: empleabilidad.py (_haversine_metros, _activar_radar_empleabilidad_si_aplica,
      _radar_msg_si_aplica, _procesar_ubicacion_empleabilidad, _cliente_habilita_proximidad),
      certificados_wa.py (_es_respuesta_liberar_certificado, _es_ack_certificado,
      _intentar_responder_envio_certificado), ventana_drip.py
      (_cliente_en_ventana, _cliente_habilita_pregunta_abierta_final,
      _pregunta_abierta_final_pendiente, _mensaje_bloqueo_drip_view)
- [x] Bloque 7: webhook_meta.py → _sandbox_inbound_repetido, _encolar_sandbox_si_async,
      _aplicar_sandbox_menu, _procesar_meta_webhook
- [x] Bloque 8: webhook_twilio.py → _procesar_twilio_webhook y _procesar_twilio_webhook_cuerpo,
      movidas tal cual (el cuerpo son ~3.600 líneas en UNA función)
- [x] Bloque 9: entrada.py → whatsapp_webhook (puerta única Meta/Twilio/Nat), sola en su archivo
- [ ] Fase 2 (después del split, con tests de caracterización): partir
      _procesar_twilio_webhook_cuerpo por estado_chat (habeas, cédula, confirmación, listo,
      evaluación, certificado) en funciones que reciben contexto y devuelven respuesta;
      el cuerpo queda como despachador.

## Reglas por bloque
1. Antes de mover, listar qué nombres de legacy.py usa cada función. Lo que se quede en
   legacy.py se importa desde `.legacy`; no duplicar.
2. Si algo que se queda en legacy.py llama a una función movida, importarla desde el módulo nuevo.
3. Copiar a cada módulo nuevo los imports necesarios con la ruta relativa ya corregida
   (`from ..models`, no `from .models`).
4. En core/views/__init__.py cambiar el origen de los nombres movidos; mismos nombres, ninguno se pierde.
5. Revisar __file__, Path( y BASE_DIR en lo movido (bajar un nivel de carpeta cambia rutas).
6. No tocar ningún patch() sin avisar (ver abajo).

## Patches de tests (trampa principal)
`patch("core.views.X")` reemplaza el nombre en el __init__, pero quien llama a X resuelve el
nombre en los globals de SU módulo. El target correcto es el módulo donde se USA, no donde se
reexporta. Hoy los 8 patches apuntan a `core.views.legacy.<nombre>`:
_aplicar_sandbox_menu, _contexto_fallback_web_agro, _encolar_bot_comercial_si_async,
_encolar_twilio_edu_si_async, _procesar_bot_comercial_twilio_webhook, _procesar_meta_webhook,
_procesar_twilio_webhook, _transcribir_audio_twilio.
Al mover una función parcheada, hay que decirme y actualizar el target al módulo desde donde
la llama su caller. Archivos con patches: core/tests_sandbox_canal_meta.py,
core/tests_twilio_webhook_security.py, core/tests_nati.py (pytest),
core/tests_sandbox_menu_event_engine.py, core/tests_twilio_inbound_audio.py.

## Verificación al cerrar cada bloque
1. `ruff check --select F821 core/views/` → F821 = nombre no definido = bug en runtime.
   No correr `ruff --fix` ni limpiar F401 en legacy.py: algunos nombres solo están importados
   para que los patch() los encuentren. La limpieza va al final con la suite completa.
2. `python manage.py check`
3. `python manage.py test core.tests_admin_package aprende.tests core.tests_flujo_whatsapp_b2b core.tests_listo_continuar_trigger --keepdb`
4. `python scripts/verificar_split_views.py 56929af7` → faltan/nuevas/distintas deben salir
   vacíos (compara por AST contra el commit previo al split; ignora from . vs from ..).
5. Commit solo con el movimiento.
6. Import real: usar django.setup() antes de importar core.views.<modulo>.

## Import que el AST no ve
`core/views/__init__.py` reexporta `_extraer_texto_archivo_simple` desde
`core.bot_comercial.webhook`. En el baseline (`56929af7`, `core/views.py` de un
solo archivo) `from core.views import _extraer_texto_archivo_simple` fallaba con
ImportError. Ahora funciona: es una mejora, no un movimiento. `webhook.py` no
importa `core.views` a nivel de módulo; los `from core.views import ...` de las
líneas 50 y 55 están dentro de funciones, así que no hay ciclo al cargar el worker.

## Deuda previa conocida (fallan igual en el baseline 56929af7; NO causados por el split)
Lista permanente del entorno completo (`.venv-full`, 2026-10-01): `scripts/baseline_failures_before.txt`.
`pytest.ini` solo recoge `tests.py` / `test_*.py` (no `tests_*.py`); esa corrida dio 54 passed y cero `FAILED` en ambos árboles. La lista de pytest del archivo se obtuvo con `--override-ini python_files=tests_*.py test_*.py`.
- core.tests_admin_mejoras_onda3.CommandSearchTests.test_admin_search_endpoint_ok
- core.tests_admin_modulo_guardar_reto.GuardarRetoDesdeAdminTests.test_guardar_el_reto_con_secciones_intercaladas
- core.tests_agentes_whatsapp.CheckpointSinTitularTests.test_pausa_no_abre_con_carlos
- core.tests_host_isolation.AdminNoStudentsTests.test_estudiante_whatsapp_no_es_staff_ni_entra_admin
- core.tests_module_builder_ui.ModuleBuilderViewTests.test_add_micro_form_accepts_pdf
- core.tests_module_steps.CheckpointIgnoraDripFinModulo1Tests.test_fin_modulo_1_con_pasos_y_eval_abcd_drip_no_bloquea_agentes
- core.tests_confirmando_datos_webhook.test_webhook_confirmando_datos_con_progreso_incluye_modulo_no_fallback_generico
- core.tests_intent_prosa_larga (dos tests: subcadena `si` / `seguir` en `detect_intent`)
- core.tests_nat_foto.test_webhook_foto_entrada_y_foto_producto (`core.nat_cuota` no existe)
- portal/tests_*.py y portal/tests_wallpaper_admin.py (mismos nodos en ambos árboles)
Con Celery y reportlab instalados, el encolado (`test_bot_comercial_webhook_encola_celery`, `tests_smoke_nat_celery`) y `test_png_buffer_a_pdf_genera_pdf_valido` pasan en ambos árboles.
`test_onboarding_natural.py` está en `.gitignore`. Copiado al worktree `56929af7` y corrido con `manage.py test`, falla igual: `AssertionError: 'nombre completo' not found in 'para continuar, debes aceptar el tratamiento de datos personales (habeas data). ¿aceptas? responde sí para continuar.'` El archivo se borró del worktree después. Deuda previa, no bloquea el split.
Si un fallo de un archivo versionado aparece solo en el árbol actual, lo causó el cambio.

## Deploy
`eb deploy` empaqueta HEAD (sc: git), no el directorio de trabajo: lo que no está commiteado
no sube. Rollback: versión main-agentes-fallback-20261001-171500. Antes de desplegar: suite
completa, smoke manual (staff: /admin/dashboard/, /admin/conversaciones/; WhatsApp: hola,
listo, *aula*, pedir un video/PDF) y mirar `eb logs` tras el deploy.

## Prompt plantilla para un bloque nuevo
"En core/views/legacy.py, mueve <funciones> a core/views/<archivo>.py sin cambiar lógica.
Aplica las reglas por bloque de docs/REFACTOR_VIEWS.md. Lista dependencias antes de mover.
Avísame si algún test hace patch() de alguna de estas. Al final corre la verificación
(ruff F821, check, tests, script AST) y muéstrame la salida completa."
