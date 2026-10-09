# Continuar eki — 8 de octubre de 2026

Handoff para la siguiente sesión. La rama local va adelante de producción. No desplegar `HEAD` completo.

## Dónde quedó el código

- Rama: `slice/escalabilidad-base`. Commits de esta tanda no están en `origin`.
- Producción `eki-prod-final`: versión `main-diploma-plantilla-meta-20261008-200300`.
- Árbol que está en el aire: commit `6ce96dd0` (la plantilla de diploma `ac602806` aplicada encima de `624113b8`).
- Rollback de esa versión: `main-diploma-pqrs-meta-20261008-191900`.
- `eb deploy` empaqueta `git archive` de `HEAD` del directorio desde el que se corre. Un archivo nuevo sin commit no sube y el web arranca con `ImportError`.

## Cómo commitear y desplegar

1. Un cambio por commit. No mezclar con el árbol sucio (Aprende, settings, docs de auditoría, scripts `qa_*`, conectores ajenos).
2. Commit en `slice/escalabilidad-base`.
3. No hacer `eb deploy` desde esa rama. Trae decenas de commits que producción no tiene (webhooks, campañas, consentimiento, presupuesto LLM).
4. Worktree limpio desde `6ce96dd0`, `git cherry-pick` solo del commit nuevo. Si aplica limpio, desplegar desde esa carpeta. La carpeta usada el 8 de octubre es `C:\Users\luxia\OneDrive\Escritorio\eki_deploy_diploma`.
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

El aula es Aprende: el mismo curso. Quien escribe y recibe módulos, audio y *listo* sigue en `core/views/webhook_twilio.py` (~3.500 líneas en una función). No se parte ni se borra hasta noviembre, y solo si dos semanas el webhook llega en cero. Hasta entonces se desmonta lo demás, un archivo por commit, sin abrir ese cuerpo.

La plantilla de diploma en Meta ya se puede usar. En admin, Configuración Global, campo «Diploma — nombre de plantilla Meta». Encabezado imagen; cuerpo `{{1}}` nombre, `{{2}}` curso, `{{3}}` código. Vacío: se sigue mandando la imagen de sesión (la persona tiene que haber escrito en 24 h, o escribir y reenviar). Con nombre, y cuando Meta la haya aprobado, el botón Enviar certificados por WhatsApp usa esa plantilla. Si Meta la rechaza, cae a la imagen. El aviso `HX…` de Twilio sigue hasta que esa plantilla esté aprobada y el envío real salga bien.

### Sigue en Twilio y se puede quitar después del aula

Cada fila es un commit. No borrar la función `enviar_whatsapp_twilio`: el aula la usa para el video de clase.

| Qué | Dónde | Condición para quitarlo |
|---|---|---|
| Aviso previo del diploma con plantilla `HX…` | `core/certificado_presencial_service.py` (`enviar_previo_whatsapp`, `_enviar_plantilla_twilio_cert`) y `core/certificado_service.py` (`_enviar_plantilla_media_twilio`, `enviar_plantilla_twilio`) | Solo después de que la plantilla de imagen en Meta esté aprobada y un envío real salga bien. El código ya la usa si el nombre está en Configuración Global. |
| Campañas HSM viejas | `core/services.py`, `core/admin_campana_actualizado.py`, `core/enviar_plantillas.py` | Confirmar que no hay campaña viva en Twilio. El camino nuevo ya es `CampanaMeta`. |
| Mensaje del admin al estudiante, avisos, gamificación | `core/admin/estudiantes.py`, `core/admin/cursos.py`, `core/mensajes_push.py`, `core/gamificacion_actions.py`, `core/seguimiento_proactivo.py`, `core/whatsapp_service.py` | El mismo texto sale por `enviar_meta` / Graph. |
| Bot comercial y carrusel demo fuera de la línea Meta | `core/bot_comercial/webhook.py`, `core/bot_comercial/productos_media.py`, `core/catalogo_demo_carousel.py` | Dentro del sandbox Meta ya se intercepta. Fuera, sigue Twilio. |
| Reintento de media | `core/media_entrega.py` | Solo si el log es de Twilio. Un video de aula no se mueve. |

El aviso `HX…` se quita cuando el envío real con la plantilla Meta esté aprobado. No es borrar Twilio entero. Aprende y el aula son el mismo curso.
