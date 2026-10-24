# Referencia del refactor (medición del 24 de octubre de 2026)

## 1. Dos líneas, un motor de curso

| | Principal (`uso = completa`) | Línea 2 (`uso = solo_cursos`) |
|---|---|---|
| Registro | `core/lineas/meta.py` (`LineaMeta`, `META_LINEAS` o variables históricas) | Igual. `WHATSAPP_PHONE_NUMBER_ID_2`, `WHATSAPP_NUMERO_2_E164` |
| Pregunta hoy | `es_modo_twilio()` es `False` | `es_modo_twilio()` es `True` (`core/lineas/variante.py`) |
| Antes del curso | Habeas, cédula, menú por plan (`planes_linea.resolver_plan`) | Habeas, cédula, directo al curso |
| Oferta | Carrusel (`lineas/oferta.cursos_de_la_linea`), asesores (`oferta.modos_permitidos`) | Solo el curso. Asesor pedido -> `TEXTO_LINEA_MODO_TWILIO` |
| Plantillas | WABA principal | WABA propia (`WHATSAPP_BUSINESS_ACCOUNT_ID_2`); no cruzan (`lineas/campana.py`) |
| Curso | Motor compartido | Motor compartido |
| Después | Menú | Certificado y cierre; otra campaña puede inscribir el siguiente curso |

Decisiones: una persona puede estar en las dos líneas; la línea 2 tiene cursos en serie; vendrán más líneas (perfil en la base).

Estado hoy: la sesión de menú es por línea (`SandboxCanalSesion.phone_id`, `lineas/sesion.py`). El estado del curso (`estado_chat`, `estado_onboarding`, `contexto_temporal`) es uno por teléfono en `Estudiante`. El candado es por teléfono (`core/locks.py`, `eki:wa:tel:<tel>`).

## 2. Recorrido de un mensaje Meta

1. `core/views/entrada.py` `whatsapp_webhook`: firma, `webhook_evento` (idempotencia), statuses.
2. `_procesar_meta_por_mensaje` -> `procesar_sandbox_meta_async` o `_aplicar_sandbox_menu`.
3. `salida_por_phone_id` + `canal_sandbox_si_meta()` (reemplaza `twilio.rest.Client` por `MetaOutboundClient`).
4. `sandbox_menu.dispatch_sandbox_menu`: opt-out, habeas, cédula, confirmación, aula, racha, `resolver_ruta_sandbox`. Línea 2 -> `'cursos'`.
5. `'cursos'` -> `webhook_twilio._procesar_twilio_webhook` -> cortes de `lineas/identidad.py` -> `_procesar_twilio_webhook_cuerpo`.
6. Cuerpo -> `get_response_for_intent` -> `module_steps` -> parser de marcadores -> `Client(...)`.

## 3. Mapa del cuerpo (`core/views/webhook_twilio.py`)

| Líneas | Tramo |
|---|---|
| 90–140 | Filtros: status callback, vacío, duplicado por `MessageSid` |
| 140–490 | Preámbulo: audio, eventos IA, ubicación, carrusel prospecto, estudiante |
| 489–1016 | Onboarding: habeas (613), cédula (656), confirmación (737), corrección (966) |
| 1017–1528 | `ACTIVO`: gate *listo*, PQRS, reenvío media, menú 1–4 |
| 1529–3000 | Estados de agente |
| 3000–3100 | IA de respaldo |
| 3106–3316 | Envío: parser de marcadores y `Client` |

Estados y entradas que leen (AST):

| Estado | Línea | Líneas propias | Lee |
|---|---|---|---|
| `ESPERANDO_CEDULA` | 656 | 79 | estudiante, msg_body, msg_from, re, telefono_limpio |
| `CONFIRMANDO_DATOS` | 737 | 227 | estudiante, msg_body, msg_from, telefono_limpio |
| `ACTIVO` | 1017 | 447 | estado_chat, estudiante, msg_body, msg_from, telefono_limpio |
| `esperando_codigo_empleabilidad` | 1529 | 76 | estudiante, msg_body |
| `esperando_respuesta_pregunta_abierta_final` | 1606 | 213 | estudiante, msg_body, msg_sid, telefono_limpio |
| `curso_finalizado` | 1821 | 22 | estudiante |
| `esperando_respuesta_asistente` | 1845 | 179 | estudiante, msg_body |
| `esperando_respuesta_reto` | 2026 | 303 | estudiante, evidencia_imagen_type, evidencia_imagen_url, msg_sid, telefono_limpio |
| `esperando_respuesta_tutor_ia` | 2331 | 85 | estudiante, msg_body |
| `esperando_respuesta_progreso` | 2418 | 53 | estudiante, msg_body |
| `esperando_respuesta_recuperacion` | 2473 | 29 | estudiante, msg_body |
| `esperando_respuesta_modulo` | 2504 | 475 | estudiante, msg_body |
| `esperando_seleccion_curso` | 2982 | 49 | estudiante, msg_body, msg_from, msg_lower, telefono_limpio |

Salida común: `texto_respuesta` (reasignada 112 veces), consumida por el tramo de envío.

Probablemente muertos: ningún código asigna `esperando_respuesta_tutor_ia`, `esperando_respuesta_progreso` ni `esperando_respuesta_recuperacion`. `elif False and …` en la línea 1149. Confirmar con conteo en producción antes de borrar.

Orden de extracción: cédula, curso finalizado, recuperación, progreso, tutor IA, asistente, confirmación, pregunta final, reto, módulo, selección de curso.

## 4. Puntos frágiles

- Reemplazo global de `twilio.rest.Client`: `core/sandbox_canal.py:97` y `core/views/twilio_transporte.py:353`. Con hilos, un mensaje restaura el cliente mientras otro sigue enviando. Hoy no estalla porque el worker es prefork con concurrencia 1.
- `enviar_whatsapp_twilio` y `_enviar_mensaje_twilio_segmentado` salen por Meta si `sandbox_meta_activo()`.
- Parser `[MULTI_MSG]`/`[SEP]` copiado: cuerpo 842, 1170, 1400, 3166; además `inicio_curso`, `lineas/paso`, `lineas/entrega`, `module_steps` (2), `response_templates`, `selector_curso`.
- `time.sleep` por `[DELAY:n]`: retiene worker y candado.
- `contexto_temporal = None` en 15 sitios del cuerpo borra claves ajenas (por ejemplo `cert_envio_pendiente`).
- `estado_onboarding` se escribe desde 18 archivos.

## 5. Dominios destino para los archivos sueltos de `core`

| Paquete | Ejemplos |
|---|---|
| canal | `sandbox_canal`, `twilio_*`, `meta_*`, `wa_*`, `whatsapp_service`, envíos de `utils` |
| conversacion | `sandbox_menu`, `intent_detector`, `response_templates`, `selector_curso`, `habeas_respuestas`, estados |
| curso | `module_steps`, `module_builder*`, `drip_*`, `helpers_examenes`, `inscripcion_curso`, `modulo_publicacion` |
| agentes | `tutor_ia_modulo`, `agentes_ia`, `utils_ia`, `openai_compat`, `nat*`, `rag_*`, `bot_comercial/` |
| campanas | `campana_*`, `plantilla_*`, `enviar_plantillas`, `mensajes_push`, `reenganche_meta` |
| certificados | `certificado_*`, `generador_certificados`, `utils_certificados` |
| gamificacion | `gamificacion*`, `recompensas`, `rachas_linea` |
| analitica | `dashboard_avanzado`, `metricas_empresa`, `telemetria`, `infra_monitor`, `copiloto_ops` |
| admin_vistas | `views_*.py` sueltos |
