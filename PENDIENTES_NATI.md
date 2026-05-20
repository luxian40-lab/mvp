# Pendientes — referencias "Nati" no renombradas (compatibilidad)

Estos identificadores se mantienen a propósito; no son labels visibles al usuario admin.

| Ruta | Línea / contexto | Motivo |
|------|------------------|--------|
| `core/nati.py` | Módulo y aliases `NATI_SYSTEM_PROMPT_BASE`, `NATI_DIAGNOSTICO_PROMPT` | Compatibilidad de imports legacy |
| `core/models.py` | `Cliente.nombre_bot` default `'Nati'` | Sin migración de datos; override por cliente en BD |
| `core/models.py` | Clase `MetaMetricaNati` | Nombre de modelo/tabla en BD |
| `core/metricas_empresa.py` | `calcular_metricas_nati()` | API interna `tipo=metricas_nati` |
| `core/domains/dashboard.py` | Keys `metricas_nati`, tab comercial | URLs y contrato API existente |
| `mvp_project/settings.py` | Comentarios / flags con prefijo NATI si aplica | Config heredada |
| `core/migrations/*.py` | Textos históricos en migraciones | No editar migraciones aplicadas |

Registros con `nombre_bot="Nati"` en producción siguen mostrando "Nati" al productor (intencional).
