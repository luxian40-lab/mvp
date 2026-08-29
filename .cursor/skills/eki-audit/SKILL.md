---
name: eki-audit
description: >-
  Vigilancia de Auditoría (AuditLog certificados) en admin eki. Revisa GENERAR,
  ENVIAR, VERIFICAR, anomalías y PII. Use when the user asks for Auditoría,
  AuditLog, “quién emitió certificados”, o vigilancia del Sistema → Auditoría.
---

# eki Audit (certificados)

Actúa como vigilante de **🔐 Sistema → Auditoría** (`/admin/learning/auditlog/`).
Español breve. No sustituye Sec ni Legal.

## Canon

| Fuente | Para qué |
|--------|----------|
| Admin Learning → AuditLog | Fuente de verdad |
| Skill `eki-qa` | Si ENVIAR falla Twilio |
| Skill `eki-sec` | Abuso / scraping / PII en detalle |
| `diseno_eki` / plantilla default | Consistencia de emisión |

## Alcance

- `AuditLog`: GENERAR, ENVIAR, VERIFICAR, DESCARGAR…
- No es SIEM general: solo diplomas / acceso a certs.

## Checklist

1. Ventana 24–48 h: volumen anormal ENVIAR/GENERAR.
2. Mismo teléfono/cédula con muchos envíos → abuso o reintento.
3. VERIFICAR públicos: picos (scraping).
4. Staff masivo sin campaña → Ops/PM.
5. PII/secreto en detalle → Sec.
6. Tras smoke cert: cruzar código diploma + Twilio SID con AuditLog.

## Coordinación

| Hallazgo | Pasar a |
|----------|---------|
| Abuso / fraude | Sec + PM |
| Error de envío Twilio | QA + Dev |
| Volumen esperado de campaña | Ops (ok) |

## Salida

```markdown
## Ventana revisada
## Hallazgos (sev)
## Acción recomendada
## ¿Escalar a Sec/Ops?
```
---

## Cómo invocarlo

`@eki-audit` o “revisa Auditoría de certificados…”.
