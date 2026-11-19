# Gate bloque 2 — 2026-11-19 (actualizado)

Rama: `slice/bloque-2-gate` (desde `origin/main` @ `18858ca1`).  
Expediente: `feat/expediente-b4-residual` (aparte; ver `docs/INFORME_EXPEDIENTE_MERGE.md`).

## Criterios

| Criterio | Resultado |
| --- | --- |
| W0 inventario colas | OK — `docs/INFORME_W0_COLAS.md` |
| W1 dueños encode/RAG | OK decisión — `docs/INFORME_W1_DUENOS.md`; flags **off** hasta setenv |
| Cero `time.sleep` en conversación/líneas/avisos | OK |
| Redis sin `127.0.0.1` en prod | Código OK (fail-closed default on); **ops:** `docs/OPS_REDIS_URL_EB.md` |
| Claim/outbox camino real | OK; `EKI_OUTBOX_ENVIO` off |
| Mitigación 5 LLM | OK (Nat, aula, `completar_chat`) |
| W2 medir colas | Código OK — `docs/INFORME_W2_COLAS.md`; falta tabla live de un día laborable |

## No hecho (ops / pedido explícito)

- `REDIS_URL` + setenv W1 (`EKI_MEDIA_ENCODE_SOLO_AI`, `EKI_RAG_INDEX_SOLO_AI`)
- Prender `EKI_OUTBOX_ENVIO` / campañas v2
- Push / deploy
- Merge expediente a `origin/main` (ff-only local cuando se pida publicar)

## Siguiente

1. Ops: Redis externo + (opcional) setenv W1.  
2. Rellenar tabla W2 en un día laborable.  
3. Merge/push expediente y/o bloque 2 con pedido explícito.  
4. W3 solo con W1+W2 verdes.
