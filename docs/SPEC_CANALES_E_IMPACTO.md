# Spec: canales Twilio / Meta, aula, campañas y tablero de Impacto

Fecha: 7 oct 2026. Canon para producto y desarrollo. No sustituye `docs/GUIA_PLATAFORMA_EKI.md`.

## 1. Dos canales, un producto

| Canal | Rol | Qué hace | Qué no hace |
|---|---|---|---|
| **Twilio** | Cursos y HSM históricos | Entrega de lecciones (`*listo*`), campañas Content SID, **aula** (código de 6 dígitos si olvidó la clave) | Menú de producto, agentes, plantillas Cloud API |
| **Meta Cloud API** | Canal principal de producto | Menú Formación / Asesoría, agentes, habeas de línea, **aula**, plantillas nativas, campañas | No sustituye el drip pedagógico de Twilio mientras el curso siga en esa línea |

La persona puede tener el mismo teléfono en ambos. El webhook mira el destino:

- JSON `entry` + firma `X-Hub-Signature-256` → Meta.
- Form-data Twilio + `X-Twilio-Signature` → Twilio.
- Un POST de Twilio cuyo `To` es el número de la línea Meta se acepta (HTTP 200) y **no se responde** (`ignorado_twilio`). Si escriben al chat viejo de Twilio, no hay burbuja en Meta.

## 2. Aula (Aprende)

Palabra clave: `aula`, `aprende`, `entrar al aula`, `código aula` (`aprende.acceso_whatsapp.mensaje_pide_acceso_aula`).

Respuesta (ambos canales, si hay ficha `Estudiante`):

1. Enlace a `/aprende/estudiante/login/`
2. Código de 6 dígitos (TTL `APRENDE_ACCESO_WA_TTL`, default 10 min)
3. Si es la primera vez, crea la clave en esa pantalla
4. Si olvidó la clave, vuelve a escribir **aula** y crea otra

Twilio: rama en `_procesar_twilio_webhook_cuerpo` cuando `estado_chat=ACTIVO` o onboarding completado. El envío sale por el número Twilio del curso.

Meta: `dispatch_sandbox_menu` llama `_responder_acceso_aula` **antes** del habeas de línea y **antes** del agrónomo. Así `aula` no se traga el menú ni Nat.

Sin ficha no hay código. En Meta sigue el menú o el habeas. No se inventa un estudiante.

No se toca el cuerpo de `_procesar_twilio_webhook_cuerpo` para este flujo: el de Twilio ya existía; el de Meta se envolvió en el menú.

## 3. Meta: conectar, plantillas, campañas, envíos

Variables de entorno (Elastic Beanstalk `eki-prod-final`), nunca en git:

| Variable | Para qué |
|---|---|
| `WHATSAPP_TOKEN` | Bearer Graph |
| `WHATSAPP_PHONE_ID` | Número Cloud API (15 dígitos) |
| `WHATSAPP_APP_SECRET` | Firma HMAC del webhook |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | WABA: crear/listar plantillas y Flows |
| `WHATSAPP_REQUIRE_SIGNATURE` | Debe ser true |
| `SANDBOX_PROVEEDOR=meta` | Producto por Cloud API |
| `LINEA_META_PLAN_DEFAULT` | Plan si no hay grupo ni org |

Operación en Admin (Unfold):

1. **Plantillas Meta** → redactar → *Enviar plantilla a Meta para aprobación*.
2. Esperar `APPROVED` (o *Traer de Meta si están aprobadas* / `python manage.py sync_plantillas_meta`).
3. **Campañas Meta** → audiencia (grupo o destinatarios) → *Enviar prueba a este número* (no marca la campaña como ejecutada) → *Ejecutar campañas Meta* solo si está aprobada.

Sin `WHATSAPP_BUSINESS_ACCOUNT_ID` Graph no crea ni lista plantillas. El token puede mandar mensajes y aun así no ver el catálogo.

Un HTTP 200 de Graph es «aceptado», no «entregado». Fallos posteriores: `131026` no entregable, `131047` fuera de 24 h, `131048` calidad, `131049` límite del ecosistema. Reintento automático solo `130429` y HTTP ≥500, una vez.

## 4. Números que escriben y no reciben nada (caso 7958 y demos)

El código no puede contestar un mensaje que Meta no entregó al webhook.

### Cómo diagnosticar (sin PII en tickets)

```
python manage.py diagnosticar_telefono 7958
```

En Admin: **Eventos webhook Meta**, búsqueda por sufijo.

Salidas típicas:

| Resultado | Qué pasó | Qué hacer |
|---|---|---|
| `(ninguno: el webhook no vio este teléfono)` | Meta no nos lo mandó, o escribieron al número Twilio | Confirmar que el chat es el de Cloud API (el de producto), no el de cursos |
| `ignorado_twilio` | POST Twilio hacia la línea Meta | Decirles que abran el hilo del número Meta |
| `ignorado` | Reacción u otro tipo que se salta | Pedir texto |
| `tipo_no_soportado` | Sticker, etc. | Ya responde «solo leo texto y notas de voz» |
| `sin_plan` | Llegó; no hay plan | Asignar plan (abajo) |
| `error` + `WhatsappLog.error_codigo` | Graph rechazó el envío | Ver código; `131026` el teléfono no puede recibir WA Business |
| Firma 403 | `WHATSAPP_APP_SECRET` / `WHATSAPP_REQUIRE_SIGNATURE` | Ops; no es la persona |
| Mismo `wamid` dos veces | Reintento de Meta | Normal; no se contesta dos veces |

El sufijo 7958 (ficha conocida en prod) históricamente tenía **cero** inbound Cloud API. La línea sí responde a otros. No era un «bloqueo de producto» genérico: el webhook no vio ese handset.

### Cómo dar de alta una demo a futuro

1. Crear o reutilizar `Estudiante` con el teléfono en E.164 (`57` + 10 dígitos).
2. Darle plan, en este orden:
   - `SandboxCanalSesion.plan` (solo esa persona) — Admin → Sesiones de canal, o
   - `GrupoEstudiantes.plan_linea_meta`, o
   - `Cliente.plan_linea_meta`.
3. Que **esa persona escriba** al número Meta (abre ventana 24 h). Entonces habeas → menú → `aula` / formación / asesoría.
4. Si hay que **hablar primero** (ellos no han escrito): plantilla **APPROVED** de utilidad, Campaña Meta → *Enviar prueba a este número*. No usar Twilio hacia el número Meta.
5. No hace falta un «whitelist de demos» aparte: el plan de sesión es el override.

No enviar smokes WhatsApp extra salvo que el operador lo pida.

## 5. Los 12 indicadores (tablero Impacto)

Se miden en **Portal → Analítica → Impacto** (`/portal/analitica/?s=impacto`), por organización. No se mezclan con Uso ni Retención. La brecha de género no es un 13.º: sale de cruzar sexo con S2, S3, E1 y A1.

**Publicación (las 12):**

- No se publica un corte con menos de 10 personas (`n` visible).
- Todo porcentaje lleva denominador.
- Cada indicador lleva evidencia A / B / C.
- E3 y A2 siempre dicen «contribución», no «causa».

**Cortes:** sexo (`genero`), joven 14–28 y 50+ (desde `edad`, no desde el rango 18–30 de operación), rural disperso y PDET (campos de ficha).

**Qué hay hoy vs qué falta capturar**

| Cód. | En v1 del tablero | Captura pendiente (slices siguientes) |
|---|---|---|
| S1 | A — personas únicas con ≥1 `WhatsappLog` en el periodo | — |
| S2 | A — certificados emitidos / inscritos (`ProgresoEstudiante`); retención a día 30 | — |
| S3–S4, E1–E3, A1–A3 | Visible como *pendiente de captura*, sin inventar % | Mini-diagnóstico, onboarding, encuestas 90/180, cierres de agentes, área, clima a 7 días |
| G1 | A — % de la muestra del reporte con `consentimiento_impacto` (distinto del habeas) | Flujo WhatsApp de consentimiento de impacto; menores + acudiente |
| G2 | A — % de indicadores con valor A o C en este tablero; respondientes vs no, cuando existan encuestas | — |

GEI, IA responsable y complementos de programa siguen fuera de este núcleo.

## 6. Ficha (migración, expand/contract)

Campos nuevos en `Estudiante`, todos opcionales, default que no cambia el chat:

- `rural_disperso`, `pdet` (nulos = desconocido)
- `consentimiento_impacto`, `consentimiento_impacto_en`, `consentimiento_impacto_acudiente`
- `area_unidad_ha` (para A2 cuando haya práctica)

`rango_edad` operativo no se sustituye. El corte de impacto se calcula en código.

## 7. Pruebas y deploy

- Suite: `portal/tests_impacto.py` + contrato de `/portal/analitica/?s=impacto`.
- Rollback de código: versión EB anterior. El rollback no revierte la migración: los campos nuevos pueden quedar; el tablero deja de leerse si se revierte el código, sin romper el chat.
