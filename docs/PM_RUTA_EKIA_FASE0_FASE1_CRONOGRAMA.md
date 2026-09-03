# PM — Ruta EkiA · cronograma por sprints

**Clasificación:** plan PM · delegación y fechas  
**Emisión:** 31 agosto 2026 · **v2 (sprints)**  
**Backlog detallado IA:** [`docs/EKIA_SPRINTS_IA_CORTO_PLAZO.md`](EKIA_SPRINTS_IA_CORTO_PLAZO.md) ← **historias, agentes IA, DoD por sprint**  
**Estrategia agentes:** [`docs/EKIA_INVESTIGACION_AGENTES.md`](EKIA_INVESTIGACION_AGENTES.md)

> **Cadencia:** sprint = **2 semanas**. 18 sprints = sep 2026 → may 2027 (Capa 0 + Capa 1).  
> **Capacidad:** Dev IA ~12 días/sprint; ~6 días reservados Module Builder (P1).

---

## 1. Respuesta ejecutiva

| Pregunta | Respuesta |
|----------|-----------|
| ¿F0 y F1 en paralelo? | **F0 sprints S1–S6** (sep–nov 2026). **F1 sprints S7–S18** (dic 2026–may 2027). Sin solapamiento fuerte. |
| ¿Usamos el MD de investigación agentes? | **Sí** — decisiones y arquitectura allí; **sprints ejecutables** en `EKIA_SPRINTS_IA_CORTO_PLAZO.md`. |
| ¿Cuánto tiempo? | **18 sprints × 2 sem = 36 sem ≈ 8,5 meses** (objetivo fin **22 may 2027**; conservador **5 jun 2027**). |
| ¿Qué ya tenemos? | Redis, ai-workers, Builder v2, EventoIA parcial, KS HITL, ContextoAgro (ago 2026). |

---

## 2. Índice de sprints

| Sprint | Fechas | Fase | Tema | Doc detalle |
|--------|--------|------|------|-------------|
| **S1** | 1–12 sep 2026 | F0 | Trazas + fuente_usada | [§4 S1](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-1--trazas-comerciales-completas) |
| **S2** | 15–26 sep | F0 | Prompts + kill switch | [§4 S2](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-2--prompts-versionados--kill-switch) |
| **S3** | 29 sep – 10 oct | F0 | Plan B + costos v0 | [§4 S3](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-3--degradación-catálogo--costos-v0) |
| **S4** | 13–24 oct | F0 | Tenancy + adversaria | [§4 S4](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-4--tenancy-duro--adversaria-v1) |
| **S5** | 27 oct – 7 nov | F0 | Matriz tools + HITL | [§4 S5](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-5--matriz-tools--hitl--agente-riesgo-v0) |
| **S6** | 10–21 nov | F0 | Chroma + **cierre F0** | [§4 S6](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-6--chroma-durable--cierre-capa-0) |
| **S7** | 24 nov – 5 dic | F1 prep | Taxonomía + org piloto | [§5 S7](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-7--taxonomía--org-piloto) |
| **S8** | 8–19 dic | F1 | DIVIPOLA v0 | [§5 S8](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-8--municipio-canónico-divipola-v0) |
| **S9** | 22 dic – 2 ene 27 | F1 | Clasificador reglas shadow | [§5 S9](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-9--clasificador-reglas-modo-shadow) |
| **S10** | 5–16 ene | F1 | Outbox | [§5 S10](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-10--outbox-transaccional) |
| **S11** | 19–30 ene | F1 | Clasificador LLM | [§5 S11](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-11--clasificador-llm-asistido) |
| **S12** | 2–13 feb | F1 | S3 raw mini-lake | [§5 S12](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-12--publicador-s3-raw-mini-lake) |
| **S13** | 16–27 feb | F1 | Tablero señales admin | [§5 S13](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-13--agregado-interno-admin) |
| **S14** | 2–13 mar | F1 | Orquestador v1 | [§5 S14](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-14--orquestador-v1--tools-formales) |
| **S15** | 16–27 mar | F1 | Diagnóstico → señales | [§5 S15](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-15--diagnóstico--señales) |
| **S16** | 30 mar – 10 abr | F1 | Router + métricas | [§5 S16](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-16--router-explícito--métricas-orquestador) |
| **S17** | 13–24 abr | F1 | Clima evento + piloto 1 | [§5 S17](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-17--clima-como-evento--piloto-org-1) |
| **S18** | 27 abr – 8 may | F1 | **Cierre F1** | [§5 S18](EKIA_SPRINTS_IA_CORTO_PLAZO.md#sprint-18--piloto-org-2--cierre-capa-1) |

---

## 3. Línea visual

```text
sep 2026          nov        dic 2026         mar 2027        may 2027
│ S1 S2 S3 S4 S5 S6 │ S7 S8 S9 S10 S11 S12 │ S13 S14 S15 S16 │ S17 S18 │
│◄── CAPA 0 ──────►│◄──────── CAPA 1 ───────────────────────────────►│
21 nov: Review F0  1 dic: F1 GO          22 may: Review F1
```

---

## 4. Ceremonias por sprint

| Cuándo | Qué | Duración | Dueño |
|--------|-----|----------|-------|
| Lun S1 | Planning: leer sprint en `EKIA_SPRINTS_IA_CORTO_PLAZO.md`, congelar scope | 45 min | PM |
| Diario | Standup async (semáforo Builder + IA) | 5 min | Dev |
| Vie S2 | Review demo + QA_PASS + deploy sí/no | 30 min | PM + QA |
| Vie S2 | Retro: 1 mejorar / 1 stop | 15 min | PM |
| Fin S6 / S18 | Review fase + checklist go/no-go | 60 min | PM |

---

## 5. Delegación agentes equipo eki

| Sprint tipo | Invocar |
|-------------|---------|
| Nat, prompts, taxonomía, casos golden | `@eki-nat` + `@eki-dev` |
| Outbox, clasificador, orquestador | `@eki-dev` + `@eki-data` |
| Infra S3, Redis, Chroma, workers | `@eki-sre` + `@eki-dev` |
| Smoke WA, adversaria | `@eki-qa` |
| Webhook, PII, matriz tools | `@eki-sec` |
| PI, contrato piloto | `@eki-legal` + `@eki-growth` |
| Admin UI replay / señales | `@eki-ux` + `@eki-dev` |
| Module Builder (paralelo P1) | `@eki-dev` + `@eki-ux` + `@eki-qa` |

**Regla:** máximo **2 frentes** Dev por sprint (IA + Builder).

---

## 6. Gates de fase

### Cierre F0 — fin Sprint 6 (21 nov 2026)

- [ ] Checklist GO §10 `EKIA_INVESTIGACION_AGENTES.md`
- [ ] QA_PASS smoke org piloto
- [ ] Kill switch probado
- [ ] Tenancy CI verde
- [ ] PI borrador Legal
- [ ] Chroma durable o plan ≤ dic con fecha

### Cierre F1 — fin Sprint 18 (22 may 2027)

- [ ] ≥80% eventos tipificados org piloto
- [ ] ≥30 días S3 raw
- [ ] Tablero admin agregados sin PII
- [ ] Orquestador v1 en prod piloto
- [ ] `EKIA_LECCIONES_PILOTO.md` escrito
- [ ] QA_PASS + Sec sin Critical/High

---

## 7. Track paralelo P1 (no cancelar)

| Sprint | Builder / admin |
|--------|-----------------|
| S1–S2 | Estabilizar upload MP4 + preview WA |
| S3 | Guía 1 pág “módulo en 15 min” |
| S7 | QA regresión builder |
| S14+ | Solo fixes; no features grandes |

---

## 8. Hitos negocio (fecha fija)

| Fecha | Hito |
|-------|------|
| 12 sep 2026 | S1: fuente_usada en replay |
| 26 sep 2026 | S2: Nat sin LLM si flag OFF |
| 24 oct 2026 | S4: tenancy CI |
| **21 nov 2026** | **Capa 0 cerrada** |
| 5 dic 2026 | S7: taxonomía v0 |
| 13 feb 2027 | S12: eventos en S3 |
| 13 mar 2027 | S14: orquestador v1 |
| **22 may 2027** | **Capa 1 cerrada** |

---

## 9. Riesgos → sprint afectado

| Riesgo | Sprint | Mitigación |
|--------|--------|------------|
| Builder come Dev | S3, S7, S14 | Dev 2 en media |
| Festivos ene | S9 | Buffer S10 |
| Orquestador grande | S14–S16 | Scope 3 tools |
| Legal lento | S7 piloto | Agregados solo internos |
| Org sin volumen | S17–S18 | 2ª org en S18 |

---

## 10. Resumen duración

| Métrica | Valor |
|---------|-------|
| Sprints totales | 18 |
| Semanas | 36 |
| Meses calendario | ~8,5 |
| Inicio | 1 sep 2026 |
| Fin objetivo | 22 may 2027 |
| Fin conservador (+1 sprint) | 5 jun 2027 |
| Días Dev IA (suma historias) | ~73–98 |

---

## 11. Decisión PM (31 ago 2026)

| Tema | Decisión |
|------|----------|
| Backlog sprint IA | **`EKIA_SPRINTS_IA_CORTO_PLAZO.md`** |
| Kickoff | **Sprint 1 — 1 sep 2026** |
| Visión 3 años | Solo referencia; no sprintear |
| Deploy | Cada 2 sem si QA_PASS |

---

## 12. Sprint activo

**Sprint 1** · 1–12 sep 2026 · Ver [`EKIA_SPRINTS_IA_CORTO_PLAZO.md` §12](EKIA_SPRINTS_IA_CORTO_PLAZO.md#12-kickoff-inmediato--sprint-1-1-sep-2026)

---

*PM actualiza §12 al cerrar cada sprint. Detalle historias: doc sprints IA.*
