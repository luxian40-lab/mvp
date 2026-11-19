# Gate bloque 2 — 2026-11-19 (ops live)

Rama: `slice/bloque-2-gate` (desde `origin/main` @ `18858ca1`, ~16 commits).  
Expediente: `feat/expediente-b4-residual` → `main` local `53479e81` (ff-only, sin push).  
Prod desplegada: `main-diploma-mock-esquinas-20261118-210303` (Green).

## Criterios

| Criterio | Resultado |
| --- | --- |
| W0 inventario colas | OK — `docs/INFORME_W0_COLAS.md` |
| W1 dueño encode | **Ops OK** — `EKI_MEDIA_ENCODE_SOLO_AI=true` en prod |
| W1 dueño RAG | Pendiente deploy bloque 2 + `EKI_RAG_INDEX_SOLO_AI` |
| Cero `time.sleep` en conversación/líneas/avisos | Código OK en rama; **falta deploy** |
| Redis sin `127.0.0.1` en prod | **Ops OK** — ElastiCache vía `CELERY_BROKER_URL`; fail-closed setenv |
| Claim/outbox camino real | **Ops ON** — `EKI_OUTBOX_ENVIO=true`; 88 ENVIADO / 0 INCIERTO |
| Mitigación 5 LLM | Código OK en rama; **falta deploy** |
| W2 medir colas | Código OK; muestra 1 live vacía — `docs/INFORME_W2_COLAS.md` |

## No hecho (pedido explícito)

- Deploy / push de `slice/bloque-2-gate` (sleeps, mit5, W2 health, RAG solo-AI).
- `eb setenv EKI_RAG_INDEX_SOLO_AI=true` **después** de ese deploy.
- Push de `main` con expediente (`53479e81`).
- Segundo muestreo W2 en pico.
- W3.

## Siguiente

1. Publicar expediente (`git push origin main`) **o** desplegar bloque 2 — por separado, nunca el mismo paquete.  
2. Tras bloque 2 en prod: setenv RAG solo-AI + muestreo W2 en pico.  
3. W3 solo con W1 RAG + W2 pico verdes.
