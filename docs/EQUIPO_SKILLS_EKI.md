# Equipo eki — skills para otra cuenta

Léelo al abrir el repo en Cursor. Las skills viven en `.cursor/skills/`. La regla que las enciende solas es `.cursor/rules/eki-team-agents.mdc`. El handoff de producción es `docs/CONTINUAR_EKI.md`. Las reglas fijas (un commit, no tocar el cuerpo del webhook, Meta primero) están en `.cursor/rules/eki.mdc`.

Modelo del chat: el automático (Composer / Auto). No lanzar subagentes de pago.

Un rol a la vez, salvo que pidan el flujo completo: CTO o PM, luego UX o Diseñador o Data, luego Dev, luego QA, y Sec o SRE si el cambio lo pide. Deploy solo si lo piden. No desplegar `HEAD` de `slice/escalabilidad-base`: cherry-pick del commit nuevo sobre el árbol que está en el aire (`docs/CONTINUAR_EKI.md`).

## Roles

| Si dicen | Skill |
|---|---|
| CTO, arquitectura, Unfold, deuda | `.cursor/skills/eki-cto/SKILL.md` |
| PM, priorizar, alcance, deploy sí o no | `.cursor/skills/eki-pm/SKILL.md` |
| UX, que el admin sea fácil | `.cursor/skills/eki-ux/SKILL.md` |
| Diseñador, tipografía, Campo / Oscuro, marca | `.cursor/skills/eki-designer/SKILL.md` |
| Nat, Nati, bot comercial, Knowledge Studio | `.cursor/skills/eki-nat/SKILL.md` |
| Aprende, aula, LMS | `.cursor/skills/eki-aprende/SKILL.md` |
| Dev, implementar | `.cursor/skills/eki-dev/SKILL.md` |
| Dev 2, rama paralela, Course Engine, audio | `.cursor/skills/eki-dev-2/SKILL.md` |
| QA, no desplegar si está rojo, media WhatsApp | `.cursor/skills/eki-qa/SKILL.md` |
| Sec, ciberseguridad, webhooks, secretos | `.cursor/skills/eki-sec/SKILL.md` |
| Auditoría, AuditLog, certificados | `.cursor/skills/eki-audit/SKILL.md` |
| Data, métricas, qué es un listo | `.cursor/skills/eki-data/SKILL.md` |
| Ops, éxito del cliente, a quién contactar | `.cursor/skills/eki-ops/SKILL.md` |
| Growth, campañas, pipeline | `.cursor/skills/eki-growth/SKILL.md` |
| Content, pedagógico, drip | `.cursor/skills/eki-content/SKILL.md` |
| Legal, habeas, PII | `.cursor/skills/eki-legal/SKILL.md` |
| SRE, Celery, EB, S3, lentitud | `.cursor/skills/eki-sre/SKILL.md` |

## Ingeniería (cuando el cambio lo pida)

| Cuándo | Skill |
|---|---|
| Tests primero | `.cursor/skills/eki-tdd/SKILL.md` |
| Gates antes de ship | `.cursor/skills/eki-constraints/SKILL.md` |
| Admin en el navegador después de un deploy | `.cursor/skills/eki-browser-qa/SKILL.md` |
| Un bug que hay que reproducir | `.cursor/skills/eki-debug/SKILL.md` |
| `eb deploy eki-prod-final` | `.cursor/skills/eki-ship/SKILL.md` |
| Un POST, ajax o webhook | `.cursor/skills/eki-api-contracts/SKILL.md` |
| Varios archivos, un corte | `.cursor/skills/eki-incremental/SKILL.md` |
| Revisión antes de merge | `.cursor/skills/eki-code-review/SKILL.md` |
| P0, producción, irreversible | `.cursor/skills/eki-doubt/SKILL.md` |
| Logs, health, fallos silenciosos | `.cursor/skills/eki-observability/SKILL.md` |

## Capacidad: cuánta gente cabe hoy

Las ~3.500 líneas de `_procesar_twilio_webhook_cuerpo` son un problema de mantenimiento. Meta, al elegir cursos, sigue entrando a esa función. Partirla no sube el cupo. El cupo lo marca la caja que está corriendo.

Números en `core/infra_monitor.py` (`CAPACITY_LIMITS`), para **1× t3.medium**, Redis en esa misma instancia y RDS `db.t4g.micro`. Re-medir con `python manage.py medir_capacidad_eki`.

| | Cómodo | Techo |
|---|---|---|
| Estudiantes activos en la base | 5.000 | 15.000 |
| Mensajes de WhatsApp a la vez | 30 | 80 |
| Destinatarios de una campaña | 500 | 2.000 |

Salida a Meta: `WA_META_MPS` default **20 mensajes por segundo** (settings, 4 de octubre de 2026; el tier real del número no se reabrió ese día). Contactos únicos de negocio en 24 h, setting `META_LIMITE_CONTACTOS_24H`: **1.000**.

El archivo `.ebextensions/options.config` dice t3.large y MaxSize 6. Eso no es la caja documentada como viva. Pasar a dos instancias el mismo día exige Redis gestionado: hoy Redis es local y cada caja tendría su propia cola.

`WEBHOOK_CELERY_ASYNC` sigue en false por defecto: el curso se procesa en el request del web. El siguiente paso de cupo, si la cola de mensajes se acerca a 80 a la vez, es ese flag y un worker, no reescribir las 3.500 líneas.
