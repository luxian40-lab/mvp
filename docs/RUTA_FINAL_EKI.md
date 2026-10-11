# Ruta final eki

Junto con `docs/PLAN_P4_A_P8_EKI.md` (el detalle técnico), es todo lo que Cursor necesita.

Principio: cerrar solo lo que protege el lanzamiento. Lo demás va al backlog (sección 7).

Orden: Deploy A (tú) → Lote 1 → Lote 2 → Lote 3 → Deploy B → Lote 4 → Lote 5 → Lote 6 → Deploy C → pre-lanzamiento → ensayo → lanzamiento. Los lotes de Cursor pueden correr mientras haces los pasos manuales.

## 1. DEPLOY A (tú, ~2 h)

Contenido: todo lo que hay en `slice/escalabilidad-base` hasta `476a637b` (P0–P3, U–Y, P8, ajustes F–H). Los flags nuevos quedan apagados.

### 1.1 Verificar en EB (no pegues valores en ningún chat)

`eb printenv`

Deben existir y no estar vacías: `EKI_ALLOWED_HOSTS` (admin, app, aprende, studio y host interno de EB), `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY`, `INTEGRACION_API_REQUIRE_KEY`, `WHATSAPP_APP_SECRET` (compara los últimos 4 caracteres con Meta → App Dashboard → Settings → Basic). `TWILIO_VALIDATE_SIGNATURE` no debe ser `false`. Si falta alguna, el web no arranca.

### 1.2 Variables a poner/confirmar en EB

| Variable | Valor |
| --- | --- |
| `SANDBOX_CELERY_ASYNC`, `WEBHOOK_CELERY_ASYNC`, `NAT_WEBHOOK_CELERY_ASYNC` | `false` |
| `META_REENGANCHE_ENABLED` | `false` |
| `EKI_BEHIND_CLOUDFLARE` | `true` (y el origen solo acepta tráfico de Cloudflare) |
| `AULA_LOGIN_REQUIERE_DOCUMENTO` | `true` (recomendado) |
| `SECURE_HSTS_SECONDS` | `86400` (súbelo después de estar estable) |

### 1.3 Red de seguridad

- Snapshot manual de RDS: `pre-deploy-a`.
- Protección de rama en `main` (check `test` obligatorio).

### 1.4 Desplegar

- PR de `slice/escalabilidad-base` a `main`; CI verde; merge.
- Desde `main`:
  - `.\scripts\eb_precheck_main.ps1`
  - `.\scripts\eb_deploy_main.ps1`
- Health Green. Los cuatro procesos (web, worker, worker_rag, beat) arriba. Un mensaje desde el teléfono interno autorizado (`573026480629`) y respuesta correcta.
- Logs sin `ImportError`, `NameError`, errores de Redis.

### 1.5 Si algo falla

- Línea Meta sin respuesta → primero `WHATSAPP_REQUIRE_SIGNATURE=false` en EB (sin redeploy) y revisa el secreto.
- El web no arranca → `eb deploy eki-prod-final --version main-20261001-213708`.

### 1.6 Comprobaciones de solo lectura (en el servidor)

```
python manage.py reenganche_dry_run --dias 1
python manage.py campanas_pendientes
free -m
ps aux --sort=-rss | head -15
```

Guarda la salida (sirve para decidir el pool del worker).

### 1.7 Versión de Graph

`v19.0` ya no existe; Meta la redirige a una versión vieja sin avisar. En EB: `WHATSAPP_API_VERSION=v24.0`. Prueba con tu teléfono interno: texto, lista/carrusel, imagen, video, audio entrante, plantilla. Si algo falla, quita la variable.

### 1.8 Decisión de async (con la salida de `free -m`)

- Si quedan ≥ 1,2 GiB libres: `CELERY_CONCURRENCY=2` en EB y puedes encender los tres flags async de a uno (orden: `WEBHOOK_`, `NAT_`, `SANDBOX_`), con una prueba desde el teléfono interno entre cada uno. Rollback: flag en `false`.
- Si no: lanza con async apagado. Con ~150 personas el camino síncrono aguanta; la idempotencia de P1 protege contra los reintentos de Meta. Reevalúalo después del lanzamiento con datos reales.

## 2. PREÁMBULO (pégalo al inicio de cada prompt de Cursor, o guárdalo en `.cursor/rules`)

```
PREÁMBULO
- Rama slice/escalabilidad-base. No mergees ni despliegues.
- Aplica las reglas 0.1 de @docs/PLAN_P4_A_P8_EKI.md (no tocar el cuerpo de _procesar_twilio_webhook_cuerpo, expand/contract, sin secretos, Meta primero, umbrales de Meta en settings con fecha de verificación).
- AHORRA TOKENS: corre localmente solo los tests del área que tocas; NO corras la suite completa (lo hace el CI). Un solo push al final del lote. No re-expliques lo que ya está en el plan. No leas archivos que no necesitas.
- No refactorices ni "mejores" nada fuera del alcance. Hallazgo fuera de alcance = una línea, sin arreglarlo.
- Si dudas en una decisión de producto, elige la opción más segura, anótala en una línea y sigue. No me hagas preguntas salvo que algo bloquee.
- INFORME FINAL, máximo 15 líneas: commits (hash + mensaje) · migraciones · tests locales (passed/skipped) · decisiones no obvias · hallazgos · riesgos · [MANUAL] pendientes · URL del run de CI, SHA y resumen pytest (passed/failed/skipped). No pegues código ni logs largos.
```

## 3. LOTES DE CURSOR

### Lote 1 — Límite de velocidad (429) y tests

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 1.

1. Localiza el middleware que devuelve 429 en portal/studio. Reporta en 5 líneas: qué rutas cubre y exime (¿`/webhook/whatsapp/`, `/webhook/ia-bot-comercial/`, `/health/`?), con qué clave identifica al cliente (`REMOTE_ADDR`, `X-Forwarded-For` o `CF-Connecting-IP`), límites y backend de cache (locmem o Redis), y por qué pytest no activa `_running_tests`.
2. Si identifica por `REMOTE_ADDR` sin pasar por `client_ip_from_request`, cámbialo para usar ese helper (commit aparte). Exime de su límite `/webhook/` y `/health/` (Meta y los balanceadores envían ráfagas desde pocas IPs). Tests de ambos.
3. En `settings_test` desactiva ese límite y añade un test que pruebe el límite con `override_settings` y cache limpio. Fixture autouse que limpie el cache entre tests.
4. Dime cuántos de los 40 fallos de suite-completa desaparecen y lista los que quedan agrupados por causa (una línea por grupo).

### Lote 2 — P6 aislamiento entre clientes

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 2.

Implementa la sección 4 completa de `@docs/PLAN_P4_A_P8_EKI.md` (P6): `portal/tests_tenant_isolation.py` con marcadores `ZZB-`, todos los roles, enumeración automática de rutas con registro `PARAMS_B` (un parámetro sin entrada hace fallar el test), exports xlsx/csv, agente de retención con LLM mockeado, aula (profesor e IDOR de estudiante), API LXP y verificación pública de certificados.

Si hay fallos: en un commit aparte arréglalos con `core/tenancy.py` (`get_for_portal` / `TenantQuerySet`) y vuelve a correr hasta que pase. En el informe pon solo una tabla de los fallos encontrados (ruta, método, rol, qué filtró) y cómo se corrigió. Añade la guardia estática informativa.

### Lote 3 — P5 costo de IA, antiflood, solo registrados

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 3.

Implementa la sección 5 completa de `@docs/PLAN_P4_A_P8_EKI.md` (P5.1 a P5.6): `UsoLLM`, presupuesto diario y por organización con modo económico al 70 % y degradación al 100 % (nunca bloquea `listo` ni el curso), antiflood, solo registrados (inspecciona primero qué hace hoy el webhook con un número desconocido y repórtalo en 3 líneas), `plan_linea_auditar`, tope de números nuevos por día, `UsoLLM` en admin de solo lectura y widget de gasto en Inicio.

Precios: verifica en la página oficial de precios y fecha el comentario; si no puedes verificar uno, dilo.

Flags con defaults seguros: `LLM_PRESUPUESTO_DIARIO_USD=10`, `LINEA_MAX_MSG_MIN=12`, `LINEA_MAX_NUEVOS_DIA=300`, `LINEA_META_SOLO_REGISTRADOS=true` (no debe bloquear el onboarding habeas→cédula de quien viene de una campaña: test explícito).

### Lote 4 — P4-lite (a): consentimiento, modelo, claim, estados

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 4.

De `@docs/PLAN_P4_A_P8_EKI.md` implementa la sección 6.0 (opt-in/opt-out) y la 6.A (que MANDA sobre 6.1–6.10) sobre `CampanaMeta`/`EnvioCampanaMeta`:

- Opt-in/opt-out en `Estudiante`, texto de habeas versionado, backfill sin inventar fechas, palabra completa de baja.
- Primero ejecuta el comando `auditar_envios_duplicados` sobre `EnvioCampanaMeta`. Si hay duplicados, DETENTE y repórtalos. Si no, sigue.
- Columnas nuevas (expand), estados `PENDIENTE`/`ENVIANDO`/`ENVIADO`/`ERROR`/`ERROR_REINTENTABLE`/`INCIERTO`/`OMITIDO`, `UniqueConstraint(campana, estudiante)`, claim atómico antes del POST, timeout → `INCIERTO` (nunca se reenvía solo), `ENVIANDO` > 10 min → `INCIERTO`, mapeo de errores de Meta desde settings, bandera de token consultada por envío, ventana (texto libre) / plantilla / `OMITIDO`.
- `core/meta_estados.py` actualiza también `EnvioCampanaMeta` por wamid (`estado_entrega`, `error_codigo`, `entregado_en`, `leido_en`) y reconcilia `INCIERTO` por `biz_opaque_callback_data="envio:{id}"` (verifica en la doc oficial el nombre del campo y su límite de longitud).
- Flag `META_CAMPANAS_V2_ENABLED` (default `false`). Con `false` se usa el camino actual.
- Tests de 6.A y 6.10 que correspondan a este lote.

### Lote 5 — P4-lite (b): velocidad, pausa, preflight, admin

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 5.

De `@docs/PLAN_P4_A_P8_EKI.md` implementa lo que falta de la sección 6 (con 6.A mandando): token bucket global en Redis con Lua (`WA_META_MPS=20`, `WA_META_BURST=20`; verifica el tope real en la doc de Meta y fecha el comentario), hueco por destinatario (`WA_DESTINO_GAP_SEG`), tope de contactos nuevos en 24 h (`META_LIMITE_CONTACTOS_24H=1000`), reemplazar el `time.sleep(0.35)` por bucket + retry de Celery, un `130429` reintenta con backoff sin abandonar el lote, pausa automática por tasa de fallo (> 15 % de los primeros 100 aceptados) contando respuestas con error Y statuses `failed` posteriores durante 30 min, comando `campana_reanudar`, `campana_preflight` (token, plantilla aprobada, destinatarios con opt-in, margen frente al tope, duración estimada), `fecha_programada` en `CampanaMeta` + tarea de beat `enviar_campanas_meta_programadas` cada 5 min, comando `meta_token_reset` si no existe, y el panel de campaña en el admin (conteos por estado y por `estado_entrega`, % entregado/leído, errores por código, `INCIERTO` sin confirmar, botones Pausar/Reanudar/Reenviar reintentables, nunca `INCIERTO`).

Servidor de Graph falso (`core/tests_support/graph_fake.py`) con éxito, secuencia de `131056`, `131047`, `190` y timeout, y `WHATSAPP_GRAPH_BASE_URL` en settings. Tests de 6.10 completos.

### Lote 6 — Observabilidad mínima

Aplica el PREÁMBULO de `@docs/RUTA_FINAL_EKI.md`. Lote 6.

De la sección 7 (P8-e) de `@docs/PLAN_P4_A_P8_EKI.md` implementa SOLO: (1) Sentry con DSN por env (sin DSN no hace nada), `send_default_pii=False` y `before_send` que elimine teléfonos, cédulas, cuerpos y cabeceras de autorización; integración Django y Celery; (2) `/health/deep/` solo staff o token de infra: DB, Redis, profundidad de colas `conversacion`/`masivo`/`celery`/`media_encode`, antigüedad del mensaje más viejo, bandera de token de Meta, y heartbeat del beat (tarea cada minuto que escribe en Redis; alerta si falta 3 min) visible en `/admin/infra/`; (3) métrica en `/admin/infra/` del % de entrantes de las últimas 24 h con canal vacío. Omite logs JSON y métricas a CloudWatch (van al backlog).

Tests del scrubbing: un error con un teléfono en el mensaje sale sin el teléfono.

## 4. DEPLOY B (tras Lotes 1–3) y DEPLOY C (tras Lotes 4–6)

Mismo procedimiento que 1.3–1.5 (snapshot, PR, CI verde, desplegar desde `main`, smoke con teléfono interno, rollback).

Deploy B — variables a revisar en EB: `LLM_PRESUPUESTO_DIARIO_USD`, `LINEA_MAX_MSG_MIN`, `LINEA_MAX_NUEVOS_DIA`, `LINEA_META_SOLO_REGISTRADOS=true`. Después: correr `python manage.py plan_linea_auditar`, asignar plan (OP1/OP2/OP3) a cada cliente y grupo en el admin, y cuando no quede ninguno sin plan, `LINEA_META_PLAN_DEFAULT=''`. Prueba: un número que no es estudiante escribe a la línea → respuesta fija, cero llamadas a IA.

Deploy C — variables: `META_CAMPANAS_V2_ENABLED=false` hasta el ensayo; `SENTRY_DSN` (crea el proyecto en Sentry); confirma que `EKI_CAMPANA_META_ENABLED` está en el valor que quieras. Prueba: `/health/deep/` responde y el heartbeat del beat aparece.

## 5. PRE-LANZAMIENTO (tuyo, en paralelo a los lotes)

### Meta

- Token de System User permanente (anota creación y rotación). `WHATSAPP_BUSINESS_ACCOUNT_ID` cargado en EB.
- `WHATSAPP_APP_SECRET` verificado y `WHATSAPP_REQUIRE_SIGNATURE` en `true`.
- Plantillas aprobadas: reenganche (categoría Utility) y bienvenida/campaña. Con su nombre e idioma en las variables de EB (`META_TEMPLATE_DRIP_REENGANCHE`).
- Calidad y nivel de mensajería del número anotados (WhatsApp Manager).
- Política de precios y de conversaciones gratuitas revisada (no des por hecho cuánto cuesta cada mensaje).

### Consentimiento (Ley 1581)

- Texto de habeas que mencione explícitamente notificaciones por WhatsApp, versionado. Revisión de tu abogado.

### AWS

- Restore de un snapshot de RDS a una instancia temporal (valida backup y migraciones 0159–0162 y las nuevas). Borra la instancia al terminar.
- Alarmas con aviso a tu celular (SNS): 5xx, CPU y `CPUCreditBalance` de la instancia, RDS (`CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`), y la alarma por falta del heartbeat del beat.
- Tipo de instancia real alineado entre `.ebextensions` (`t3.large`) y `.elasticbeanstalk` (`t3.medium`).

### Producto

- Plan asignado a cada cliente y grupo; `LINEA_META_PLAN_DEFAULT=''`.

## 6. ENSAYO INTERNO (5–10 números propios, línea Meta, antes del grupo real)

Marca cada punto; si uno falla, no se lanza.

- Onboarding completo: habeas → cédula → curso. Queda registrado el opt-in con fecha y versión.
- `listo` entrega el módulo completo; un segundo `listo` inmediato no duplica.
- Evaluación A–D: `listo` no avanza, la letra sí. «casi» y «no quiero seguir» no avanzan.
- Video, imagen y audio llegan; un video fallido deja error visible en `/admin/infra/`.
- Número desconocido escribe: respuesta fija, sin IA.
- Doce mensajes en un minuto: se descartan con un solo aviso.
- Campaña a los 5–10 números con `META_CAMPANAS_V2_ENABLED=true` y `campana_preflight` correcto. Lanzarla dos veces → un solo mensaje por persona. Estados delivered/read aparecen en el panel.
- Matar el worker en medio de un lote (`kill -9`): filas `INCIERTO`, cero duplicados.
- Ventana cerrada (espera 24 h sin escribir) + reenganche con `META_REENGANCHE_ENABLED=true`: sale la plantilla.
- Opt-out: escribe «baja» → no recibe más plantillas.
- Token inválido simulado (pon una clave `eki:meta:token_invalido` o un token erróneo en el entorno de prueba): ningún envío sale y aparece la alerta.
- Aula: `aula` por WhatsApp → código (con documento) → entra; 6 intentos erróneos → bloqueo.
- Sentry recibe un error de prueba sin teléfono ni cédula.
- Portal: dos organizaciones de prueba, cada una ve solo lo suyo.

Lanzamiento: enviar la campaña de bienvenida por tandas (por ejemplo 30, esperar 2 horas, revisar fallos y calidad del número, luego el resto). Mantén `campana_reanudar` y `meta_token_reset` a mano. Revisa `/admin/infra/` cada pocas horas el primer día.

## 7. BACKLOG POST-LANZAMIENTO (no bloquea)

- P4-full: interfaz Sender única, reenganche sobre el mismo pipeline, reenganche de inactivos con horario silencioso y tope semanal, variantes A/B, `media_id`, lectura automática de calidad/tier del número.
- P7: resúmenes diarios e índices (cuando haya volumen real); política de retención de logs.
- P8-d: corregir contradicciones de docs y escribir `RUNBOOK.md` (importante para el factor bus).
- P8-f: contrato de dependencias entre apps (import-linter).
- Logs JSON con `trace_id` y métricas a CloudWatch.
- Carga sintética (Graph falso + Locust) si decides escalar el grupo.
- Los 40 fallos viejos de suite-completa (portal/studio): clasificarlos tras el Lote 1.
- Retirar Twilio cuando no queden usos.
