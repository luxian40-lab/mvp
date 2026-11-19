# Gate bloque 2 — 2026-11-19 (pre-deploy)

Rama: `slice/bloque-2-gate` rebaseada sobre `origin/main` @ `53479e81` (expediente ya en prod).  
Prod actual: `main-expediente-b4-20261119-133839` (Green).

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
| W1 RAG código | En rama; setenv **después** del deploy |
| Cero sleep / DELAY Celery | En rama |
| Redis fail-closed | Código + ops OK |
| Outbox camino real | Ops ON |
| Mit5 LLM | En rama |
| W2 medir | Código OK; falta pico |

## Tras deploy

1. Health Green + smoke Celery.  
2. Pedido explícito: `EKI_RAG_INDEX_SOLO_AI=true` en prod-final.  
3. Muestreo W2 en pico → luego W3.
