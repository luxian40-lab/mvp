# Provision eki-ai-workers (t3.small) + guía ElastiCache
# Requiere: eb CLI, AWS profile eb-cli, ENDPOINT Redis ya creado en consola.
param(
    [string]$Environment = "eki-ai-workers",
    [string]$RedisEndpoint = "",
    [switch]$CreateOnly,
    [switch]$SkipCreate
)

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }

if (-not $RedisEndpoint) {
    $RedisEndpoint = $env:EKI_REDIS_ENDPOINT
}

if (-not $RedisEndpoint) {
    Warn "Falta endpoint ElastiCache."
    Write-Host @"

Crear en AWS Console (cuenta con permisos elasticache):
  - Redis cache.t4g.micro, VPC vpc-0ceabc228a1ed992a
  - SG: puerto 6379 desde sg-09fbce3fd0cb2a913
  - Ver docs/EKI_AI_WORKERS_SETUP.md

Luego re-ejecutar:
  `$env:EKI_REDIS_ENDPOINT='xxx.cache.amazonaws.com'
  .\scripts\provision_eki_ai_workers.ps1

"@ -ForegroundColor Yellow
    exit 1
}

$broker = "redis://${RedisEndpoint}:6379/0"
$cache = "redis://${RedisEndpoint}:6379/1"
$envVars = "EKI_EB_ROLE=ai_workers,USE_LOCAL_REDIS=0,CELERY_BROKER_URL=$broker,CELERY_RESULT_BACKEND=$broker,REDIS_CACHE_URL=$cache"

Info "Redis broker: $broker"

if (-not $SkipCreate) {
    $exists = eb list 2>$null | Select-String -Pattern $Environment
    if ($exists) {
        Ok "Env $Environment ya existe — saltando create."
    } else {
        Info "Creando EB env $Environment (t3.small, single instance)..."
        eb create $Environment `
            --instance-type t3.small `
            --single-instance `
            --envvars $envVars `
            --keyname eki-ssh-2026 `
            --region us-east-2
        if ($LASTEXITCODE -ne 0) {
            throw "eb create falló"
        }
        Ok "Env $Environment creado."
    }
}

if ($CreateOnly) {
    exit 0
}

Info "Deploy código a $Environment..."
$label = "ai-workers-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
eb deploy $Environment --label $label --region us-east-2
if ($LASTEXITCODE -ne 0) {
    throw "eb deploy falló"
}

Ok "Listo. Verificar:"
Write-Host "  eb health $Environment"
Write-Host "  eb ssh $Environment --command 'ps aux | grep celery'"
Write-Host ""
Warn "Actualizar también eki-prod-final con las mismas vars Redis (paso 2 del runbook)."
