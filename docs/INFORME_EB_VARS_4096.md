# Informe — tope CloudFormation `EnvironmentVariables` (4096) en EB

Fecha de lectura: **2026-11-20** (rama `main`, worktree `C:\Users\luxia\eki_deploy_main`).  
**Solo inventario y plan.** No se ejecutó `eb setenv`, no se borraron variables, no hubo deploy.

## Resumen ejecutivo

| Entorno | Variables (`eb printenv`) | Longitud serializada estimada* | vs tope 4096 |
| --- | ---: | ---: | --- |
| `eki-prod-final` | 99 | **4176** | **+80** (sin margen para nuevas) |
| `eki-ai-workers` | 58 | **2865** | −1231 (cupo libre) |

\*Mismo criterio que falló ayer: todos los pares `NOMBRE=valor` unidos por comas (`K=V,K2=V2,...`), como documenta CloudFormation para el option setting agregado de `aws:elasticbeanstalk:application:environment`. Medido con `eb printenv` + script local (2026-11-20).

| Objetivo | Estimación |
| --- | --- |
| Añadir `EKI_ESTADO_LINEA_SIN_ESPEJO=true` (E4) | **+33** chars en el bloque (`EKI_ESTADO_LINEA_SIN_ESPEJO=true` + separador) |
| Margen a liberar en `eki-prod-final` | **≥ 113** chars (4176 + 33 − 4096) |
| Liberación con candidatas **SEGURAS** (solo defaults de código) | **≈ 613** chars (20 variables) |
| ¿Alcanza E4 solo con SEGURAS? | **Sí** (sobra ~500 chars) |

Contexto ya documentado:

- `eb setenv EKI_RAG_INDEX_SOLO_AI=true` falló el **2026-11-19** (`docs/INFORME_W3_DECISION.md`, `docs/INFORME_GATE_BLOQUE_2.md`).
- **No reintentar** `EKI_RAG_INDEX_SOLO_AI`: prod no indexa con `EKI_ROLE=web`; AI tiene worker `rag@` (`docs/OPS_REDIS_URL_EB.md`).
- E4 en código (`EKI_ESTADO_LINEA_SIN_ESPEJO`, default `false` en `mvp_project/settings.py`); listado CRM ya lee `EstadoLinea` (`docs/PLAN_MODULARIDAD_EKI.md`).
- Comentario en código: tope CFN 4096 (2026-11-19) junto a flags de registro Meta.

Referencias de configuración:

- `docs/OPS_REDIS_URL_EB.md`, `docs/CONTINUAR_EKI.md`, `docs/RUNBOOK_EB_MAIN.md`
- `mvp_project/settings.py`, `mvp_project/settings_production.py`
- `.ebextensions/01_django.config` (`DJANGO_SETTINGS_MODULE`, `PYTHONPATH`, `RUN_MIGRATIONS`)

---

## Lectura live (`eb printenv`, sin mutar)

Comando usado: `eb printenv eki-prod-final` y `eb printenv eki-ai-workers`.

**Política de este informe:** solo **nombre** + **longitud del valor** (`len(valor)`). No se copian tokens, contraseñas ni llaves. El backup operativo debe **redactar** filas marcadas como `secreto` en el inventario.

### Mayores consumidores de caracteres (`eki-prod-final`)

| Variable | `len(valor)` | Notas |
| --- | ---: | --- |
| `WHATSAPP_TOKEN` | 201 | NO TOCAR |
| `EKI_ALLOWED_HOSTS` | 178 | NO TOCAR (hosts prod) |
| `CSRF_TRUSTED_ORIGINS` | 167 | NO TOCAR |
| `OPENAI_API_KEY` | 164 | NO TOCAR |
| `INTEGRACION_API_ALLOWED_ORIGINS` | 94 | revisar acortar URLs → DUDOSA |
| `CELERY_*` / `REDIS_CACHE_URL` | 67 c/u | NO TOCAR |
| `SECRET_KEY`, DB, Twilio, Meta… | varios | NO TOCAR |

---

## Clasificación de candidatas a **quitar del option setting** (no del código)

Criterio **SEGURA**: al borrar la variable del entorno EB, el comportamiento en `settings_production` + `settings` queda igual al actual (valor explícito = default documentado).

Criterio **DUDOSA**: cambio de producto, tuning distinto al default, duplicado funcional, o ahorro incierto por `.ebextensions`.

### SEGURAS (~613 chars liberables en `eki-prod-final`)

| Variable | `len(valor)` | Ahorro pair* | Por qué es segura |
| --- | ---: | ---: | --- |
| `META_REENGANCHE_ENABLED` | 5 | 30 | Default `false` (`settings.py`) |
| `DJANGO_DEBUG` | 5 | 19 | `settings_production` fuerza `DEBUG=False` |
| `EKI_BEHIND_CLOUDFLARE` | 4 | 27 | Default `true` en prod (`settings_production`) |
| `SECURE_HSTS_SECONDS` | 5 | 26 | Default `86400` en prod |
| `EKI_ENTREGA_DELAYS_CELERY` | 4 | 31 | Default `true` en prod |
| `DATA_LAKE_PSEUDO_SALT` | 11 | 34 | Default `eki-lake-v0` (`settings.py`) |
| `EVENT_ENGINE_EMIT_TELEMETRIA` | 4 | 34 | Default `true` (`settings.py`) |
| `ALERTA_TERRITORIAL_MIN_K` | 1 | 27 | Default `3` |
| `ALERTA_TERRITORIAL_VENTANA_HORAS` | 2 | 36 | Default `72` |
| `BOT_COMERCIAL_RAG_CANAL` | 13 | 38 | Default `bot_comercial` |
| `BOT_COMERCIAL_RAG_MAX_CHARS` | 4 | 33 | Default `1200` |
| `BOT_COMERCIAL_RAG_TOP_K` | 1 | 26 | Default `4` |
| `BOT_COMERCIAL_WHATSAPP_NUMBER` | 11 | 42 | Default `14155238886` |
| `COURSE_ENGINE_TTS_PROVIDER` | 10 | 38 | Default `elevenlabs` |
| `ELEVENLABS_MODEL_ID` | 22 | 43 | Default `eleven_multilingual_v2` |
| `AWS_S3_REGION_NAME` | 9 | 29 | Default `us-east-2` en prod |
| `USE_S3` | 4 | 12 | `setdefault('True')` en prod |
| `INTEGRACION_API_REQUIRE_KEY` | 4 | 33 | Default on en prod si unset |
| `WHATSAPP_REQUIRE_SIGNATURE` | 4 | 32 | Default `true` en prod |
| `ELASTIC_BEANSTALK` | 4 | 23 | Detección EB también vía `AWS_EXECUTION_ENV` / `AWS_EB_ENVIRONMENT_NAME` (`settings.py`) |

\*Ahorro ≈ `len(NOMBRE)+1+len(valor)+1` (incluye coma entre pares).

**Mínimo para E4:** basta cualquier subconjunto que sume **≥ 113** chars (p. ej. las cinco primeras de la tabla ≈ 133).

**No incluidas como SEGURAS** (valor en prod ≠ default):

- `BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS=1` (default código `4`)
- `BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS=400` (default `2000`)

### DUDOSAS (confirmación humana antes de borrar)

| Variable | Motivo |
| --- | --- |
| `BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS` / `BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS` | Tuning activo ≠ defaults |
| `TWILIO_PHONE_NUMBER` | Duplicado de `TWILIO_WHATSAPP_NUMBER` (mismo valor, ~42 chars); código usa ambos con fallback hardcodeado — validar campañas/HSM |
| `PYTHONPATH`, `DJANGO_SETTINGS_MODULE`, `RUN_MIGRATIONS` | También en `.ebextensions/01_django.config`; **quitar solo del console puede no bajar el conteo CFN** si el bundle sigue declarándolas |
| `LINEA_META_PLAN_DEFAULT=curso_asesor` | Default en código es vacío; cambia plan por defecto de líneas Meta |
| `STUDIO_ALLOW_PAYMENT_SIMULATION=True` | Default off; apaga simulación de pagos en Studio |
| `ELEVENLABS_VOICE_ID` | Default vacío; voz custom en prod |
| `BOT_COMERCIAL_SANDBOX_NUMBER` | ≠ default Twilio sandbox en `settings.py` |
| `ADMIN_*_V2`, `EKI_MODULE_BUILDER_UI_V2` | Default off; prod las tiene **ON** a propósito (admin Unfold) |
| `AULA_LOGIN_REQUIERE_DOCUMENTO` | Default `false`; prod `true` |
| `CELERY_CONCURRENCY=2` | Default shell `1` (`scripts/run_worker.sh`); decisión ops documentada (`CONTINUAR_EKI`) |
| `INTEGRACION_API_ALLOWED_ORIGINS` / acortar `EKI_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | Muchos chars, alto riesgo de romper login/admin |
| Migrar secretos largos a SSM/Secrets Manager | Proyecto aparte; no cuenta como “quitar var” sin cambio de código |

### NO TOCAR

- **Redis / Celery:** `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_CACHE_URL`, `USE_LOCAL_REDIS=0`, `EKI_REDIS_FAIL_CLOSED=true`, `RUN_BEAT`, `EKI_ROLE=web`, colas async críticas (`WEBHOOK_CELERY_ASYNC=false`, `NAT_WEBHOOK_CELERY_ASYNC=false` — si se quitan, default prod de `_flag_async` vuelve a **true** y se reabre el incidente Meta→Twilio de `CONTINUAR_EKI`).
- **Flags producto ya ON:** `EKI_OUTBOX_ENVIO`, `EKI_COLAS_POR_TIPO`, `EKI_CURSO_VERSIONES`, `EKI_ESTADO_LINEA_ESCRITURA`, `EKI_ESTADO_LINEA_LECTURA`, `EKI_CLIENTE_CANAL_PERMANENTE`, `EKI_CONTEXTO_CONSERVA_CLAVES`, asesoría, bandeja, etc.
- **Credenciales y DB:** `SECRET_KEY`, `DB_*`, `WHATSAPP_*`, `TWILIO_*`, `OPENAI_*`, `AWS_*` keys, `COHERE_*`, `ELEVENLABS_API_KEY`, etc.
- **`EKI_RAG_INDEX_SOLO_AI`:** no reintentar setenv; no aporta en prod web.

`eki-ai-workers` no bloquea el tope hoy; E4 se prevé en **`eki-prod-final`** (escritura de estado en web/worker conversación). Reevaluar AI solo si allí también se prende E4.

---

## Plan manual (ops)

### 0. Precondiciones

- Worktree `eki_deploy_main`, rama `main`, entorno Green.
- Ventana con posible **reinicio de configuración** (~minutos) por cada actualización de env.
- Leer `docs/CONTINUAR_EKI.md` si el cambio toca async webhooks o beat.

### 1. Backup (obligatorio antes de cualquier borrado)

```powershell
cd C:\Users\luxia\eki_deploy_main
eb printenv eki-prod-final | Out-File -Encoding utf8 backup\printenv-eki-prod-final-20261120.txt
eb printenv eki-ai-workers  | Out-File -Encoding utf8 backup\printenv-eki-ai-workers-20261120.txt
```

Redactar en el archivo las filas `secreto` antes de subir a git o compartir. El rollback operativo depende de este backup.

### 2. Liberar cupo (solo candidatas SEGURAS)

**Opción A — consola AWS:** Elastic Beanstalk → `eki-prod-final` → Configuration → Software → Environment properties → eliminar filas de la tabla SEGURAS (por lotes pequeños).

**Opción B — CLI (una variable por llamada, ejemplo):**

```powershell
aws elasticbeanstalk update-environment `
  --environment-name eki-prod-final `
  --options-to-remove "Namespace=aws:elasticbeanstalk:application:environment,OptionName=META_REENGANCHE_ENABLED"
```

Repetir por cada clave SEGURA a eliminar. Tras cada lote: esperar **Green**, `curl` `/health/` 200, smoke Celery documentado en `CONTINUAR_EKI`.

**Recomendación de lote mínimo (≥ 113 chars):**  
`META_REENGANCHE_ENABLED`, `DJANGO_DEBUG`, `EKI_BEHIND_CLOUDFLARE`, `SECURE_HSTS_SECONDS`, `EKI_ENTREGA_DELAYS_CELERY`.

**Opción C — resto de SEGURAS** si se quiere margen para futuros flags (outbox, modularidad, etc.).

### 3. Verificar cupo (local)

```powershell
eb printenv eki-prod-final
# Repetir script de conteo (coma entre pares) hasta total < 4063 antes de sumar E4
```

Umbral orientativo: **≤ 4063** deja espacio para `EKI_ESTADO_LINEA_SIN_ESPEJO=true` (+33).

### 4. Encender E4 (cuando exista cupo — **fuera de este informe**)

```powershell
eb setenv EKI_ESTADO_LINEA_SIN_ESPEJO=true -e eki-prod-final
```

Validación: flag leído en instancia (sin pegar valores secretos en logs), listado CRM estable, prueba teléfono interno en líneas con tráfico (`EKI_ESTADO_LINEA_ESCRITURA` / `LECTURA` ya true). Rollback E4: `EKI_ESTADO_LINEA_SIN_ESPEJO=false` o unset.

### 5. Rollback de liberación

Restaurar pares `NOMBRE=valor` desde el backup redactado:

```powershell
eb setenv NOMBRE=valor ... -e eki-prod-final
```

(o consola / `update-environment` con `OptionSettings`). **Sin backup no borrar.**

---

## Inventario completo `eki-prod-final` (2026-11-20)

| Variable | `len(valor)` | Tipo |
| --- | ---: | --- |
| ADMIN_AGENTES_V2 | 1 | config |
| ADMIN_CLIENTES_V2 | 1 | config |
| ADMIN_ESTUDIANTE_ALTA_V2 | 1 | config |
| ALERTA_TERRITORIAL_MIN_K | 1 | config |
| ALERTA_TERRITORIAL_VENTANA_HORAS | 2 | config |
| AULA_LOGIN_REQUIERE_DOCUMENTO | 4 | config |
| AWS_ACCESS_KEY_ID | 5 | secreto |
| AWS_S3_REGION_NAME | 9 | config |
| AWS_SECRET_ACCESS_KEY | 40 | secreto |
| AWS_STORAGE_BUCKET_NAME | 14 | config |
| BOT_COMERCIAL_RAG_CANAL | 13 | config |
| BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS | 1 | config |
| BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS | 3 | config |
| BOT_COMERCIAL_RAG_MAX_CHARS | 4 | config |
| BOT_COMERCIAL_RAG_TOP_K | 1 | config |
| BOT_COMERCIAL_SANDBOX_NUMBER | 12 | config |
| BOT_COMERCIAL_WHATSAPP_NUMBER | 11 | config |
| CELERY_BROKER_URL | 67 | config |
| CELERY_CONCURRENCY | 1 | config |
| CELERY_RESULT_BACKEND | 67 | config |
| COHERE_API_KEY | 40 | secreto |
| COURSE_ENGINE_TTS_PROVIDER | 10 | config |
| CSRF_TRUSTED_ORIGINS | 167 | config |
| CURSO_GEI_ID | 1 | config |
| DATA_LAKE_PSEUDO_SALT | 11 | secreto |
| DB_HOST | 53 | config |
| DB_NAME | 5 | config |
| DB_PASSWORD | 16 | secreto |
| DB_PORT | 4 | config |
| DB_USER | 8 | config |
| DJANGO_DEBUG | 5 | config |
| DJANGO_SETTINGS_MODULE | 31 | config |
| EKI_AGRICAPITAL_CLIENTE_ID | 2 | config |
| EKI_ALLOWED_HOSTS | 178 | config |
| EKI_ASESORIA_CONTEXTO | 4 | config |
| EKI_ASESORIA_ENTRADA | 4 | config |
| EKI_ASESORIA_PREGUNTA | 4 | config |
| EKI_AVISO_MODULO_DISPONIBLE_ENABLED | 4 | config |
| EKI_BANDEJA_ENTRADA | 4 | config |
| EKI_BEHIND_CLOUDFLARE | 4 | config |
| EKI_CERTIFICADO_ASYNC | 4 | config |
| EKI_CLIENTE_CANAL_PERMANENTE | 4 | config |
| EKI_COLAS_POR_TIPO | 4 | config |
| EKI_CONSTRUCTOR_CURSOS | 4 | config |
| EKI_CONTEXTO_CONSERVA_CLAVES | 4 | config |
| EKI_CONTEXTO_PARTICIPANTES_ENABLED | 4 | config |
| EKI_CURSO_VERSIONES | 4 | config |
| EKI_ENTREGA_DELAYS_CELERY | 4 | config |
| EKI_ESTADO_LINEA_ESCRITURA | 4 | config |
| EKI_ESTADO_LINEA_LECTURA | 4 | config |
| EKI_MEDIA_ENCODE_SOLO_AI | 4 | config |
| EKI_MODULE_BUILDER_UI_V2 | 1 | config |
| EKI_OUTBOX_ENVIO | 4 | config |
| EKI_RECORDATORIO_CURSO_ENABLED | 4 | config |
| EKI_REDIS_FAIL_CLOSED | 4 | config |
| EKI_REPORTE_CLIENTES_EMAIL | 13 | config |
| EKI_RETO_SI_CERT_EMITIDO | 4 | config |
| EKI_ROLE | 3 | config |
| EKI_TURNO_LECCION_COMPANERO | 4 | config |
| EKI_TURNO_LECCION_TIP | 4 | config |
| EKI_VIDEO_SHORTLINKS | 1 | config |
| ELASTIC_BEANSTALK | 4 | config |
| ELEVENLABS_API_KEY | 51 | secreto |
| ELEVENLABS_MODEL_ID | 22 | config |
| ELEVENLABS_VOICE_ID | 20 | config |
| EVENT_ENGINE_EMIT_TELEMETRIA | 4 | config |
| INTEGRACION_API_ALLOWED_ORIGINS | 94 | config |
| INTEGRACION_API_REQUIRE_KEY | 4 | config |
| LINEA_META_PLAN_DEFAULT | 12 | config |
| META_REENGANCHE_ENABLED | 5 | config |
| MODULO_GEI_ID | 2 | config |
| NAT_WEBHOOK_CELERY_ASYNC | 5 | config |
| OPENAI_API_KEY | 164 | secreto |
| PYTHONPATH | 28 | config |
| REDIS_CACHE_URL | 67 | config |
| RUN_BEAT | 1 | config |
| RUN_MIGRATIONS | 4 | config |
| SANDBOX_CELERY_ASYNC | 4 | config |
| SANDBOX_PROVEEDOR | 4 | config |
| SANDBOX_WHATSAPP_PHONE_ID | 15 | config |
| SECRET_KEY | 50 | secreto |
| SECURE_HSTS_SECONDS | 5 | config |
| STUDIO_ALLOW_PAYMENT_SIMULATION | 4 | config |
| TWILIO_ACCOUNT_SID | 34 | secreto |
| TWILIO_AUTH_TOKEN | 32 | secreto |
| TWILIO_PHONE_NUMBER | 22 | config |
| TWILIO_WHATSAPP_NUMBER | 22 | config |
| USE_LOCAL_REDIS | 1 | config |
| USE_S3 | 4 | config |
| WEBHOOK_CELERY_ASYNC | 5 | config |
| WHATSAPP_APP_SECRET | 32 | secreto |
| WHATSAPP_BUSINESS_ACCOUNT_ID | 15 | config |
| WHATSAPP_BUSINESS_ACCOUNT_ID_2 | 16 | config |
| WHATSAPP_NUMERO_2_E164 | 12 | config |
| WHATSAPP_PHONE_ID | 15 | config |
| WHATSAPP_PHONE_NUMBER_ID_2 | 16 | config |
| WHATSAPP_REQUIRE_SIGNATURE | 4 | config |
| WHATSAPP_TOKEN | 201 | secreto |
| WHATSAPP_VERIFY_TOKEN | 24 | secreto |

## Inventario `eki-ai-workers` (resumen)

58 variables; total serializado **2865**. Mismas familias de secretos y Redis; sin flags de conversación de prod-final. No requiere liberación para el incidente del 4096 salvo que se agreguen muchas vars nuevas.

---

## Siguientes pasos sugeridos (humano)

1. Aprobar lista SEGURA (o subconjunto mínimo de 5 vars).
2. Backup `printenv` + liberar en `eki-prod-final`.
3. Recontar; si ≤ 4063, `eb setenv EKI_ESTADO_LINEA_SIN_ESPEJO=true`.
4. QA teléfono + admin listado CRM (E4).
5. Documentar en `CONTINUAR_EKI.md` tras el setenv real (fuera de este slice).

**Explícitamente fuera de alcance de este documento:** commit, push, deploy, `eb setenv` de E4 o RAG.