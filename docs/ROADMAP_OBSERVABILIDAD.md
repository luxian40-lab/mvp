# Hoja de ruta colaborativa — Observabilidad eki

Documento para avanzar **juntos** en arquitectura seria. Cada parte tiene entregables, archivos clave y criterio de “listo”.

---

## ✅ Hecho hoy (sesión actual)

| Parte | Qué | Rutas / archivos |
|-------|-----|-------------------|
| **0** | Dominios (`core/domains/`) | Registry + facades learning/analytics |
| **1** | 4 dashboards + redirects legacy | `/admin/dashboard/?tab=executive\|learning\|ai_ops\|commercial` |
| **Bug** | M1 solo en modo Auto (no en override Sí) | `core/helpers_examenes.py` |
| **2A** | EventoIA + checkpoint auditable | Ver abajo |

---

## Parte 2A — Event System (implementado)

### Rutas admin

| Ruta | Nombre | Para qué |
|------|--------|----------|
| `/admin/ai-ops/eventos/` | `ai_ops_eventos` | Listado filtrable (tipo, trace, estudiante) |
| `/admin/ai-ops/replay/<uuid>/` | `ai_ops_replay` | Timeline de un trace (conversation replay v1) |
| `/admin/ai-ops/api/eventos/` | `api_eventos_ia` | JSON para integraciones |
| `/admin/dashboard/?tab=ai_ops` | — | Tab con últimos 20 eventos + enlace |

### Modelo `EventoIA`

Tipos activos:

- `modulo_completado` — signal al crear `ModuloCompletado`
- `checkpoint_evaluado` — cada vez que se decide reto IA (con **regla explícita**)
- `ia_agent_triggered` — agentes educativos + Nati
- `rag_query_executed` — consulta RAG comercial

### Checkpoint — tres reglas del admin (precedencia)

```
curso sin IA → NO
facilitador_checkpoint = NO → NO  (aunque sea M3)
facilitador_checkpoint = SÍ → SÍ  (aunque sea M1)
facilitador_checkpoint = AUTO → regla numérica (M3, último≥5, 6/9/12…)
modulo_ya_completado → anula reto (anti-loop)
```

Función auditable: `evaluar_checkpoint_reto_ia()` → `CheckpointDecision.regla_aplicada`

Valores de `regla_aplicada`:

| Valor | Significado |
|-------|-------------|
| `override_si` | Admin puso **Sí** en el módulo |
| `override_no` | Admin puso **No** |
| `auto_regla_m3` | Auto → módulo 3 |
| `auto_regla_ultimo` | Auto → último módulo (curso ≥5) |
| `auto_regla_intermedio_post5` | Auto → 6, 9, 12… |
| `auto_sin_match` | Auto → no aplica regla |
| `anulado_modulo_ya_completado` | Anti-loop post-reto |
| `curso_sin_ia` | Curso con agentes desactivados |

### Archivos clave

```
core/models.py              → EventoIA
core/migrations/0092_*      → migración
core/eventos_ia.py          → emit_* + trace_id
core/helpers_examenes.py    → evaluar_checkpoint_reto_ia
core/signals_eventos_ia.py  → ModuloCompletado
core/views_eventos_ia.py    → vistas admin
core/templates/admin/ai_ops_*.html
```

### Cómo probar juntos (5 min)

1. Admin → Curso → Módulo 1 → Checkpoint = **Sí** → estudiante cierra M1 → evento `override_si` + reto SÍ.
2. Módulo 1 → Checkpoint = **Auto** → mismo flujo → `auto_sin_match` + reto NO.
3. Módulo 3 → Checkpoint = **No** → `override_no` + reto NO.
4. Consulta a Nati → eventos `rag_query_executed` + `ia_agent_triggered`.
5. Abrir replay desde trace en `/admin/ai-ops/eventos/`.

---

## Parte 2B — Completado (event-driven parcial)

| Evento | Estado |
|--------|--------|
| `webhook_recibido` | ✅ WhatsApp edu + Nati |
| `intent_detectado` | ✅ Flujo principal webhook |
| `mensaje_enviado` | ✅ Twilio send + Nati |
| Chunks RAG en metadata | ✅ fuente, cliente_id, similitud |
| Feature registry | ✅ `core/ai_capabilities.py` |
| Admin EventoIA | ✅ Solo lectura en Django admin |

### Replay v2 (cadena objetivo)

```
webhook_recibido → intent_detectado → checkpoint_evaluado → rag_query_executed
→ ia_agent_triggered → mensaje_enviado
```

Visible en `/admin/ai-ops/replay/<uuid>/`.

---

## Parte 3 — Nati contexto agronómico (pendiente — 60 días)

- Modelo `ContextoAgroSession` (cultivo, etapa, región, problema)
- Extracción NLU ligera + prompt obligatorio
- Golden dataset + eval automática

---

## Parte 4 — Knowledge Studio + HITL (90 días)

- `ConversacionRAGCandidata` → revisión agrónomo → publicar chunk
- UI Biblioteca / Etiquetado / Salud RAG

---

## Parte 5 — Conversation Replay v2

Replay completo cuando existan eventos:

```
Webhook → Intent → Checkpoint → RAG → Prompt → IA → Enviado
```

UI ya iniciada en `/admin/ai-ops/replay/<uuid>/`.

---

## Regla de equipo

1. Código nuevo emite eventos (`core/eventos_ia`).
2. Decisiones de negocio auditable (`evaluar_*`, no solo bool).
3. No reescribir webhook monolítico — extraer servicios gradualmente.
4. Commits/deploy cuando **tú** digas “listo para prod”.

---

## Tests

```bash
python manage.py test core.tests_eventos_ia core.tests_agentes core.tests_domains_dashboard -v 2
```

---

*Última actualización: mayo 2026 — Parte 2A*
