# Runbook: Redis gestionado (ElastiCache) + Chroma persistente

## Objetivo

Sacar Redis y Chroma del disco/proceso efímero de la instancia EB.

**Costo:** desplegar solo el código (sin crear ElastiCache/EFS) **no sube la factura**.
ElastiCache `cache.t4g.micro` ≈ **US$10–12/mes**. EFS pequeño (Chroma) suele ser **pocos dólares/mes**.
Hasta que no crees esos recursos y pongas las env vars, todo sigue en Redis local + `/var/app/chroma_data`.

Hoy:
- Redis local en la caja (`.ebextensions/03_redis.config`)
- Chroma en `/var/app/chroma_data` (sobrevive deploys, **no** sobrevive si AWS reemplaza la instancia)

La app ya acepta broker externo y `CHROMA_DB_DIR` configurable.

---

## 1) Redis → ElastiCache (recomendado primero)

### En AWS (us-east-2, misma VPC que `eki-prod-final`)

1. Crear **ElastiCache Redis** (cache.t4g.micro o superior).
2. Security group: permitir **6379** desde el SG de las instancias EB.
3. Sin TLS al inicio (más simple): endpoint `xxx.cache.amazonaws.com:6379`.
4. Con TLS: usar `rediss://` y, si el cert falla en la instancia, `CELERY_BROKER_SSL_CERT_REQS=none` solo mientras se ajusta.

### Variables en EB (`eki-prod-final` → Configuration → Software)

```
CELERY_BROKER_URL=redis://TU-ENDPOINT:6379/0
CELERY_RESULT_BACKEND=redis://TU-ENDPOINT:6379/0
USE_LOCAL_REDIS=0
```

Alias opcional: `REDIS_URL` (si no hay `CELERY_BROKER_URL`).

### Verificar

```bash
eb ssh eki-prod-final
# con env de producción:
python manage.py diagnostico_infra --ping
# (o celery_redis_ping si existe)
```

Workers/beat del Procfile deben seguir vivos; colas `celery` y `rag_index` deben aceptar tareas.

### Rollback

Quitar `CELERY_BROKER_URL` / poner `USE_LOCAL_REDIS=1` y redeploy (vuelve Redis local).

---

## 2) Chroma → ruta persistente (EFS)

### Opción A — EFS (mejor si la instancia puede reemplazarse)

1. Crear **EFS** en la misma VPC/subnets que EB.
2. Mount targets + SG: NFS 2049 desde SG de EB.
3. Montar en la instancia (manual o `.ebextensions` propio) en `/mnt/efs`.
4. En EB:

```
CHROMA_DB_DIR=/mnt/efs/chroma_data
```

5. Redeploy (el hook crea el directorio y ajusta owner `webapp`).

**Nota:** con varias instancias EB escribiendo el mismo árbol Chroma puede haber locks.
Mientras haya **1 instancia** (o un solo writer RAG), EFS está bien. Multi-instance writer → migrar a vector store remoto más adelante.

### Opción B — quedarse en `/var/app/chroma_data`

Sigue siendo el default. Mejor que `/var/app/current`, pero se pierde si AWS **reemplaza** el EC2. Hacer snapshot/backup periódico del directorio si no hay EFS aún.

---

## 3) Checklist post-cambio

- [ ] `celery_redis_ping` OK
- [ ] Encolar indexación biblioteca Nat de prueba
- [ ] Campaña programada / drip no rompe (beat)
- [ ] Consulta Nati sigue trayendo RAG del cliente
- [ ] `USE_LOCAL_REDIS=0` y Redis local no es crítico

---

## 4) Qué NO hacer todavía

- No partir microservicios.
- No poner Chroma multi-writer en EFS con ASG>1 sin diseño.
- No borrar el fallback local hasta confirmar ElastiCache estable 48h.
