# Continuar eki — 8 de octubre de 2026

Handoff para la siguiente sesión. La rama local va adelante de producción. No desplegar `HEAD` completo.

## Dónde quedó el código

- Rama: `slice/escalabilidad-base`. Commits de esta tanda no están en `origin`.
- Producción `eki-prod-final`: versión `main-diploma-pqrs-meta-20261008-191900`.
- Árbol que está en el aire: commit `624113b8` (el diploma/PQRS `9ed75b92` aplicado encima del café `27fa0835`, que a su vez está encima del listado `73989a00`).
- Rollback de esa versión: `main-experto-cafe-20261008-184457`.
- `eb deploy` empaqueta `git archive` de `HEAD` del directorio desde el que se corre. Un archivo nuevo sin commit no sube y el web arranca con `ImportError`.

## Cómo commitear y desplegar

1. Un cambio por commit. No mezclar con el árbol sucio (Aprende, settings, docs de auditoría, scripts `qa_*`, conectores ajenos).
2. Commit en `slice/escalabilidad-base`.
3. No hacer `eb deploy` desde esa rama. Trae decenas de commits que producción no tiene (webhooks, campañas, consentimiento, presupuesto LLM).
4. Worktree limpio desde `624113b8`, `git cherry-pick` solo del commit nuevo. Si aplica limpio, desplegar desde esa carpeta.
5. Label `main-<tema>-YYYYMMDD-HHMMSS`. Anotar la versión anterior (`eb status`) antes de subir.
6. Después: `/health/` en `http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/health/` debe ser 200.
7. El commit de la rama y el del worktree no son el mismo hash. El siguiente cherry-pick sale del hash que quedó en producción, no de `73989a00`.

Reglas fijas que ya están en `.cursor/rules/eki.mdc`: no tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`; firma Meta/Twilio antes de cualquier lógica; `patch()` al módulo que usa el nombre.

## Meta ya hace esto

- Línea de producto y menú sandbox (agentes, incluido el experto en café).
- Imagen del diploma. `enviar_whatsapp_twilio` llama a `core/views/diploma_meta.py` y, si el texto es el certificado, sale por Graph y no llega a la API de Twilio. Cubre el cierre del curso y el botón de enviar del admin.
- Respuesta de PQRS: `core/pqrs_respuesta.py` usa `core/views/pqrs_meta.py`. Si Meta falla, el caso sigue pendiente.
- Pruebas: `core/tests_diploma_y_pqrs_meta.py` y `core.tests_pqrs_agent.TestPQRSRespuestaWhatsApp`.

## Twilio se queda solo para el aula

Ese es el destino. El aula es quien escribe al número Twilio y recibe módulos, audio y *listo*. Vive en `core/views/webhook_twilio.py` (~3.500 líneas en una función). No se parte ni se borra hasta noviembre, y solo si dos semanas el webhook llega en cero. Hasta entonces se desmonta lo demás, un archivo por commit, sin abrir ese cuerpo.

### Sigue en Twilio y se puede quitar después del aula

Cada fila es un commit. No borrar la función `enviar_whatsapp_twilio`: el aula la usa para el video de clase.

| Qué | Dónde | Condición para quitarlo |
|---|---|---|
| Aviso previo del diploma con plantilla `HX…` | `core/certificado_presencial_service.py` (`enviar_previo_whatsapp`, `_enviar_plantilla_twilio_cert`) y `core/certificado_service.py` (`_enviar_plantilla_media_twilio`, `enviar_plantilla_twilio`) | Primero una plantilla de imagen en Meta. Sin eso, pasadas 24 h el diploma queda mudo (Meta rechaza la imagen de sesión). |
| Campañas HSM viejas | `core/services.py`, `core/admin_campana_actualizado.py`, `core/enviar_plantillas.py` | Confirmar que no hay campaña viva en Twilio. El camino nuevo ya es `CampanaMeta`. |
| Mensaje del admin al estudiante, avisos, gamificación | `core/admin/estudiantes.py`, `core/admin/cursos.py`, `core/mensajes_push.py`, `core/gamificacion_actions.py`, `core/seguimiento_proactivo.py`, `core/whatsapp_service.py` | El mismo texto sale por `enviar_meta` / Graph. |
| Bot comercial y carrusel demo fuera de la línea Meta | `core/bot_comercial/webhook.py`, `core/bot_comercial/productos_media.py`, `core/catalogo_demo_carousel.py` | Dentro del sandbox Meta ya se intercepta. Fuera, sigue Twilio. |
| Reintento de media | `core/media_entrega.py` | Solo si el log es de Twilio. Un video de aula no se mueve. |

El primer corte de la próxima sesión es el aviso `HX…`, y solo cuando exista la plantilla Meta equivalente. No es borrar Twilio entero.
