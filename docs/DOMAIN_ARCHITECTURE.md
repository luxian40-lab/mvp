# Arquitectura de dominios eki — bounded contexts

**Decisión CTO (mayo 2026):** no microservicios aún. Separación lógica en apps Django con imports unidireccionales.

## Mapa de dominios

| Dominio | App Django | Responsabilidad | Código legacy (transitorio) |
|---------|------------|-----------------|------------------------------|
| Core | `core` | Identidad, Estudiante, Cliente, webhook orquestador Twilio | `core/views.py`, `core/models.py` |
| Educación | `learning` | Cursos, módulos, progreso, certificados, drip | `core/helpers_examenes`, drip |
| IA pedagógica | `agents_edu` | Darío, Claudia, tutor RAG educativo | `core/agentes_ia.py` |
| IA comercial | `agents_commercial` | Nati, RAG comercial, HITL | `core/nati.py`, `knowledge_studio` |
| Analytics | `analytics` | Dashboards, métricas, exports Excel | `core/metricas_empresa`, `analytics/exports.py` |
| Integraciones | `integrations` | API LXP / Angular, CORS | `core/api.py` → `integrations/urls.py` |
| Automations | `core` (fase 2) | Celery, campañas, envíos | `core/tasks.py` |
| GEI / Form | `formulario` | Encuestas, balance GEI | `formulario/` |

## Regla de imports

```
formulario  → core.models
learning    → core.models
agents_*    → core.models
analytics   → core.models, core.metricas_empresa
integrations→ core.api (fachada)
core        → NO importa learning | agents_* | analytics | integrations
```

## Fases de migración

1. **Hecho:** apps registradas + registry + exports en `analytics/`
2. **Siguiente:** mover `agentes_ia.py` → `agents_edu/`, `nati.py` → `agents_commercial/`
3. **Luego:** modelos de curso/progreso → `learning/` (migraciones Django)

Ver también `core/domains/registry.py` y Manual v2.0 en instructivo.
