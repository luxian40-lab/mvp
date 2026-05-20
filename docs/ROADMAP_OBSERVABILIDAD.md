# Hoja de ruta colaborativa — Observabilidad eki



Documento para avanzar **juntos** en arquitectura seria. Cada parte tiene entregables, archivos clave y criterio de “listo”.



---



## ✅ Hecho (mayo 2026)



| Parte | Qué | Rutas / archivos |

|-------|-----|-------------------|

| **0** | Dominios (`core/domains/`) | Registry + facades learning/analytics |

| **1** | 4 dashboards + redirects legacy | `/admin/dashboard/?tab=executive\|learning\|ai_ops\|commercial` |

| **Bug** | M1 solo en modo Auto (no en override Sí) | `core/helpers_examenes.py` |

| **2A** | EventoIA + checkpoint auditable | Ver abajo |

| **2B** | Event-driven parcial + feature registry | `core/ai_capabilities.py` |

| **3** | Contexto agronómico Nat | `ContextoAgroSession`, `core/contexto_agro.py` |

| **4** | Knowledge Studio + HITL | `/admin/knowledge-studio/`, `core/knowledge_studio.py` |



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

- `ia_agent_triggered` — agentes educativos + Nat

- `rag_query_executed` — consulta RAG comercial

- `webhook_recibido`, `intent_detectado`, `mensaje_enviado`



### Checkpoint — tres reglas del admin (precedencia)



```

curso sin IA → NO

facilitador_checkpoint = NO → NO  (aunque sea M3)

facilitador_checkpoint = SÍ → SÍ  (aunque sea M1)

facilitador_checkpoint = AUTO → regla numérica (M3, último≥5, 6/9/12…)

modulo_ya_completado → anula reto (anti-loop)

```



Función auditable: `evaluar_checkpoint_reto_ia()` → `CheckpointDecision.regla_aplicada`



---



## Parte 3 — Nat contexto agronómico (implementado)



### Modelo `ContextoAgroSession`



OneToOne con `SesionComercial`. Campos: cultivo, etapa, región, municipio, clima, problema, notas, metadata.



### Servicio `core/contexto_agro.py`



- `extraer_campos_desde_mensaje()` — NLU rule-based (extensible a LLM)

- `actualizar_contexto_desde_mensaje()` — fusiona sin sobrescribir campos llenos

- `formatear_bloque_contexto_para_prompt()` — bloque inyectado en prompt Nat



### Integración



- Webhook bot comercial: actualiza contexto tras cada mensaje

- `_bot_comercial_respuesta_catalogo`: recibe `bloque_contexto_agro`

- Feature flag: `Nat_structured_context`



### Migración



`core/migrations/0093_contexto_agro_hitl.py`



---



## Parte 4 — Knowledge Studio + HITL (implementado)



### Modelo `ConversacionRAGCandidata`



Estados: pendiente → aprobada / rechazada / publicada.



### Rutas



| Ruta | Para qué |

|------|----------|

| `/admin/knowledge-studio/` | Panel: cola HITL, biblioteca, salud RAG |

| `/admin/knowledge-studio/revisar/<id>/` | POST aprobar / rechazar / publicar |



### Servicio `core/knowledge_studio.py`



- `crear_candidata_hitl()` — auto tras respuesta Nat técnica

- `revisar_candidata()` / `publicar_candidata_en_rag()` — indexa vía `rag_comercial_manager`

- `calcular_salud_rag()` — métricas para UI



### Feature flag



`hitl_rag_publish`



---



## Parte 5 — Conversation Replay v2 (pendiente largo plazo)



Replay completo cuando existan todos los eventos en cadena:



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

python manage.py test core.tests_eventos_ia core.tests_agentes core.tests_domains_dashboard core.tests_contexto_agro core.tests_knowledge_studio -v 2

```



---



*Última actualización: 19 mayo 2026 — Partes 3 y 4 + Manual v2.0*

