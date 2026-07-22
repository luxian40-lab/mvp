# Umbrales detallados: S3, RDS, Redis, EB, Chroma (eki prod)

Números baseline ~22 jul 2026 · región **us-east-2**.  
Panel en vivo: **Admin → nav superior → Infra** (`/admin/infra/`).

Leyenda de `action_type` en el panel:

| Tipo | Significa |
|------|-----------|
| `NO_HACER_NADA` | Hoy no gastes ni toques |
| `CAMBIAR_INSTANCIA` | Subir clase RDS o tamaño EC2 |
| `ELASTICACHE` | Sacar Redis de la caja EB |
| `SOLO_DISCO` | Más GB en RDS (o autoscaling) |
| `MULTI_AZ` / `READ_REPLICA` | HA o lecturas separadas |
| `LIFECYCLE` / `CLOUDFRONT` | Optimizar S3 (no “upgrade de instancia”) |
| `EFS` | Disco compartido para Chroma |
| `ESCALAR_A_2_INSTANCIAS` | EB ASG≥2 **y** ElastiCache el mismo día |
| `REINICIAR_LOCAL` | Redis local caído |

---

## S3 — `eki-produccion`

| Dato | Valor |
|------|--------|
| Uso | **~1.7–1.8 GB** |
| ¿Instancia que subir? | **No existe** — S3 escala solo |
| Hoy | **NO_HACER_NADA** |

**Actuar con LIFECYCLE** si el costo sube o hay basura histórica.  
**Actuar con CLOUDFRONT** si hay descargas masivas concurrentes.

---

## RDS — `eki-database`

| Dato | Valor |
|------|--------|
| Clase | **db.t4g.micro** |
| Disco | **20 GB** (autoscaling max **1000 GB**) |
| Uso | **~1.7 GB** · CPU ~**3–4%** avg |
| Multi-AZ | No |
| Hoy | **NO_HACER_NADA** / no cambiar instancia |

### Orden de crecimiento

1. **CAMBIAR_INSTANCIA** → `db.t4g.small` si CPU pico sostenida >60–70% o timeouts  
2. **SOLO_DISCO** si se llena el volumen sin CPU alta  
3. **MULTI_AZ** solo por SLA de negocio (~2× costo)  
4. **READ_REPLICA** solo si analytics satura lecturas  

---

## Redis

| Hoy | Redis **local** en EB |
| ElastiCache | Solo con umbrales (2+ instancias, colas que no pueden morir, etc.) |
| Costo ElastiCache | ~**US$10–12/mes** `cache.t4g.micro` |

Ver `docs/UMBRAL_ELASTICACHE.md` + `docs/RUNBOOK_REDIS_CHROMA.md`.

---

## Elastic Beanstalk

| Hoy | 1 instancia · OK |
| Subir EC2 | Si CPU/RAM de la **caja** (no confundir con RDS) |
| 2+ instancias | **Obliga ELASTICACHE el mismo día** |

---

## Chroma

| Hoy | `/var/app/chroma_data` |
| EFS | Solo si un replace de EC2 no puede obligarte a reindexar |

---

## Cómo usar el panel

1. Nav superior **Infra**  
2. Mira el banner verde/ámbar/rojo  
3. En cada bloque: veredicto + tabla “current” + acciones con **Cuándo / Specs / Costo / Cómo**  
4. CPU histórica: CloudWatch (el panel no la pollea cada 30s a propósito, para no abusar de la API AWS)
