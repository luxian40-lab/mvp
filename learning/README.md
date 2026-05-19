# Learning (bounded context)

Migración gradual desde `core/`:

| Módulo legacy | Destino futuro |
|---------------|----------------|
| `core.helpers_examenes`, drip, módulos | `learning/` |
| `core.domains.learning.checkpoints` | facade transitorio en `core/` |

**Regla:** `learning` → importa `core.models`; `core` no importa `learning` (unidireccional).
