# eki — Inst. 2 IA (`t3.small`) + ElastiCache micro

**Decisión (2026-08-31):** montar ahora ElastiCache + env `eki-ai-workers` (`t3.small`).
RDS `small` → revisar en **2 semanas** (métricas en `/admin/infra/`).

Costo delta estimado: **~USD 26–32/mes** (inst. 2 + ElastiCache; sin upgrade RDS).

---

## Arquitectura

| Componente | Rol |
|------------|-----|
| `eki-prod-final` (`t3.medium`) | Web + Celery `celery` + **beat** |
| `eki-ai-workers` (`t3.small`) | Celery `media_encode`, `rag_index`, `course_engine` |
| ElastiCache `cache.t4g.micro` | Broker Celery + cache Django compartido |
| RDS actual | Sin cambio (revisión en 2 semanas) |

VPC prod: `vpc-0ceabc228a1ed992a` · SG EB: `sg-09fbce3fd0cb2a913`

---

## Paso 1 — ElastiCache Redis (script automático)

**Recomendado — un solo comando** (tras adjuntar IAM policy, ver abajo):

```powershell
.\scripts\provision_eki_ai_stack.ps1
```

Dry-run (solo muestra comandos):

```powershell
.\scripts\provision_eki_ai_stack.ps1 -DryRun
```

### IAM (una vez)

Usuario `eki-S3-produccion` necesita permisos ElastiCache. Adjuntar en IAM:

`scripts/iam/eki-elasticache-provision-policy.json`

O ejecutar con perfil admin:

```powershell
.\scripts\provision_eki_ai_stack.ps1 -AwsProfile TU-PERFIL-ADMIN
```

### Manual (consola AWS) — solo si el script falla por permisos

1. **ElastiCache** → Redis → Create
2. Nombre: `eki-celery-prod`
3. Engine: Redis 7.x · Node: **cache.t4g.micro** · 1 nodo
4. VPC: `vpc-0ceabc228a1ed992a`
5. Subnet group: incluir al menos 2 subnets (`subnet-0bb2dcfa021c2d25d`, `subnet-0fa2a74a4e2abefea`)
6. Security group: crear `eki-elasticache-sg` — inbound **6379** desde `sg-09fbce3fd0cb2a913`
7. Sin TLS al inicio (más simple): endpoint `xxx.cache.amazonaws.com:6379`

Anotar endpoint: `REDIS_HOST=eki-celery-prod.xxxxx.cache.amazonaws.com`

---

## Paso 2 — Variables en `eki-prod-final` (EB → Configuration → Software)

```
CELERY_BROKER_URL=redis://ENDPOINT:6379/0
CELERY_RESULT_BACKEND=redis://ENDPOINT:6379/0
REDIS_CACHE_URL=redis://ENDPOINT:6379/1
USE_LOCAL_REDIS=0
```

Apply → **no redeploy obligatorio** pero recomendado tras crear inst. 2.

Verificar:

```bash
eb ssh eki-prod-final --command "source /var/app/current/.venv/bin/activate && cd /var/app/current && python manage.py celery_redis_ping"
python scripts/smoke_nat_celery.py --remote eki-prod-final
```

---

## Paso 3 — Crear env `eki-ai-workers`

El script `provision_eki_ai_stack.ps1` hace **clone de prod** + `t3.small` + deploy.

Manual alternativo:

```powershell
eb create eki-ai-workers `
  --instance-type t3.small `
  --single-instance `
  --envvars "EKI_EB_ROLE=ai_workers,USE_LOCAL_REDIS=0,CELERY_BROKER_URL=redis://ENDPOINT:6379/0,CELERY_RESULT_BACKEND=redis://ENDPOINT:6379/0,REDIS_CACHE_URL=redis://ENDPOINT:6379/1" `
  --keyname eki-ssh-2026
```

El hook `.platform/hooks/prebuild/01_eki_procfile_role.sh` copia `Procfile.ai` → `Procfile`.

Deploy código:

```powershell
eb deploy eki-ai-workers --label ai-workers-initial
```

---

## Paso 4 — Smoke

1. Module Builder → subir MP4 → badge verde en ≤3 min (`media_encode` en inst. 2).
2. Indexar doc Nat → cola `rag_index` en inst. 2.
3. `python manage.py course_engine_generate_video --micro-realista ...` (local o futuro job Celery).

---

## Paso 5 — Ajuste prod (opcional tras 48 h estables)

En `eki-prod-final`, el `worker_rag` puede apagarse si todo RAG va a inst. 2 (quitar línea del Procfile web o escalar procesos). **Beat siempre solo en prod-final.**

---

## Rollback

- Quitar `CELERY_BROKER_URL` + `USE_LOCAL_REDIS=1` → Redis local en caja.
- Terminar env `eki-ai-workers` si no se usa.
- Eliminar ElastiCache cluster (último paso).

---

## RDS small (semana +2)

Revisar en admin Infra / CloudWatch RDS:

- CPU promedio > 60% sostenido
- `DatabaseConnections` cerca del límite
- Timeouts en logs Django

Si no hay dolor → **mantener micro**.
