# PLAN P4 → P8 — eki (Meta primero)

Versión: 4 oct 2026. Complementa `docs/PLAN_ESCALABILIDAD_EKI.md`.

**Cómo usarlo con Cursor:** *"Lee @docs/PLAN_P4_A_P8_EKI.md. Ejecuta SOLO el bloque que te indique, siguiendo el protocolo de la sección 0. Un commit por sub-bloque, informe al final de cada bloque, push, sin deploy."* Un bloque por conversación de Cursor.

---

## 0. Reglas y protocolo (valen para todos los bloques)

### 0.1 Reglas permanentes
1. Un cambio por commit. No mezclar movimiento de código con cambio de comportamiento.
2. **No tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`.** Solo se envuelve desde afuera.
3. Todo archivo nuevo queda en git. Cada informe lista `git status` y lo no trackeado. `eb deploy` empaqueta `HEAD`.
4. Migraciones expand/contract. El rollback de EB revierte código, no esquema. Índices en tablas grandes con `AddIndexConcurrently` + `atomic = False`, en migración separada.
5. Sin SQL con f-strings. Tests contra PostgreSQL y Redis reales (CI). Red externa bloqueada (`pytest-socket`); solo `127.0.0.1`.
6. `patch()` apunta al módulo donde el caller busca el nombre, no al reexport de `core/views/__init__.py`.
7. Firma de Meta (HMAC-SHA256 sobre body crudo) y de Twilio se validan **antes** de cualquier lógica. `hmac.compare_digest`.
8. Nada de secretos en git, logs, tests ni informes. Teléfonos y cédulas se enmascaran (`573****0629`) o se hashean con HMAC (`telefono_hash`).
9. **Meta es el canal principal.** Todo diseño de envío, estados, límites y alertas se piensa primero para Meta detrás de la interfaz `Sender`. Twilio es legacy y no se extiende.
10. Umbrales y códigos de Meta (mps, tamaños, tiers, errores, ventana 24 h, precios) viven en settings, con comentario de la fecha en que se verificaron contra la documentación oficial. Si no puedes verificar un dato, **dilo en el informe**; no lo asumas.
11. Todo flag nuevo nace con un default que **no cambia el comportamiento actual**, salvo que el bloque diga lo contrario.
12. Si un test que no estaba en el baseline falla, detente y repórtalo. No cambies el test para que pase.
13. Los tests de carrera/lock/Redis/Postgres no pueden quedar en `skipped` en CI (`pytest -rs` debe mostrar 0 skipped en ellos).
14. Tareas Celery: `countdown` ≤ 540 s (por `visibility_timeout=600`); timeouts HTTP explícitos; `acks_late` solo en tareas idempotentes.

### 0.2 Plantilla de informe (obligatoria al terminar cada bloque)
```
BLOQUE: <id>
Commits: <hash + mensaje>
Archivos tocados: <lista>
Archivos nuevos y estado en git: <lista>
Migraciones: <nombre, expand/contract, reversible sí/no>
Resultado: check / makemigrations --check / tests (passed, skipped, xfailed) / CI run URL
Decisiones que tomaste y por qué: <lista>
Hallazgos fuera de alcance: <lista, sin arreglarlos>
Riesgos: <lista>
[MANUAL] pendientes para el humano: <lista>
```

### 0.3 Estado de partida (no repetir)
Hecho en código, sin desplegar: P0 CI · P1 idempotencia · P2 async + lock por teléfono · P3 roles/colas/Redis/migrate_locked · W/W2 ventana de 24 h por canal · Z/Z2 diseño P4 · Q colas · R audio · H–N ajustes.
**Debe estar terminado antes de P4:** W3, U (errores/token/versión Graph), V (statuses de Meta), X (inspección de `CampanaMeta`), Y (mantenimiento). Los bloques P8-a/b/c, P6 y P5 pueden hacerse antes que P4.

### 0.4 Orden de ejecución y despliegues
| Orden | Bloque | Depende de | Despliegue sugerido |
|---|---|---|---|
| 1 | P8-a, P8-b, P8-c | — | Deploy B |
| 2 | P6 aislamiento entre clientes | — | Deploy B |
| 3 | P5 costo LLM, antiflood, registrados | P2 | Deploy B |
| 4 | P4-lite campañas Meta seguras (incluye P4.0 opt-in) | U, V, X | Deploy C |
| 5 | P8-e observabilidad mínima | — | Deploy C |
| 6 | P4-full (Sender, reenganche unificado, media_id, calidad del número, carga sintética) | P4-lite | Deploy D (post-lanzamiento o en paralelo al ensayo) |
| 7 | P7 resúmenes e índices | datos reales o sintéticos | Deploy D |
| 8 | P8-d docs, P8-f contrato de dependencias | — | cuando haya un rato |

Deploy A (previo): P0–P3 + U–Y, con los tres `*_CELERY_ASYNC=false`, `META_REENGANCHE_ENABLED=false`.
Cada deploy: PR a `main`, CI verde, desplegar desde `main`, checklist de la sección 10.

---

## 1. P8-a — `detect_intent` por palabra completa

**Problema:** `core/intent_detector.py` busca palabras clave como subcadena. «casi» o «perseguir» salen como `continuar_leccion` (`si`, `seguir`). En la línea Meta eso puede avanzar el curso o saltar una evaluación A–D.

**Pasos**
1. Inspecciona cómo se construye `texto_limpio` (minúsculas, sin tildes, puntuación). Repórtalo.
2. Crea helper en el mismo módulo:
   ```python
   import re
   def contiene_palabra(texto: str, palabra: str) -> bool:
       return re.search(rf"(?<!\w){re.escape(palabra)}(?!\w)", texto) is not None
   ```
   Para frases de varias palabras, mismo patrón (los espacios internos se escapan igual).
3. Sustituye cada `palabra in texto` de las listas de intents por `contiene_palabra`. Variantes legítimas (plural, apócope, sinónimos) se listan **explícitamente** en la lista del intent; no se usa coincidencia difusa.
4. Revisa los intents con palabras muy cortas (`si`, `ok`, `ya`, `no`): documenta cuáles son ambiguos y cómo se resuelven (p. ej. exigir que el mensaje sea corto: ≤ 3 palabras).
5. Verifica el flujo Meta: con `esperando_respuesta_evaluacion_paso` activo, `continuar_leccion` NO debe avanzar; debe pedir letra A–D. Si hoy avanza, corrígelo **sin tocar el cuerpo de `_procesar_twilio_webhook_cuerpo`** (en el punto de entrada de Meta o en `response_templates`/`module_steps`, según donde viva) y repórtalo.
6. Quita del baseline xfail el test de `detect_intent` si pasa a pasar.

**Tests**
| Entrada | Esperado |
|---|---|
| `casi` | NO `continuar_leccion` |
| `perseguir` | NO `continuar_leccion` |
| `así` / `asi` | NO `continuar_leccion` |
| `si` / `sí` | `continuar_leccion` |
| `listo` / `LISTO!` / `listo ✅` | `continuar_leccion` |
| `no se si seguir` | documenta el resultado (ambigua); no debe romper |
| Evaluación A–D abierta + `listo` por Meta | pide letra, no avanza |
| Evaluación A–D abierta + `b` | corrige/avanza evaluación |

**Aceptación:** tests verdes; ningún intent usa subcadena. **Commit:** `fix(intent): comparar palabras completas y proteger evaluaciones abiertas`

---

## 2. P8-b — Código de acceso al aula: fuerza bruta

**Contexto:** el estudiante escribe *aula* por WhatsApp, recibe un código de 6 dígitos (~10 min) y lo pega en `/aprende/estudiante/login/`. Si el login identifica al estudiante **solo por el código**, un atacante que prueba códigos al azar acierta el de alguien: con N códigos vivos la probabilidad por intento es N/1.000.000.

**Pasos**
1. **Inspección primero (sin cambios):** ¿la vista busca el estudiante solo por código o pide también documento? ¿Cómo se genera (`random` vs `secrets`)? ¿Es de un solo uso? ¿Cómo se compara? Repórtalo.
2. Generación con `secrets.randbelow(10**6)` rellenado a 6 dígitos (si hoy usa `random`, cámbialo). Comparación con `hmac.compare_digest`. Código de un solo uso: se invalida al canjearlo.
3. Módulo `core/rate_limit.py` con helper Redis genérico:
   ```python
   def hit(clave: str, limite: int, ventana_seg: int) -> tuple[bool, int]:
       """INCR con TTL en la primera vez. Devuelve (permitido, intentos)."""
   ```
4. Límites (settings, defaults entre paréntesis):
   - Por **IP** (`AULA_LOGIN_MAX_POR_IP`=10 / 600 s). Detrás de Cloudflare, usa `CF-Connecting-IP` solo si `EKI_BEHIND_CLOUDFLARE`; si no, `REMOTE_ADDR`. No confíes en `X-Forwarded-For` arbitrario.
   - Por **estudiante** si el login pide documento (`AULA_LOGIN_MAX_POR_ESTUDIANTE`=5 / 600 s).
   - **Global** (`AULA_LOGIN_MAX_GLOBAL`=200 / 600 s): al superarlo, loguea `aula_login_ataque_probable` y activa modo estricto (límite por IP baja a 3) durante 15 min.
   - Tras agotar intentos de un estudiante, **se invalida el código vigente** (debe volver a escribir *aula*).
5. Mensaje de error genérico e idéntico para: código inexistente, vencido, ya usado o bloqueado. No reveles cuál.
6. **Recomendación de diseño (si el login es solo por código):** añadir el documento como segundo factor, o ampliar el código a 8 caracteres alfanuméricos sin ambiguos. Impleméntalo detrás de `AULA_LOGIN_REQUIERE_DOCUMENTO` (default False) y reporta el costo de UX.
7. Registro: `logger.warning('aula_login_fallido ip_hash=… est_hash=…')`, nunca el código ni el teléfono completos.

**Tests:** 5 fallos de un estudiante bloquean y queman el código; 11 intentos desde una IP bloquean; éxito resetea el contador del estudiante (no el de la IP); código de un solo uso; mensajes idénticos; modo estricto global; Redis caído → falla cerrado (rechaza) y loguea (decisión documentada).
**Aceptación:** no es posible probar más de ~10 códigos por IP cada 10 min. **Commit:** `fix(aula): límite de intentos y código de un solo uso`

---

## 3. P8-c — Settings de producción que fallan cerrado

**Pasos**
1. `settings_production.py`: si `EKI_ALLOWED_HOSTS` no está definido o vacío → `ImproperlyConfigured` (hoy cae a `['*']`). Igual para `CSRF_TRUSTED_ORIGINS`.
2. `INTEGRACION_API_REQUIRE_KEY` default `True`. Con `True` y key vacía, la API LXP rechaza todo (no abre la puerta).
3. `SECRET_KEY` sin fallback en producción: si falta o es el valor de desarrollo → `ImproperlyConfigured`. `DEBUG=False` forzado.
4. Corre `python manage.py check --deploy` con settings de producción simulados y reporta cada advertencia; arregla las triviales (cookies seguras, HSTS tras Cloudflare, `SECURE_PROXY_SSL_HEADER`) y lista el resto sin tocar.
5. Tests: importar `settings_production` con env incompleto lanza la excepción esperada; con env completo, no.
6. **Commit aparte, NO mergear hasta el [MANUAL]:** `WHATSAPP_REQUIRE_SIGNATURE` con default `True` en producción.

**[MANUAL] antes del deploy de este bloque (sin imprimir valores):**
- `eb printenv` y confirmar que existen `EKI_ALLOWED_HOSTS` (con admin, app, aprende, studio y host interno), `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY`, `INTEGRACION_API_REQUIRE_KEY`, `WHATSAPP_APP_SECRET` (no vacío; comparar los últimos 4 caracteres con Meta → App Dashboard → Settings → Basic) y que `TWILIO_VALIDATE_SIGNATURE` no sea `false`.
- Si falta algo, el web no arranca: por eso se verifica **antes**. Rollback = versión anterior.
**Commit:** `fix(settings): producción falla cerrado si faltan hosts, SECRET_KEY o clave de API`

---

## 4. P6 — Aislamiento entre clientes (multi-tenant)

**Riesgo:** una vista del portal sin filtro de `cliente` entrega datos de otra organización. Es el fallo más caro para un B2B.

### 4.1 Test sistemático (`portal/tests_tenant_isolation.py`)
1. **Fixture** con dos clientes A y B. En B, cada campo de texto de cada objeto lleva un marcador único (`ZZB-NOMBRE-001`, cédula `9990000001`, teléfono `573990000001`, nombre de curso `ZZB-CURSO`, etc.): estudiantes, cursos, módulos, campañas, certificados, fichas GEI, sesiones Nat, tareas, entregas, conversaciones, PQRS, grupos, eventos de retención.
2. Usuarios del portal en A con **cada rol** (`admin`, `profesor`, `viewer`) y sesión autenticada.
3. **Enumeración automática de rutas:** recorre `portal/urls.py` con `get_resolver`. Para cada ruta con parámetros, un diccionario `PARAMS_B = {"curso_id": b_curso.pk, "estudiante_id": ..., ...}`. Si aparece un parámetro **sin entrada** en el diccionario, el test **falla** con el nombre del parámetro (obliga a mantenerlo al día).
4. Para cada ruta: GET y POST (CSRF desactivado en test). Aserción: estado 403/404, o respuesta (HTML, JSON, bytes de xlsx abiertos con `openpyxl`, CSV) **sin ningún marcador `ZZB-`**.
5. **Rutas sin parámetros** (listados, dashboards, exports): el usuario de A no debe ver marcadores de B.
6. **Agente de retención** (`POST /portal/retencion/agente/`): mockea el LLM y captura el prompt: no puede contener marcadores de B.
7. **Aula:** profesor de A no accede a cursos/entregas/módulos de B; un estudiante autenticado no accede a `modulo/<id>`, `tarea/<id>` ni `entrega` de otro estudiante o de un módulo no liberado (IDOR).
8. **API LXP** (`core/api.py`): sin credenciales y con credenciales de A, no devuelve datos de B.
9. **Verificación pública de certificados:** documento enmascarado; no expone teléfono ni otros datos.
10. Informe: tabla `ruta | método | rol | resultado`. Si hay fallos, **no los arregles en este commit**: lista y detente.

### 4.2 Corrección (commit aparte, solo si hay fallos)
- `core/tenancy.py`:
  ```python
  class TenantQuerySet(models.QuerySet):
      def de_cliente(self, cliente): return self.filter(cliente=cliente)
  def get_for_portal(modelo, request, **filtros):
      """get_object_or_404 que SIEMPRE filtra por request.portal_usuario.cliente."""
  ```
- Reemplaza en cada vista los `Model.objects.get(pk=…)` / `get_object_or_404` por el helper.
- **Guardia estática** (test informativo): escanea `portal/*.py` y avisa de `get_object_or_404(` / `.objects.get(` que no pasen por el helper.
- El staff de eki con `is_staff` queda exento solo en `/admin/`, nunca en el portal.

**Aceptación:** el test recorre el 100 % de las rutas y no filtra marcadores. **Commits:** `test(portal): aislamiento multi-tenant sobre todas las rutas` y, si hace falta, `fix(portal): filtro de cliente obligatorio en vistas`.

---

## 5. P5 — Costo de IA, antiflood y solo registrados

### 5.1 Ledger de uso (`UsoLLM`)
- Modelo: `cliente` (nullable), `telefono_hash`, `agente`, `modelo`, `tokens_in`, `tokens_out`, `tokens_razonamiento` (null), `costo_usd_est` (Decimal 10,6), `estimado` (bool), `creado`. Índice `(cliente, creado)`. Migración expand.
- Se registra en `core/openai_compat.py` tras cada llamada exitosa. Tokens desde `response.usage`; si no vienen, estima `len(texto)/4` y marca `estimado=True`. Verifica si los tokens de razonamiento de gpt-5 están incluidos en el conteo de salida facturado.
- Precios en settings `LLM_PRECIOS_USD_POR_MTOK = {modelo: (entrada, salida)}`. Referencia (guía §26.5): mini 0,25/2; gpt-5 1,25/10; **verifica todos, incluido gpt-5-nano, en la página oficial de precios y fecha el comentario**.

### 5.2 Presupuesto diario y modo económico
- Contador Redis `eki:llm:gasto:{AAAAMMDD}` (día en `America/Bogota`), `INCRBYFLOAT`, TTL 48 h. También por organización: `eki:llm:gasto:{cliente_id}:{día}`.
- Settings: `LLM_PRESUPUESTO_DIARIO_USD`, `LLM_PRESUPUESTO_DIARIO_ORG_USD`, `LLM_UMBRAL_ECONOMICO`=0,7, `LLM_UMBRAL_ALERTA`=0,8.
- Comportamiento:
  - ≥ 70 %: **modo económico**: Nat técnico baja de `gpt-5` a `gpt-5-mini`.
  - ≥ 80 %: `logger.warning('llm_presupuesto_80')` + alerta en `/admin/infra/`.
  - ≥ 100 %: los agentes (Nat, Lina, Profe IA, Ventas) responden con la respuesta degradada fija **del mismo tema** (reutiliza el fallback existente de `sandbox_agentes`/`openai_compat`), `logger.error('llm_presupuesto_agotado')`.
  - **Nunca** bloquea *listo*, avance de curso, certificados ni PQRS por reglas (el PQRS sigue con su fallback de reglas).
- Redis caído → **falla abierto** para el curso y **degrada** el LLM (decisión documentada); loguea.

### 5.3 Antiflood
- Clave `eki:flood:{telefono_hash}:{minuto}`, `INCR`, TTL 70 s. `LINEA_MAX_MSG_MIN` default 12.
- Se aplica en las tareas del webhook **después** del reclamo de P1 (los duplicados no cuentan) y **antes** del procesamiento pesado. No cuenta `statuses`.
- Al superar: descarta con log (`flood_descartado`), y envía **un solo** aviso por ventana (`SET NX` con TTL 60 s): «Estás escribiendo muy rápido; espera un momento…».
- Tope de números nuevos por día (`LINEA_MAX_NUEVOS_DIA`, default 300): evita que un barrido de números cree miles de `Estudiante` basura.

### 5.4 Solo registrados (`LINEA_META_SOLO_REGISTRADOS`, default True)
1. **Inspección primero:** ¿qué hace hoy el webhook con un número desconocido? ¿Crea un `Estudiante`? ¿Con qué estado? Repórtalo.
2. Definición de **registrado** (propuesta; confirma con la inspección): `Estudiante` con `cliente` asignado, o en un `GrupoEstudiantes`, o con `ProgresoEstudiante`, o en un estado de onboarding legítimo (habeas → cédula) iniciado por una campaña.
3. Para **no registrado**: no se aplica `LINEA_META_PLAN_DEFAULT`, **no se llama al LLM**, no se inscribe a cursos. Responde un texto fijo («Esta línea es para estudiantes de programas eki…») una vez por 24 h por número.
4. No debe bloquear el onboarding real (habeas → cédula) de quien viene de una campaña. Test explícito.
5. Comando `plan_linea_auditar`: lista clientes y grupos **sin** plan y cuántos estudiantes afectaría retirar el default. Cuando todos tengan plan, `LINEA_META_PLAN_DEFAULT=''` en EB.

### 5.5 Admin y alertas
- `UsoLLM` solo lectura en admin (filtros por cliente, agente, modelo, día) y widget en Inicio: gasto hoy, mes, por organización y por agente, **costo por estudiante activo**.
- Timeout de 30 s en cada cliente LLM (ya hecho para OpenAI; verifica Gemini). Fallback a Gemini detrás de `LLM_FALLBACK_GEMINI` (default False).

### 5.6 Tests
Ledger guarda costo correcto por modelo · 70 % cambia a mini · 100 % degrada y *listo* sigue funcionando · contador por día (cambio de día en Bogotá) · antiflood: 13.º mensaje se descarta con un solo aviso · duplicado de P1 no cuenta · desconocido no llama al LLM (mock verifica 0 llamadas) · onboarding de campaña no se bloquea · Redis caído.
**Aceptación:** con presupuesto 0 el curso sigue avanzando y ningún agente llama al proveedor. **Commit(s):** `feat(llm): ledger`, `feat(llm): presupuesto y modo económico`, `feat(webhook): antiflood`, `feat(linea): solo registrados y auditoría de planes`.
**Rollback:** `LLM_PRESUPUESTO_DIARIO_USD` muy alto; `LINEA_META_SOLO_REGISTRADOS=false`; `LINEA_MAX_MSG_MIN` alto.

---

## 6. P4-lite — Campañas por Meta seguras (mínimo antes del lanzamiento)

### 6.A AJUSTE TRAS EL INFORME X (4 oct 2026) — MANDA SOBRE 6.1 A 6.10 SI HAY CONFLICTO

**Base real:** `CampanaMeta` + `EnvioCampanaMeta` + `ejecutar_campana_meta` / `encolar_campana_meta` (`core/meta_waba.py`). El pipeline `Campana` + `EnvioLog` (Twilio) queda **legacy y no se toca**. Donde 6.1–6.10 digan `EnvioLog` léase `EnvioCampanaMeta`; donde digan `Campana` léase `CampanaMeta`. **No** se crea `Campana.proveedor` ni se migra `linea_origen`.

**Defectos confirmados en X que P4-lite debe corregir**
1. Sin claim previo al POST: un timeout deja el envío sin estado y el siguiente pase (solo salta `ENVIADO`) puede **duplicarlo**.
2. Un `130429` (o 4, 80008, 613) corta el lote y deja la campaña a medias sin reanudación ordenada.
3. `time.sleep(0.35)` dentro de la tarea: sustituir por token bucket global + hueco por destinatario con `retry` de Celery.
4. Sin tope compartido con el reenganche ni con el tope de contactos nuevos en 24 h.
5. Un `190` a mitad de lote no se frena: la bandera de token se consulta **por envío**, no solo al empezar.
6. `CampanaMeta` no tiene fecha programada: añadir `fecha_programada` (expand) y una tarea de beat `enviar_campanas_meta_programadas` (cada 5 min, cola `masivo`) que reutilice `encolar_campana_meta`. `EKI_CAMPANA_META_ENABLED` se mantiene como interruptor global.

**Seguimiento de entrega de campañas (hueco nuevo)**
- En Cloud API, un 200 significa «aceptado por Meta», **no** entregado. Errores como `131026` o `131049` llegan **después** como `status: failed` en el webhook.
- `meta_estados` (V) actualiza `WhatsappLog` por `mensaje_id`, pero los envíos de campaña **no crean `WhatsappLog`**: sus `delivered/read/failed` hoy se pierden (id desconocido → debug).
- Cambios (expand) en `EnvioCampanaMeta`: `wamid` (indexado; verifica si ya existe con otro nombre), `estado_entrega` (sent|delivered|read|failed), `error_codigo`, `entregado_en`, `leido_en`, `claim_token`, `claimed_at`, `intentos`, `omitido_motivo`. Estados: `PENDIENTE`, `ENVIANDO`, `ENVIADO`, `ERROR`, `ERROR_REINTENTABLE`, `INCIERTO`, `OMITIDO` (`FALLIDO` histórico se sigue leyendo).
- `core/meta_estados.py` además actualiza `EnvioCampanaMeta` por `wamid`, con estados monótonos. Si el status trae `biz_opaque_callback_data="envio:{id}"` y el envío está `INCIERTO` (no tiene wamid), lo reconcilia: `ENVIADO` + `wamid`.
- **Pausa automática por fallos:** cuenta tanto respuestas síncronas con error como statuses `failed` posteriores. Se evalúa al llegar a 100 envíos aceptados y se **re-evalúa mientras lleguen statuses** (hasta 30 min después del último envío). Si `fallos/n > 0,15` → `pausada=True`; los `PENDIENTE` no salen.
- Constraint: `UniqueConstraint(campana, estudiante)` en `EnvioCampanaMeta`, **solo tras** `auditar_envios_duplicados` ejecutado y limpio (pega la salida y detente).
- Panel de campaña: conteos por estado de envío y por `estado_entrega`, tasa entregado/leído, errores por código, `INCIERTO` sin confirmar, y botones Pausar / Reanudar / Reenviar reintentables (nunca `INCIERTO`).

**Tests adicionales:** statuses de una campaña actualizan `EnvioCampanaMeta` (no `WhatsappLog`); `failed` posterior al 200 cuenta para la pausa; `INCIERTO` se reconcilia por `biz_opaque_callback_data`; re-ejecutar `ejecutar_campana_meta` tras un timeout no duplica; un `130429` reintenta con backoff sin abandonar el resto del lote; un `190` a mitad de lote detiene los envíos siguientes.

**Objetivo:** que una campaña (a) no duplique mensajes, (b) no reenvíe nada dudoso, (c) no se pase de velocidad, (d) se frene sola si algo va mal, (e) respete opt-in, ventana y token. Una campaña mal hecha baja la calidad del número y afecta todo el producto.

> Parte de lo que reporte **X** sobre `CampanaMeta`/`ejecutar_campana_meta`. Reutiliza lo que sirva; no lo reescribas. Si X dice que no sirve, construye el pipeline de abajo y explícalo.

### 6.0 P4.0 — Consentimiento (opt-in/opt-out)
Meta exige consentimiento para mensajes iniciados por la empresa, y Colombia (Ley 1581) exige constancia del tratamiento. *(No es asesoría legal: valídalo con tu abogado.)*
1. Inspecciona dónde se acepta el habeas data en la línea Meta (`webhook_meta`/sandbox) y qué guarda hoy (fecha, versión del texto).
2. Migración expand en `Estudiante`: `wa_optin_fecha`, `wa_optin_version` (CharField), `wa_optin_origen` (habeas|formulario|importación), `wa_optout_fecha` (null).
3. El texto de habeas debe mencionar de forma explícita las notificaciones por WhatsApp (recordatorios del curso). Versiona el texto (`HABEAS_TEXTO_VERSION`). Registra al aceptar.
4. Opt-out: palabras `baja`, `stop`, `no mas mensajes`, `cancelar notificaciones` (palabra completa) → se marca `wa_optout_fecha`, confirmación única, y **ninguna** plantilla ni reenganche sale a ese número. Los mensajes de sesión (respuestas a quien escribe) no se afectan.
5. Backfill: estudiantes existentes con habeas aceptado → `wa_optin_origen='habeas'`, fecha de aceptación si existe; si el texto antiguo no cubría WhatsApp, déjalos en `NULL` y la campaña los omite (lista exportable para pedir consentimiento).
**Tests:** sin opt-in no hay plantilla; opt-out inmediato respetado; backfill no inventa fechas.

### 6.1 Modelo (expand)
`EnvioLog` (verifica los campos reales primero):
- `proveedor` (`meta`|`twilio`; histórico = `twilio`), `provider_id` (wamid/SID, indexado), `error_codigo`, `intentos` (int), `claim_token` (UUID, null), `claimed_at` (null), `omitido_motivo` (null).
- `estado` admite: `PENDIENTE`, `ENVIANDO`, `ENVIADO`, `ERROR`, `ERROR_REINTENTABLE`, `INCIERTO`, `OMITIDO`. `FALLIDO` histórico se sigue leyendo.
- Antes de cualquier restricción: comando `auditar_envios_duplicados` (pares `(campana, estudiante)` con más de un `EnvioLog`) → ejecútalo, **pega la salida y detente**.
- Con la auditoría limpia: `UniqueConstraint(fields=['campana','estudiante'], condition=Q(proveedor='meta'), name='uniq_envio_meta_por_destinatario')` (parcial: no afecta el historial de Twilio). La tabla es pequeña: `AddConstraint` normal.
`Campana`: `proveedor` (default `meta` para nuevas), `linea_origen` obligatoria solo al crear; campos de control `pausada` (bool), `pausa_motivo`.

### 6.2 Máquina de estados
```
PENDIENTE → ENVIANDO → ENVIADO          (Graph devolvió messages[0].id)
                     → ERROR            (código no reintentable)
                     → ERROR_REINTENTABLE → (backoff) → PENDIENTE (máx. N intentos)
                     → INCIERTO         (timeout / conexión cortada / 5xx sin cuerpo)
PENDIENTE → OMITIDO (token inválido | ventana cerrada sin plantilla | opt-out | sin opt-in | tier agotado)
```
**Regla de oro:** `INCIERTO` jamás se reenvía solo. El mensaje pudo salir.

### 6.3 Claim atómico
```python
n = (EnvioLog.objects
     .filter(pk=envio_id, estado__in=['PENDIENTE'])
     .update(estado='ENVIANDO', claim_token=token, claimed_at=timezone.now(),
             intentos=F('intentos') + 1))
if n != 1:
    return  # otro worker lo tiene o ya se procesó
```
Después del envío, la actualización de estado lleva `filter(pk=…, claim_token=token)` para no pisar a otro actor.

### 6.4 Tareas
- **Padre** `ejecutar_campana_meta_padre(campana_id)` (cola `masivo`, **no** `acks_late` hasta que el claim exista; después sí):
  1. Lock Redis `eki:campana:{id}:padre` (evita dos padres).
  2. Pre-chequeos (6.7). Si fallan → `OMITIDO` masivo con motivo y fin.
  3. Calcula destinatarios, `bulk_create(EnvioLog PENDIENTE, ignore_conflicts=True)` (la restricción única hace idempotente la re-ejecución).
  4. Encola lotes de 50: `enviar_lote_meta.delay(campana_id, [ids])`.
  5. Marca la campaña como lanzada **después** de encolar.
- **Hija** `enviar_lote_meta(campana_id, envio_ids)` (cola `masivo`): por cada envío: ¿token inválido (`eki:meta:token_invalido`)? ¿campaña pausada? ¿opt-in/opt-out? ¿ventana? → token bucket → hueco por destinatario → claim → enviar → actualizar.
- **Ventana:** abierta (último entrante por Meta ≤ 23 h) → texto libre; cerrada → **plantilla** (`campana.plantilla_meta`, nombre + idioma + variables); sin plantilla aprobada → `OMITIDO('ventana_cerrada')`.

### 6.5 Velocidad: token bucket global en Redis (Lua)
Celery `rate_limit` es por worker, no por clúster; hace falta un límite global.
```lua
-- KEYS[1]=bucket  ARGV: rate(tokens/s), capacity, now_ms, pedir
local d = redis.call('HMGET', KEYS[1], 't', 'ms')
local t = tonumber(d[1]) or tonumber(ARGV[2]); local ms = tonumber(d[2]) or tonumber(ARGV[3])
t = math.min(tonumber(ARGV[2]), t + (tonumber(ARGV[3]) - ms) / 1000 * tonumber(ARGV[1]))
local ok = 0; local espera = 0
if t >= tonumber(ARGV[4]) then t = t - tonumber(ARGV[4]); ok = 1
else espera = (tonumber(ARGV[4]) - t) / tonumber(ARGV[1]) end
redis.call('HSET', KEYS[1], 't', t, 'ms', ARGV[3]); redis.call('EXPIRE', KEYS[1], 60)
return {ok, tostring(espera)}
```
- Settings: `WA_META_MPS` (default 20; **el tope real depende del número, verifícalo**), `WA_META_BURST` (default 20), `WA_TWILIO_MPS` (3).
- Sin tokens → `self.retry(countdown=min(ceil(espera)+jitter(0..2), 30))` (sin gastar `max_retries` de errores).
- **Hueco por destinatario:** `SET eki:wa:gap:{hash} NX PX WA_DESTINO_GAP_SEG*1000` (default 6 s; **verifica el límite por par de usuarios**). Si existe, ese envío se difiere.
- **Tope de contactos nuevos en 24 h:** `ZSET eki:wa:contactos24h` con hash de teléfono y timestamp (`ZREMRANGEBYSCORE` > 24 h, `ZCARD`). Límite en `META_LIMITE_CONTACTOS_24H` (**manual** hasta que se lea el tier por API; hoy ~1000 según tu cuenta). Al 90 %, difiere el resto al día siguiente y alerta.

### 6.6 Mapeo de errores de Meta (settings, con fecha de verificación)
| Código | Acción |
|---|---|
| `130429`, `131056` | `ERROR_REINTENTABLE`, backoff exponencial con jitter, máx. 5 |
| `131047` | ventana cerrada → plantilla si existe; si no, `OMITIDO` |
| `131026`, `131048`, `131049` | `ERROR` (no reintentar), cuenta para pausa |
| `131052`, `131053` | media: `ERROR` + marca de media fallida |
| `190` | token inválido: activa `eki:meta:token_invalido`, `OMITIDO` el resto, **pausa la campaña** |
| timeout / conexión cortada / 5xx sin cuerpo | `INCIERTO` |

### 6.7 Pre-chequeos y pausa automática
- **Pre-flight** (`campana_preflight <id>`, también automático): token válido (llamada ligera a Graph), plantilla en estado aprobado (`sincronizar_plantillas_meta`), número de destinatarios con opt-in vs sin opt-in, margen frente a `META_LIMITE_CONTACTOS_24H`, duración estimada = destinatarios / `WA_META_MPS`. Salida legible; en el admin, pantalla de confirmación previa al lanzamiento.
- **Pausa por tasa de fallo:** contadores Redis `eki:campana:{id}:n` y `:fallos`. Al llegar a 100 envíos resueltos, si `fallos/n > CAMPANA_PAUSA_TASA_FALLO` (0,15) → `campana.pausada=True`, log `campana_pausada_por_fallos` y alerta en `/admin/infra/` y en Inicio. Los `PENDIENTE` quedan como están. Códigos que cuentan: `CAMPANA_CODIGOS_CUENTAN_FALLO` (configurable). Comando `campana_reanudar <id>`.
- **Recuperación de `ENVIANDO` viejos:** tarea cada 5 min en `masivo`: `ENVIANDO` con `claimed_at` > 10 min → `INCIERTO` (el worker murió a mitad).
- **Reconciliación de `INCIERTO`:** el envío incluye `biz_opaque_callback_data="envio:{id}"` (**verifica nombre del campo y límite de longitud**). Cuando llega el status de V con ese dato → `ENVIADO` + `provider_id`. Los `INCIERTO` sin confirmar tras 24 h se muestran como «sin confirmar»; reenviarlos es una acción manual con confirmación, nunca automática.

### 6.8 Admin
Pantalla de campaña Meta: conteos por estado y por código de error, tasas entregado/leído (de V), botones **Pausar / Reanudar / Reenviar errores reintentables** (nunca `INCIERTO`), exportación de lista de omitidos con motivo. Selector de proveedor con default Meta.

### 6.9 Servidor de Graph falso (para tests y carga)
`core/tests_support/graph_fake.py`: servidor HTTP local configurable (éxito con wamid falso; secuencia de `131056`; `131047`; `190`; timeout). Setting `WHATSAPP_GRAPH_BASE_URL` (default `https://graph.facebook.com`) para apuntar al falso. `pytest-socket` ya permite `127.0.0.1`.

### 6.10 Tests
1. Re-ejecutar el padre dos veces: 1 `EnvioLog` y 1 envío por destinatario.
2. Dos hilos reclaman el mismo envío: solo uno envía.
3. Timeout → `INCIERTO`; no se reenvía nunca solo; el status de V lo convierte en `ENVIADO`.
4. `ENVIANDO` > 10 min → `INCIERTO`.
5. Bucket global: dos workers simulados no superan `WA_META_MPS` (medición con reloj controlado).
6. Hueco por destinatario: dos mensajes al mismo número se separan.
7. Pausa a los 100 con > 15 % de fallos; reanudar funciona.
8. Token inválido detiene el lote y la campaña; ninguna llamada posterior a Graph.
9. Ventana abierta → texto; cerrada → plantilla; sin plantilla → `OMITIDO`.
10. Sin opt-in / con opt-out → `OMITIDO`.
11. Tope de 24 h al 90 %: difiere.
12. `130429` reintenta con backoff y no cuenta como fallo definitivo.
13. Unicidad parcial: duplicado de `(campana, estudiante)` meta falla; histórico Twilio no.
14. Pre-flight informa correctamente.

**Aceptación (humana, en tu línea con 5–10 números internos):** una campaña lanzada dos veces envía una sola vez a cada uno; matar el worker en medio de un lote deja filas `INCIERTO` y cero duplicados; una plantilla inexistente pausa la campaña.
**Flag:** `META_CAMPANAS_V2_ENABLED` (default False; con False sigue el camino actual).
**Rollback:** flag en `false`; la restricción parcial puede quedarse.
**Commits:** `feat(consent): opt-in y opt-out`, `feat(campanas): modelo y estados de envío Meta`, `feat(campanas): claim atómico y lotes`, `feat(campanas): token bucket y tope 24 h`, `feat(campanas): pausa, preflight y recuperación`, `feat(admin): panel de campaña Meta`, `test(graph): servidor falso`.

---

## 7. P8-e — Observabilidad mínima

1. **Sentry** (DSN por variable de entorno; sin DSN no hace nada). `send_default_pii=False` y `before_send` que elimina teléfonos, cédulas, cuerpos de mensaje y cabeceras de autorización. Etiquetas: `canal`, `tarea`, `cliente_id`. Integración Django + Celery.
2. **Logs estructurados** (JSON) con `trace_id` (reutiliza el de `EventoIA` si existe), `canal`, `external_id`, `telefono_hash`. Un solo formato para webhook, tareas y envíos.
3. **Health profundo:** `/health/deep/` (solo staff o token de infra): DB (`SELECT 1`), Redis (`PING`), profundidad de colas `conversacion`/`masivo`/`celery`/`media_encode`, antigüedad del mensaje más viejo, bandera de token de Meta, último estado del beat (heartbeat Redis escrito por una tarea cada minuto).
4. **Métricas a CloudWatch** (por `put_metric_data` desde una tarea cada minuto en `masivo`, o logs con filtros de métrica): `cola_conversacion`, `cola_masivo`, `webhook_fallido_24h`, `fallos_meta_24h` por código, `llm_gasto_hoy`, `campana_pausada`.
5. **[MANUAL] Alarmas en AWS:** ELB/EB 5xx; EC2 `CPUUtilization` y **`CPUCreditBalance`** (t3); memoria (agente de CloudWatch); RDS `CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`, `FreeableMemory`; las métricas de arriba; **un SNS a tu correo y a tu celular**.
6. Heartbeat del beat: si no hay latido en 3 min → alerta (detecta el beat caído, que si no pasa desapercibido).
**Aceptación:** al apagar Redis en el clon, aparece alerta; un error con teléfono en el mensaje llega a Sentry sin el teléfono.
**Commits:** `feat(obs): sentry sin PII`, `feat(obs): logs JSON y trace_id`, `feat(obs): health profundo y métricas`.

---

## 8. P4-full — Después del lanzamiento (o en paralelo al ensayo)

1. **Interfaz `Sender`** (`MetaSender` real, `TwilioSender` legacy sin extender). `ResultadoEnvio(estado, provider_id, codigo_error, reintentable)`. El proveedor se decide por `Campana.proveedor`/`Linea`, no por `if` repartidos.
2. **Reenganche de las 08:00 sobre el mismo pipeline** (padre/hijas/claim/bucket) en vez de su bucle propio. Mismo mapeo de errores, mismo opt-in, misma ventana. `META_REENGANCHE_ENABLED` sigue siendo el interruptor.
3. **Reenganche de inactivos** (hoy fuera del beat): `REENGANCHE_INACTIVOS_ENABLED` (False), `DIAS_INACTIVIDAD_REENGANCHE`, cooldown por estudiante, **tope de mensajes proactivos por estudiante por semana** (`WA_PROACTIVO_MAX_SEMANA`, default 3), **horario silencioso** (no enviar entre 20:00 y 07:00 America/Bogotá; `WA_HORARIO_SILENCIO`).
4. **Variantes A/B** de plantilla de reenganche (dos plantillas, asignación estable por hash del estudiante) y métrica de recuperación a 7 días por variante.
5. **Media por `media_id`:** modelo `MediaWA(url_origen, sha256, media_id, subido_en)`. Subir a `/{phone-id}/media` una vez, reutilizar el id, renovar antes de su caducidad (**verifica vigencia vigente**). Los envíos prefieren `media_id`; fallback al enlace. Reduce la dependencia de S3 público (paso previo a cerrar el bucket con URLs firmadas).
6. **Calidad y nivel del número:** tarea cada hora que lee calidad/tier por Graph (**verifica campos y permisos**; requiere `WHATSAPP_BUSINESS_ACCOUNT_ID`), guarda `NumeroWAEstado(calidad, tier, leido_en)`, alerta al pasar a amarillo y **pausa campañas** en rojo. Reemplaza el valor manual `META_LIMITE_CONTACTOS_24H`.
7. **Versión de Graph:** una vez decidida con tu informe de U, prueba en el teléfono interno y fíjala; recordatorio de calendario semestral.
8. **Carga sintética (ensayo del pico de las 08:00)**
   - Comando `crear_org_prueba_carga --estudiantes 200 --prefijo 57399` (teléfonos ficticios en un rango reservado). El `Sender` **rechaza** estos números fuera de un entorno de carga (`EKI_ENTORNO_CARGA=1`).
   - Entorno aparte (restore de snapshot de RDS + credenciales falsas + `WHATSAPP_GRAPH_BASE_URL` apuntando al falso). **No `eb clone` directo:** heredaría la base y las llaves reales.
   - Locust con payloads de Meta firmados: 150 usuarios simultáneos escribiendo *listo*, y disparo simulado de 500 reenganches.
   - Objetivos: p95 de respuesta del webhook < 500 ms; cola `conversacion` sin superar 200 mensajes más de 2 min; 500 envíos completados en ≈ 500/`WA_META_MPS` s; 0 duplicados; 0 `WebhookFallido` inesperados.
9. **Retiro gradual de Twilio:** inventario de qué sigue usándolo (demo, HSM históricos) y fecha objetivo para apagarlo.

---

## 9. P7 — Resúmenes diarios e índices

**Cuándo:** cuando haya datos reales o sintéticos de volumen. Hoy no hay estudiantes activos: sin volumen, el planificador de Postgres elegirá escaneos secuenciales y no podrás medir nada.

1. **Datos de volumen para medir:** comando `generar_datos_volumen --logs 1000000 --eventos 500000` (solo en base de prueba). Toma `EXPLAIN (ANALYZE, BUFFERS)` de las consultas de los paneles **antes** y **después**.
2. **Modelo `ResumenDiarioCurso`:** `fecha`, `cliente`, `curso`, `inscritos`, `onboarding`, `empezaron`, `activos_7d`, `activos_30d`, `listos_dia`, `mensajes_entrantes`, `mensajes_salientes`, `completados_por_modulo` (JSON), `certificados`, `fallos_wa_por_codigo` (JSON, de V), `media_fallida`, `llm_costo_usd` (de P5). `UniqueConstraint(fecha, cliente, curso)`.
   Definiciones idénticas a la guía §11.9 (Inscrito, Activo N días, Listo = INCOMING normalizado `listo`/`continuar`, etc.). **No** inventes deltas sin base.
3. **Tarea** a las 03:00 `America/Bogota`, cola `masivo`, un subtarea por cliente, `update_or_create`, idempotente. Comando `backfill_resumen_diario --dias 90 [--cliente ID]`. Comando `verificar_resumen --cliente ID --fecha` que compara resumen vs cálculo en vivo (para días cerrados la diferencia debe ser 0).
4. **Lectura:** `portal/retencion_service.py`, `portal/centro_exito.py` (KPIs, embudo, curva, cohortes) y `core/views/admin_panel.py` (Inicio, Analítica) leen del resumen. El **score de riesgo por estudiante** sigue en vivo, solo para la lista de riesgo alto paginada, con caché de 5 min en Redis (`cache.get_or_set`). Si falta un día en el resumen: calcula en vivo para ese cliente con límite de tiempo y encola el backfill.
5. **Índices** (migración separada, `AddIndexConcurrently`, `atomic = False`; verifica los nombres reales de campos): `WhatsappLog(estudiante, agente_usado, fecha)`, `WhatsappLog(canal, tipo, fecha)`, `WhatsappLog(mensaje_id)` (si V no lo creó), `EstudianteEventoAprendizaje(estudiante, tipo, creado)`, `EnvioLog(campana, estado)`, `UsoLLM(cliente, creado)`. Confirma con `EXPLAIN` que se usan; si no, no los dejes.
6. **Retención de datos (minimización, Ley 1581):** `LOG_RETENCION_DIAS` (propuesta: 180) para el **texto** de `WhatsappLog` (se anula el cuerpo, se conservan metadatos). Memoria de conversación de agentes solo necesita las últimas semanas. Documenta la política y valídala con tu abogado.
7. **Nuevos paneles baratos** gracias al resumen: costo de IA por cliente y por estudiante activo; tasa de entrega/lectura por campaña; tendencia de fallos de Meta por código.
**Tests:** idempotencia (correr dos veces no duplica), backfill, equivalencia resumen vs vivo, fallback cuando falta un día, caché.
**Aceptación:** los paneles no dependen del tamaño de las tablas crudas (tiempo de respuesta estable con 1 M de logs).
**Commits:** `feat(analitica): resumen diario`, `perf(analitica): índices`, `feat(retencion-datos): política de retención de logs`.

---

## 10. P8-d y P8-f — Docs y contrato de dependencias

### P8-d (solo texto, un commit por documento)
- Guía §10.3, §15.4, §15.5, §22 (glosario) y §16.1: quitar o corregir las menciones al reenganche de inactivos a las 09:00 hasta que `REENGANCHE_INACTIVOS_ENABLED` exista y se active; eliminar variables `REENGANCHE_INACTIVOS_*` que no se usen.
- Guía §9.2 alineada con la auditoría §7 y con el diseño final del login del aula (P8-b).
- Auditoría §7: quitar `catalogo_service` tipo Platzi de `aprende`; §13: añadir `studio` a dominios de producción.
- Guía §11.5 y Apéndice A: `core/views_admin_panel.py` → `core/views/admin_panel.py`.
- Guía §2.1: Django 5.2; Meta como canal principal, Twilio demo/campañas.
- Guía §25: la firma de Twilio ya está implementada; añadir firma de Meta, límites del aula, presupuesto de IA y antiflood.
- Nueva sección en la guía: «Operación de campañas Meta» (estados, pausa, reanudar, INCIERTO) y «Costos y límites de IA».
- Un `docs/RUNBOOK.md` (factor bus): cómo desplegar y revertir, qué hacer si cae el token, si se pausa una campaña, si crece una cola, cómo restaurar RDS, cómo rotar llaves, contactos.

### P8-f — Fronteras entre apps (monolito modular)
`import-linter` con contrato: `aprende`, `portal`, `studio`, `formulario` pueden importar `core.services.*`/modelos públicos, **`core` no importa de ellas**; `learning/`, `integrations/` sin importaciones cruzadas nuevas. Se ejecuta en CI como paso informativo primero y obligatorio después. Regla escrita: **no se extrae un servicio sin una señal medida** (carga incompatible, ciclo de despliegue incompatible, equipo, requisito contractual).

---

## 11. Checklists

### 11.1 Antes de cada deploy
```
git status                                  # nada sin trackear que el código importe
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -rs                                  # 0 skipped en carrera/lock/Redis/Postgres
```
1. PR a `main` con CI verde (protección de rama activa). Desplegar siempre desde `main`.
2. Revisar migraciones nuevas: ¿compatibles con el código del rollback?
3. Flags nuevos en su valor seguro en EB.
4. `eb deploy`; Health Green; smoke: `/health/`, `/portal/login/`, `/aprende/`, `/studio/`, y un mensaje desde el teléfono interno autorizado.
5. Logs: sin `ImportError`, `NameError`, errores de lock o de Redis.
6. Anota versión desplegada y de rollback.

### 11.2 Rollback por bloque
| Bloque | Cómo se revierte |
|---|---|
| P8-a/b | versión anterior; `AULA_LOGIN_REQUIERE_DOCUMENTO=false` |
| P8-c | versión anterior (si falla el arranque por variables faltantes) |
| P6 | los cambios son filtros; versión anterior |
| P5 | `LLM_PRESUPUESTO_DIARIO_USD` alto; `LINEA_META_SOLO_REGISTRADOS=false`; `LINEA_MAX_MSG_MIN` alto |
| P4-lite | `META_CAMPANAS_V2_ENABLED=false`; la restricción parcial puede quedarse |
| P8-e | quitar `SENTRY_DSN` |
| P4-full | flags de reenganche en `false`; `EKI_ENTORNO_CARGA` solo en el entorno de carga |
| P7 | versión anterior; los paneles vuelven al cálculo en vivo |

### 11.3 [MANUAL] — lo que Cursor no puede hacer
- **Meta:** token de System User permanente (anota fecha de creación y rotación); `WHATSAPP_BUSINESS_ACCOUNT_ID` cargado; `WHATSAPP_APP_SECRET` no vacío → luego `WHATSAPP_REQUIRE_SIGNATURE=true`; plantillas aprobadas (reenganche **Utility**, bienvenida/campaña); calidad y nivel del número anotados; política de precios/costos vigente revisada.
- **Consentimiento:** texto de habeas que mencione WhatsApp, versionado; revisión legal.
- **AWS:** restore de RDS a instancia temporal (valida backup y migraciones `0159`–`0161`+); PITR activado; alarmas de 8.5; tipo de instancia real alineado entre `.ebextensions` y `.elasticbeanstalk` (hoy dicen t3.large y t3.medium); `free -m` y `ps aux --sort=-rss | head -15` del servidor para decidir pool; créditos de CPU.
- **Producto:** asignar plan (OP1/OP2/OP3) a cada cliente y grupo → luego `LINEA_META_PLAN_DEFAULT=''`.
- **Ensayo interno** con 5–10 números propios por la línea Meta: onboarding, *listo*, evaluación A–D, media, campaña lanzada dos veces, reenganche con ventana cerrada, opt-out, token inválido simulado (en el clon).
- **Clon seguro (no `eb clone` directo):** restore de snapshot a RDS temporal; en el clon `DATABASE_URL` a esa copia y `TWILIO_*`, `WHATSAPP_*`, `OPENAI_API_KEY` falsos; sin registrar webhooks; probar `kill -9` del worker (verifica `redelivered`), `migrate_locked` con dos instancias y beat único. Terminar clon y base al acabar.

### 11.4 Definición de terminado (P4 → P8)
- [ ] `detect_intent` sin subcadenas; evaluación A–D abierta nunca se salta.
- [ ] Login del aula con límites por IP/estudiante/global y códigos de un solo uso.
- [ ] Producción no arranca sin hosts, `SECRET_KEY` ni clave de API; firma de Meta exigida.
- [ ] Prueba de aislamiento entre clientes recorre el 100 % de rutas del portal y del aula.
- [ ] Presupuesto diario de IA, modo económico, antiflood y solo registrados activos; plan por defecto retirado.
- [ ] Campañas Meta: sin duplicados, `INCIERTO` nunca se reenvía, límite global, pausa automática, opt-in respetado, ventana/plantilla correctas, token inválido detiene todo.
- [ ] Sentry sin PII, logs estructurados, health profundo y alarmas con aviso a tu celular.
- [ ] (Post-lanzamiento) `Sender` unificado, reenganche en el mismo pipeline, `media_id`, calidad del número leída, carga sintética superada.
- [ ] Resúmenes diarios e índices con `EXPLAIN` verificado; política de retención de logs.
- [ ] Docs sin contradicciones, `RUNBOOK.md` escrito, contrato de dependencias en CI.
- [ ] Ensayo interno superado y restore de RDS probado.
