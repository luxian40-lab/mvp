# Gate bloque 2 — 2026-11-19 (desplegado)

**Cierre código:** 2026-11-23 — bloque 2 **CERRADO** a nivel código en `origin/main` (auditoría post-merge). Pendiente ops: únicamente el pico W2 de carga en día laborable (`docs/INFORME_W2_COLAS.md`); no bloquea el cierre de código.

Label: `main-bloque-2-gate-20261119-141312` (`759f4905`).  
Rollback: `main-expediente-b4-20261119-133839`.  
Prod + AI: Green; health 200; smoke Celery OK; W2 colas 0; outbox 0 INCIERTO/ERROR.  
`EKI_RAG_INDEX_SOLO_AI` unset: setenv chocó con el tope 4096 de EB. Prod no indexa igual (`EKI_ROLE=web`). Ver `docs/INFORME_W3_DECISION.md`.

## Riesgos al desplegar (revisión)

| Riesgo | Severidad | Mitigación / evidencia |
| --- | --- | --- |
| Ritmo: sin `time.sleep`; DELAY → Celery | Media (UX) | Smoke `listo` / turno Meta tras deploy |
| `salida_turno` → Sender/outbox | Media | Outbox ya ON; 0 INCIERTO pre-deploy |
| Redis fail-closed default on | Baja | Broker ElastiCache + setenv ya en ambas cajas |
| Mit5 LLM fail-closed si Redis cae | Baja | Solo bajo fallo de Redis |
| `EKI_RAG_INDEX_SOLO_AI` | Baja ahora | Default **off**; prod ya duerme rag con `EKI_ROLE=web`; AI tiene `rag@` |
| Mezclar con expediente | — | Expediente ya desplegado; rebase limpio |

## Criterios

| Criterio | Resultado |
| --- | --- |
| W0 inventario colas | OK |
| W1 encode | Ops OK (`EKI_MEDIA_ENCODE_SOLO_AI=true`) |
| W1 RAG | Ops OK por `EKI_ROLE=web` + `rag@` en AI; setenv del flag no cupo (4096) |
| Cero sleep / DELAY Celery | **OK en `origin/main`** (auditoría 2026-11-23) |
| Redis fail-closed | Código + ops OK |
| Outbox camino real | Ops ON (`EKI_OUTBOX_ENVIO`) |
| Mit5 LLM | OK en main |
| W2 medir | Código OK; noche 2026-11-19 LLEN 0 (no es pico) — **pico laborable pendiente ops** |
| W3 decisión | Cerrado: no crecer (`docs/INFORME_W3_DECISION.md`) |

## Tras deploy

1. Health Green + smoke Celery. **Hecho.**  
2. W3 cerrado en decisión: no crecer (`docs/INFORME_W3_DECISION.md`). **Hecho.**  
3. Pico laborable de W2 sigue útil antes de separar `masivo`. **Pendiente ops** (no gate de código).