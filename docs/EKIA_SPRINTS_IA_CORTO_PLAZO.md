# EkiA / agentes IA — backlog por sprints (corto plazo)

**Clasificación:** plan de ejecución IA · solo implementable en semanas/meses  
**Emisión:** 31 agosto 2026 · **v1.0**  
**Fuente estratégica:** `docs/EKIA_INVESTIGACION_AGENTES.md` (decisiones, agentes, capas 0–1)  
**Fuente PM:** `docs/PM_RUTA_EKIA_FASE0_FASE1_CRONOGRAMA.md`  
**Explícitamente FUERA de este doc:** IQ Rural, Gemelo Digital, modelos propios, lake curated, alertas al cliente, Arco C–D, visión 2029–2035.

> **Cadencia:** sprint = **2 semanas hábiles** (lun–vie). Review + retro viernes semana 2. Deploy solo con QA_PASS.  
> **Capacidad honesta:** 1 Dev ~12–14 días útiles/sprint en IA; ~6 días reservados a Module Builder admin (P1). Resto: QA, Sec, SRE, Nat, Legal en gates.

---

## 0. Qué significa “agente” aquí

| Término | Significado en eki |
|---------|------------------|
| **Agente de producto** | Rol conversacional con contrato fijo (Nat/EkiA, tutor, PQRS, GEI, retención) |
| **Especialista interno** | Tool o sub-flujo bajo EkiA (RAG, catálogo, clima, diagnóstico, riesgo) |
| **Orquestador** | Servicio que elige especialista; **no** es un LLM con acceso a SQL |
| **Agente del equipo eki** | Skill Cursor (`eki-dev`, `eki-nat`, …) — quien implementa |

**Decisión cerrada (ago 2026):** EkiA = evolución de **Nat comercial**. Una cara (marca) · varios especialistas · **no** fusionar con tutor/PQRS/GEI.

---

## 1. Inventario de agentes IA (estado y sprint objetivo)

### 1.1 Agentes de producto (líneas separadas — no tocar contrato)

| Agente | Estado ago 2026 | Sprint “listo gobernado” | Notas |
|--------|-----------------|--------------------------|-------|
| **EkiA / Nat** (comercial) | Producción | Sprint 12 (~may 2027) | Foco de este doc |
| Tutor educativo | Producción | Sprint 6 (trazas mínimas) | Solo Capa 0 compartida |
| PQRS | Producción | — | Sin sprint dedicado 2026 |
| GEI secuencial | Producción | — | Sin RAG; no mezclar |
| Consultor retención | Producción | Sprint 8 (costos) | Portal; heurística + LLM opcional |

### 1.2 Especialistas bajo EkiA (orquestador)

| Especialista | Existe hoy | Sprint primera versión formal | Sprint maduro |
|--------------|------------|------------------------------|---------------|
| Router / intención | Implícito en `nat_router` | Sprint 14 | Sprint 16 |
| Diagnóstico campo | `nat_diagnostico.py` | Sprint 6 (tests) | Sprint 15 |
| RAG biblioteca org | `biblioteca_nat_service` | Sprint 4 (tenancy) | Sprint 14 |
| Catálogo / Plan B | `nat_catalogo_service` | Sprint 3 (degradación) | Sprint 14 |
| Clima Open-Meteo | Producción | Sprint 17 (evento) | Sprint 17 |
| Agente riesgo / veto | Parcial | Sprint 5 | Sprint 13 |
| HITL Knowledge Studio | Producción | Sprint 5 (ritual) | continuo |
| Clasificador señales | **No existe** | Sprint 11 | Sprint 13 |
| Emisor outbox | **No existe** | Sprint 12 | Sprint 14 |

### 1.3 Lo que NO implementamos en estos sprints (honesto)

- Modelo propio / fine-tune con chats del cliente  
- Alertas sanitarias/plaga visibles al cliente B2B  
- Event Engine durable tipo Kinesis/MSK  
- Fusionar agentes educativo + comercial  
- LLM con lectura libre a PostgreSQL  
- Rebrand masivo código `nat_*` → `ekia_*` (solo UI/copy gradual)

---

## 2. Baseline (pre-Sprint 1) — ya hecho ago 2026

| Item | Estado |
|------|--------|
| ElastiCache Redis prod | ✅ |
| `eki-ai-workers` (RAG, media, course_engine) | ✅ |
| Nat respuesta más rápida | ✅ QA_PASS |
| `EventoIA` + replay AI Ops | ✅ parcial |
| `ContextoAgroSession` | ✅ |
| Knowledge Studio HITL | ✅ |
| Module Builder v2 admin | ✅ desplegado |

**Sprint 1 arranca:** 1 sep 2026.

---

## 3. Mapa de sprints (calendario)

```text
2026                          2027
S1 S2 S3 S4 S5 S6 │ S7 S8 S9 S10 S11 S12 │ S13 S14 S15 S16 S17 S18
sep      oct  nov │ dic  ene  feb  mar   │ abr  may
◄── CAPA 0 ─────►│◄────── CAPA 1 ───────►│
Fase 0 cierre S6  │ F1 kickoff S7         │ F1 cierre S18
```

| Sprint | Fechas (lun inicio) | Tema | Capa |
|--------|---------------------|------|------|
| S1 | 1 sep 2026 | Trazas + fuente_usada | 0 |
| S2 | 15 sep | Prompts + kill switch | 0 |
| S3 | 29 sep | Degradación catálogo + costos v0 | 0 |
| S4 | 13 oct | Tenancy + adversaria v1 | 0 |
| S5 | 27 oct | Matriz tools + HITL ritual + riesgo v0 | 0 |
| S6 | 10 nov | Chroma durable + cierre F0 | 0 |
| S7 | 24 nov | Taxonomía señales + org piloto | 1 prep |
| S8 | 8 dic | Municipio DIVIPOLA v0 | 1 |
| S9 | 22 dic | Clasificador reglas (shadow) | 1 |
| S10 | 5 ene 2027 | Outbox + tabla eventos | 1 |
| S11 | 19 ene | Clasificador LLM-asistido | 1 |
| S12 | 2 feb | Publicador → S3 raw | 1 |
| S13 | 16 feb | Agregado interno admin | 1 |
| S14 | 2 mar | Orquestador v1 + tools formales | 1 |
| S15 | 16 mar | Diagnóstico → señales | 1 |
| S16 | 30 mar | Router explícito + métricas | 1 |
| S17 | 13 abr | Clima + eventos + piloto org 1 | 1 |
| S18 | 27 abr | Piloto org 2 + cierre F1 | 1 |

**Fin objetivo Capa 0:** 21 nov 2026 (fin S6)  
**Fin objetivo Capa 1:** 22 may 2027 (fin S18)  
**Buffer conservador:** +1 sprint (+2 sem) por slip → **5 jun 2027**

---

## 4. Sprints detallados — Capa 0 (gobernanza)

### Sprint 1 · Trazas comerciales completas

**Fechas:** 1–12 sep 2026  
**Objetivo:** Toda interacción WA comercial deja rastro replayable con **fuente usada**.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S1-1 | Registrar `fuente_usada` en EventoIA (rag, catalogo, regla, clima, plan_b) | Dev + Nat | 2 | Campo en modelo + migración |
| S1-2 | Cablear flujo `_procesar_bot_comercial_*` → siempre EventoIA al responder | Dev | 2 | 100% paths críticos |
| S1-3 | AI Ops replay muestra fuente en UI | Dev + UX | 1 | Screenshot admin |
| S1-4 | Smoke regresión Nat post-Redis | QA | 1 | QA_PASS |

**No hacer:** refactor masivo views; UI EkiA rename.  
**Deploy:** fin sprint si QA_PASS.  
**Riesgo:** paths legacy sin hook → +2 días slip S2.

---

### Sprint 2 · Prompts versionados + kill switch

**Fechas:** 15–26 sep 2026  
**Objetivo:** Prompts en repo; Nat responde sin LLM si flag OFF.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S2-1 | Extraer 5 prompts Nat a `core/prompts/nat/` con versión | Dev + Nat | 2 | PR + lista prompts |
| S2-2 | `EKI_NAT_LLM_ENABLED=0` → reglas + catálogo + biblioteca | Dev + SRE | 2 | Test unitario |
| S2-3 | Copy degradación (mensaje usuario cuando sin LLM) | Nat | 0.5 | Texto aprobado PM |
| S2-4 | Documentar kill switch en runbook | SRE | 0.5 | 1 párrafo en RUNBOOK |

**Gate Sec:** kill switch no expone stack trace al usuario.  
**Deploy:** staging primero; prod si smoke OK.

---

### Sprint 3 · Degradación catálogo + costos v0

**Fechas:** 29 sep – 10 oct 2026  
**Objetivo:** Plan B documentado en código; costo Nat visible internamente.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S3-1 | Plan B tipado cuando org sin catálogo (no inventar marca) | Dev + Nat | 2 | Test caso vacío |
| S3-2 | Contador tokens/completion por org en log estructurado | Dev + Data | 2 | JSON log diario |
| S3-3 | Export CSV semanal costos (management command) | Dev | 1 | Comando documentado |
| S3-4 | Legal kickoff PI 1 pág (paralelo, sin dev) | Legal + PM | — | Borrador 15 oct |

**Paralelo P1:** Module Builder — guía upload video (UX, 1 día).

---

### Sprint 4 · Tenancy duro + adversaria v1

**Fechas:** 13–24 oct 2026  
**Objetivo:** Org A nunca ve RAG/catálogo de org B; tests CI.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S4-1 | Tests tenancy biblioteca + catálogo (2 orgs fixture) | Dev + QA | 3 | CI verde |
| S4-2 | Test alucinación: precio sin producto → Plan B o “no sé” | Dev + Nat | 2 | Caso tomate/mancha |
| S4-3 | Test inyección prompt en mensaje usuario | Dev + Sec | 2 | No ejecuta tool arbitraria |
| S4-4 | Sec review webhook comercial HMAC | Sec | 1 | Sin Critical |

**Honesto:** adversaria v1 ≠ cobertura total; lista 10 casos mínimos en `core/tests_nat_adversarial.py`.

---

### Sprint 5 · Matriz tools + HITL + agente riesgo v0

**Fechas:** 27 oct – 7 nov 2026  
**Objetivo:** Qué puede leer/enviar EkiA; ritual HITL semanal; veto agroquímico básico.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S5-1 | Doc `docs/EKIA_MATRIZ_TOOLS.md` + enforcement lectura catálogo | Nat + Sec + Dev | 2 | Doc + 1 check código |
| S5-2 | Flag escalamiento si menciona dosis/agroquímico sin etiqueta | Dev + Nat | 2 | Test + copy |
| S5-3 | Ritual HITL: dueño Content + acta semanal template | Ops + Nat | 0 | Calendario fijado |
| S5-4 | Rate limit respuestas comerciales por tel/org (anti-abuso) | Dev + Sec | 2 | 429 interno log |

**PM:** nombrar org piloto antes fin sprint.

---

### Sprint 6 · Chroma durable + cierre Capa 0

**Fechas:** 10–21 nov 2026  
**Objetivo:** Vector no solo en disco EB; checklist GO F0 completo.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S6-1 | Chroma en EFS o path durable + doc restore | SRE + Dev 2 | 4–5 | Reindex probado |
| S6-2 | Smoke piloto: saludo → diag → precio → Plan B (1 org) | QA + Nat | 2 | QA_PASS escrito |
| S6-3 | Checklist §10 EKIA investigación (GO F0) | PM | — | Todo ✅ o excepción escrita |
| S6-4 | Tutor educativo: EventoIA en path tutor (mínimo) | Dev | 2 | Opcional si tiempo |

**Ceremonia:** Review F0 — 21 nov 2026.  
**Si Chroma slip:** plan durable aprobado + implementación dic; no bloquea kickoff F1.

---

## 5. Sprints detallados — Capa 1 (señales tipificadas)

### Sprint 7 · Taxonomía + org piloto

**Fechas:** 24 nov – 5 dic 2026  
**Objetivo:** 10–15 tipos señal agro acordados; 1 org piloto nombrada.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S7-1 | Workshop 2h taxonomía v0 (`agro.plaga.*`, `agro.cultivo.*`, …) | PM + Nat + Data | 1 | Doc 1 pág |
| S7-2 | Contrato JSON ejemplo evento tipado | Data + Dev | 1 | Schema en doc |
| S7-3 | Contrato comercial org piloto (agregados internos) | PM + Growth | — | Nombre org |
| S7-4 | Module Builder estabilización (P1) | Dev + QA | 4 | Upload MP4 verde |

**Precondición F1:** F0 ≥80% (ideal 100% S1–S5).

---

### Sprint 8 · Municipio canónico DIVIPOLA v0

**Fechas:** 8–19 dic 2026  
**Objetivo:** Municipio deja de ser texto libre en diagnóstico/piloto.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S8-1 | Catálogo DIVIPOLA mínimo (CSV o tabla) municipios Colombia | Dev + Data | 2 | Top 500 o completo |
| S8-2 | Resolver municipio en `ContextoAgroSession` → código | Dev | 3 | unknown explícito |
| S8-3 | UI/admin: ver código resuelto en sesión agro | Dev + UX | 1 | Campo readonly |
| S8-4 | Costos retención: mismo export para consultor portal | Dev | 1 | Opcional |

**Honesto:** vereda/geocod fina puede quedar `unknown` hasta S15.

---

### Sprint 9 · Clasificador reglas (modo shadow)

**Fechas:** 22 dic 2026 – 2 ene 2027  
**Objetivo:** Reglas etiquetan consulta; **no** cambian respuesta Nat aún.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S9-1 | `clasificar_consulta_agro(texto, contexto)` → tipo + confianza | Dev + Nat | 4 | 20 casos test |
| S9-2 | Log shadow: clasificación vs conversación real | Dev | 2 | Solo admin |
| S9-3 | QA no regresión WA (vacaciones mínimas) | QA | 1 | QA_PASS |

**Nota:** sprint corto por festivos; slip común → absorber en S10.

---

### Sprint 10 · Outbox transaccional

**Fechas:** 5–16 ene 2027  
**Objetivo:** Mismo COMMIT persiste hecho + fila outbox.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S10-1 | Modelo `EventOutbox` + migración | Dev | 2 | Idempotente |
| S10-2 | Escribir outbox al cerrar turno comercial relevante | Dev | 3 | Sin doble write manual |
| S10-3 | Worker Celery publica outbox (log primero; S3 en S12) | Dev + SRE | 3 | DLQ log |
| S10-4 | Sec: payload outbox sin PII en agregados | Sec | 1 | Review |

---

### Sprint 11 · Clasificador LLM-asistido

**Fechas:** 19–30 ene 2027  
**Objetivo:** Mejorar precisión vs reglas; sigue shadow opcional.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S11-1 | LLM clasifica solo taxonomía v0 (JSON estricto) | Dev + Nat | 3 | Temperatura baja |
| S11-2 | Fallback reglas si LLM falla | Dev | 1 | Degradación |
| S11-3 | Métrica precisión manual (muestra 50 chats piloto) | Data + Nat | 2 | ≥70% v0 aceptable |
| S11-4 | Prompt clasificador versionado | Nat | 1 | En repo |

**Honesto:** 70% v0 es OK; perfeccionismo bloquea. Iterar S15+.

---

### Sprint 12 · Publicador S3 raw (mini-lake)

**Fechas:** 2–13 feb 2027  
**Objetivo:** Eventos en S3 particionados `raw/agro/YYYY/MM/DD/`.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S12-1 | Prefijo S3 analítico separado de media prod | SRE | 1 | IAM mínimo privilegio |
| S12-2 | Consumidor outbox → JSON gzip a S3 | Dev | 3 | 7 días retención test |
| S12-3 | Script listar partición (ops) | Dev | 1 | CLI documentado |
| S12-4 | Alerta si lag outbox > 1h | SRE | 1 | Log/metric |

---

### Sprint 13 · Agregado interno admin

**Fechas:** 16–27 feb 2027  
**Objetivo:** Tablero eki: top señales por municipio/semana sin PII.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S13-1 | Job batch: conteos por municipio + tipo + semana | Dev + Data | 3 | Tabla materializada o SQL |
| S13-2 | Vista admin `/admin/ai-ops/señales/` (solo staff) | Dev + UX | 3 | k-anonimato ≥3 |
| S13-3 | Agente riesgo: bloqueo refuerzo post-S5 | Dev | 1 | Cierre deuda |

**No hacer:** mostrar al cliente B2B aún (decisión D2).

---

### Sprint 14 · Orquestador v1 + tools formales

**Fechas:** 2–13 mar 2027  
**Objetivo:** Un servicio elige RAG / catálogo / clima / diag; Nat deja lógica dispersa.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S14-1 | `EkiAOrchestrator` (nombre interno) con interface tools | Dev + Nat | 5 | Sin SQL al LLM |
| S14-2 | Tools: rag_query, catalog_lookup, weather_block, diag_step | Dev | 4 | Cada uno testeado |
| S14-3 | EventoIA registra tool invocada | Dev | 1 | Trazabilidad |

**Riesgo alto:** refactor puede slip 1 sprint — PM congelar scope a 3 tools si falta tiempo.

---

### Sprint 15 · Diagnóstico → señales

**Fechas:** 16–27 mar 2027  
**Objetivo:** Al completar diagnóstico, emitir evento tipado + territorio.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S15-1 | Fin diagnóstico → outbox `agro.diagnostico.completado` | Dev | 2 | Payload sin teléfono |
| S15-2 | Foto cultivo: metadata evento sin almacenar imagen en lake | Dev + Sec | 2 | Solo hash/ref |
| S15-3 | Mejorar clasificador con contexto diag | Dev + Nat | 2 | Shadow ON |

---

### Sprint 16 · Router explícito + métricas orquestador

**Fechas:** 30 mar – 10 abr 2027  
**Objetivo:** Intención visible; latencia por tool.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S16-1 | Router intención (precio, plaga, clima, general, escalamiento) | Dev + Nat | 3 | Matriz intención→tool |
| S16-2 | Métricas p95 latencia por tool en admin | Dev + SRE | 2 | Dashboard AI Ops |
| S16-3 | Regresión orquestador (20 conversaciones golden) | QA + Nat | 2 | QA_PASS |

---

### Sprint 17 · Clima como evento + piloto org 1

**Fechas:** 13–24 abr 2027  
**Objetivo:** Consultas clima generan evento; piloto activo con revisión quincenal.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S17-1 | Evento `clima.consulta` en outbox | Dev | 2 | Municipio canónico |
| S17-2 | Activar clasificación **live** (no solo shadow) en org piloto 1 | PM + Dev | 1 | Flag por org |
| S17-3 | Reunión quincenal piloto (Ops + Nat) | Ops | — | Acta #1 |
| S17-4 | Smoke end-to-end piloto | QA | 2 | QA_PASS |

---

### Sprint 18 · Piloto org 2 + cierre Capa 1

**Fechas:** 27 abr – 8 may 2027  
**Objetivo:** Checklist F1; documento lecciones para Arco B.

| ID | Historia | Agente equipo | Días Dev | DoD |
|----|----------|---------------|----------|-----|
| S18-1 | Org piloto 2 (opcional) o ampliar volumen org 1 | PM | — | Decisión datos |
| S18-2 | ≥80% consultas piloto con evento + territorio | Data | 2 | Informe |
| S18-3 | ≥30 días historia S3 raw piloto | SRE | 1 | Verificación |
| S18-4 | Doc `EKIA_LECCIONES_PILOTO.md` | PM + Nat | 1 | Entregable |
| S18-5 | Review F1 + go/no-go Arco B prep | PM | — | Jun 2027 |

**Ceremonia cierre:** 22 may 2027 (review); buffer hasta 5 jun.

---

## 6. Sprints compartidos (otros agentes IA — mínimo)

No bloquean EkiA; se hacen si sobra capacidad o en S6/S8.

| Sprint | Agente | Historia mínima | Días |
|--------|--------|-----------------|------|
| S6 | Tutor | EventoIA + fuente en respuesta tutor educativo | 2 |
| S8 | Retención | Token/costo consultor portal en mismo export | 1 |
| S16 | PQRS | Checklist: PQRS no llama RAG comercial (test) | 1 |

**Honesto:** tutor/PQRS/GEI no tienen roadmap de orquestador en 2026–2027; solo gobernanza compartida Capa 0.

---

## 7. Delegación PM por sprint (plantilla)

Copiar al inicio de cada sprint:

```markdown
## Sprint N — [tema]
**Inicio:** DD-MMM-YYYY · **Fin:** DD-MMM-YYYY
**Objetivo:** [1 frase]
**Capacidad Dev IA:** __ días · **Builder reservado:** __ días

| Rol | Responsable | Entregable sprint |
|-----|-------------|-------------------|
| PM | Andrés | Scope congelado + deploy sí/no |
| Dev | @eki-dev | Historias S*-1..n |
| Nat | @eki-nat | Prompts, taxonomía, casos golden |
| QA | @eki-qa | QA_PASS |
| Sec | @eki-sec | Review si webhook/outbox/PII |
| SRE | @eki-sre | Infra S3/Redis/Chroma |
| Legal | @eki-legal | Solo si sprint toca PI/contrato |

**Fuera de scope:** [lista explícita]
**Deploy prod:** [fecha] · Gate: QA_PASS
```

---

## 8. Definición de Done (DoD) global IA

Una historia IA está **done** solo si:

1. Código + tests (unit o adversarial) en CI  
2. Degradación documentada si usa LLM  
3. Tenancy respetado si toca datos org  
4. EventoIA u outbox si es flujo comercial (desde S1)  
5. QA smoke Nat si tocó webhook comercial  
6. Sin Critical/High Sec en diff  
7. PM marcó deploy o excepción escrita  

---

## 9. Velocidad honesta y slips

| Supuesto | Realidad |
|----------|----------|
| 2 sem = 10 días Dev | 6–8 días efectivos (deploy, soporte, Builder) |
| Clasificador 90% día 1 | 70% v0 a las 8 semanas; iterar |
| Orquestador sprint único | A menudo 2 sprints (S14–S16) |
| Legal PI | 2–4 sem calendario paralelo; no bloquea S1–S5 |
| Festivos dic–ene | S9 más corto; buffer en S10 |

**Velocidad medida (a establecer en S4):** story points completados/sprint → ajustar S7+.

---

## 10. Qué viene después de S18 (solo referencia, no sprintear aún)

| Tema | Cuándo honesto | Doc |
|------|----------------|-----|
| Lake curated | 2027 H2 | Visión cap. 11 |
| Alertas territoriales v1 | 2027 H2 | Arco B |
| Predicción demanda Nat | 2028 | Capa 2 |
| Fine-tune español rural | 2029+ | Capa 3 |
| Modelo propio | 2032+ | Capa 4 |

---

## 11. Enlaces entre documentos

| Documento | Rol |
|-----------|-----|
| `EKIA_INVESTIGACION_AGENTES.md` | **Por qué** (estrategia, decisiones D1–D5, escenarios) |
| **Este doc** | **Cómo y cuándo** (sprints, historias, fechas) |
| `PM_RUTA_EKIA_FASE0_FASE1_CRONOGRAMA.md` | PM delegación, riesgos, hitos negocio |
| `NAT_GUIA_COMPLETA.md` | Operación Nat hoy |
| `VISION_TECNOLOGICA_EKI_2026_2035.md` | Norte largo plazo — **no** backlog sprint |

---

## 12. Kickoff inmediato — Sprint 1 (1 sep 2026)

**Invocar:** `@eki-pm` `@eki-dev` `@eki-nat` `@eki-qa`

| # | Acción | Dueño | Fecha límite |
|---|--------|-------|--------------|
| 1 | Congelar scope S1 (4 historias, nada más) | PM | 1 sep |
| 2 | Implementar S1-1 + S1-2 | Dev | 8 sep |
| 3 | Listar 5 prompts para S2 | Nat | 5 sep |
| 4 | Baseline smoke Nat | QA | 3 sep |
| 5 | Kickoff Legal PI (paralelo) | Legal | 15 sep |

---

*Documento vivo v1.0. PM actualiza estado sprint al cierre de cada quincena. Estrategia: `EKIA_INVESTIGACION_AGENTES.md`.*
