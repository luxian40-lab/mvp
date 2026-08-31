# eki — ElastiCache Redis micro + env eki-ai-workers (t3.small) vía CLI.
# Uso:
#   .\scripts\provision_eki_ai_stack.ps1
#   .\scripts\provision_eki_ai_stack.ps1 -AwsProfile admin
#   .\scripts\provision_eki_ai_stack.ps1 -SkipElasticache -RedisEndpoint xxx.cache.amazonaws.com
#
# Requiere IAM: scripts/iam/eki-elasticache-provision-policy.json (adjuntar a usuario EB)
# o ejecutar con un perfil AWS que ya tenga elasticache + ec2 SG.

param(
    [string]$Region = "us-east-2",
    [string]$VpcId = "vpc-0ceabc228a1ed992a",
    [string[]]$SubnetIds = @("subnet-0bb2dcfa021c2d25d", "subnet-0fa2a74a4e2abefea"),
    [string]$EbSecurityGroupId = "sg-09fbce3fd0cb2a913",
    [string]$SubnetGroupName = "eki-redis-subnets",
    [string]$CacheSecurityGroupName = "eki-elasticache-redis",
    [string]$ClusterId = "eki-celery-prod",
    [string]$CacheNodeType = "cache.t4g.micro",
    [string]$ProdEnv = "eki-prod-final",
    [string]$AiEnv = "eki-ai-workers",
    [string]$AwsProfile = "eb-cli",
    [string]$RedisEndpoint = "",
    [switch]$SkipElasticache,
    [switch]$SkipEbCreate,
    [switch]$SkipProdSetenv,
    [switch]$SkipDeploy,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

function AwsArgs() {
    $a = @("--region", $Region)
    if ($AwsProfile) { $a += @("--profile", $AwsProfile) }
    return $a
}

function RunAws([string[]]$CmdArgs, [string]$Label, [switch]$AllowFail) {
    $all = (AwsArgs) + $CmdArgs
    $shown = "aws " + ($all -join ' ')
    if ($DryRun) {
        Write-Host "[DRY-RUN] $shown" -ForegroundColor DarkGray
        return ""
    }
    Info $Label
    $out = & aws @all 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host $out
        if ($AllowFail) { return $null }
        Fail "AWS falló: $Label"
    }
    return $out.Trim()
}

function RunEb([string[]]$CmdArgs, [string]$Label) {
    $ebArgs = $CmdArgs + @("--region", $Region)
    if ($AwsProfile) { $ebArgs += @("--profile", $AwsProfile) }
    if ($DryRun) {
        Write-Host "[DRY-RUN] eb $($ebArgs -join ' ')" -ForegroundColor DarkGray
        return
    }
    Info $Label
    & eb @ebArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "EB falló: $Label"
    }
}

function TestElasticacheAccess() {
    if ($SkipElasticache -or $RedisEndpoint) { return $true }
    if ($DryRun) { return $true }
    $probe = & aws @((AwsArgs) + @("elasticache", "describe-cache-clusters", "--max-items", "1")) 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host $probe
        Warn @"
Sin permisos ElastiCache en el perfil '$AwsProfile'.

Opcion A - adjuntar policy (cuenta admin, una vez):
  IAM -> Users -> eki-S3-produccion -> Add permissions -> Create inline policy -> JSON:
  scripts/iam/eki-elasticache-provision-policy.json

Opcion B - otro perfil:
  .\scripts\provision_eki_ai_stack.ps1 -AwsProfile TU-PERFIL-ADMIN

Opcion C - Redis ya creado a mano:
  .\scripts\provision_eki_ai_stack.ps1 -SkipElasticache -RedisEndpoint xxx.cache.amazonaws.com
"@
        return $false
    }
    return $true
}

function EnsureSubnetGroup() {
    $existing = RunAws @(
        "elasticache", "describe-cache-subnet-groups",
        "--cache-subnet-group-name", $SubnetGroupName
    ) "Subnet group $SubnetGroupName" -AllowFail
    if ($existing -and $existing -match $SubnetGroupName) {
        Ok "Subnet group ya existe."
        return
    }
    RunAws @(
        "elasticache", "create-cache-subnet-group",
        "--cache-subnet-group-name", $SubnetGroupName,
        "--cache-subnet-group-description", "eki Celery + Django cache",
        "--subnet-ids", ($SubnetIds -join ',')
    ) "Creando subnet group"
    Ok "Subnet group creado."
}

function EnsureCacheSecurityGroup() {
    $q = RunAws @(
        "ec2", "describe-security-groups",
        "--filters", "Name=group-name,Values=$CacheSecurityGroupName", "Name=vpc-id,Values=$VpcId",
        "--query", "SecurityGroups[0].GroupId", "--output", "text"
    ) "SG ElastiCache"
    if ($q -and $q -ne "None" -and $q -match "^sg-") {
        Ok "SG cache: $q"
        return $q.Trim()
    }
    $create = RunAws @(
        "ec2", "create-security-group",
        "--group-name", $CacheSecurityGroupName,
        "--description", "eki ElastiCache Redis - solo desde EB",
        "--vpc-id", $VpcId,
        "--query", "GroupId", "--output", "text"
    ) "Creando SG ElastiCache"
    $sgId = $create.Trim()
    RunAws @(
        "ec2", "authorize-security-group-ingress",
        "--group-id", $sgId,
        "--protocol", "tcp",
        "--port", "6379",
        "--source-group", $EbSecurityGroupId
    ) "Regla 6379 desde EB SG"
    Ok "SG cache creado: $sgId"
    return $sgId
}

function EnsureRedisCluster([string]$CacheSgId) {
    $desc = RunAws @(
        "elasticache", "describe-cache-clusters",
        "--cache-cluster-id", $ClusterId,
        "--show-cache-node-info"
    ) "Cluster $ClusterId" -AllowFail
    if ($desc -and $desc -match '"CacheClusterStatus"\s*:\s*"available"') {
        Ok "Cluster Redis ya available."
        return
    }
    if ($desc -and $desc -match $ClusterId) {
        Info "Cluster existe pero no available - esperando..."
    } else {
        RunAws @(
            "elasticache", "create-cache-cluster",
            "--cache-cluster-id", $ClusterId,
            "--engine", "redis",
            "--engine-version", "7.1",
            "--cache-node-type", $CacheNodeType,
            "--num-cache-nodes", "1",
            "--cache-subnet-group-name", $SubnetGroupName,
            "--security-group-ids", $CacheSgId
        ) "Creando cluster Redis $CacheNodeType"
    }
    if (-not $DryRun) {
        Info "Esperando cluster available (5-10 min)..."
        & aws @((AwsArgs) + @("elasticache", "wait", "cache-cluster-available", "--cache-cluster-id", $ClusterId))
        if ($LASTEXITCODE -ne 0) { Fail "Timeout esperando Redis." }
    }
    Ok "Cluster Redis listo."
}

function GetRedisEndpoint() {
    if ($RedisEndpoint) { return $RedisEndpoint.Trim() }
    if ($DryRun) { return "DRY-RUN-endpoint.cache.amazonaws.com" }
    $addr = RunAws @(
        "elasticache", "describe-cache-clusters",
        "--cache-cluster-id", $ClusterId,
        "--show-cache-node-info",
        "--query", "CacheClusters[0].CacheNodes[0].Endpoint.Address",
        "--output", "text"
    ) "Endpoint Redis"
    return $addr.Trim()
}

function SetRedisEnvVars([string]$Endpoint, [string]$EnvName, [string]$ExtraVars) {
    $broker = "redis://${Endpoint}:6379/0"
    $cacheUrl = "redis://${Endpoint}:6379/1"
    $pairs = @(
        "CELERY_BROKER_URL=$broker",
        "CELERY_RESULT_BACKEND=$broker",
        "REDIS_CACHE_URL=$cacheUrl",
        "USE_LOCAL_REDIS=0"
    )
    if ($ExtraVars) { $pairs += $ExtraVars }
    RunEb @("setenv") + $pairs + @("--environment", $EnvName) "setenv Redis en $EnvName"
    Ok "Variables Redis en $EnvName."
}

function EnsureAiEnvironment([string]$Endpoint) {
    $list = (& eb list --region $Region $(if ($AwsProfile) { @("--profile", $AwsProfile) }) 2>&1 | Out-String)
    $aiExists = $list -match $AiEnv
    if ($aiExists) {
        Ok "Env $AiEnv ya existe."
        SetRedisEnvVars $Endpoint $AiEnv @("EKI_EB_ROLE=ai_workers")
        return
    }
    if ($SkipEbCreate) {
        Warn "SkipEbCreate: no se crea $AiEnv."
        return
    }
    Info "Clonando $ProdEnv -> $AiEnv (hereda DATABASE_URL, secrets, etc.)..."
    RunEb @("clone", $ProdEnv, "-n", $AiEnv, "--scale", "1", "-c", "eki-ai-workers") "eb clone"
    Info "Instance type -> t3.small..."
    if (-not $DryRun) {
        RunAws @(
            "elasticbeanstalk", "update-environment",
            "--environment-name", $AiEnv,
            "--option-settings",
            "Namespace=aws:autoscaling:launchconfiguration,OptionName=InstanceType,Value=t3.small",
            "Namespace=aws:ec2:instances,OptionName=InstanceTypes,Value=t3.small"
        ) "EB instance type t3.small"
    }
    SetRedisEnvVars $Endpoint $AiEnv @("EKI_EB_ROLE=ai_workers")
    Ok "Env $AiEnv creado/configurado."
}

# --- main ---
Info "eki AI stack - region $Region perfil $AwsProfile"
if (-not (TestElasticacheAccess)) { exit 1 }

if (-not $SkipElasticache -and -not $RedisEndpoint) {
    EnsureSubnetGroup
    $cacheSg = EnsureCacheSecurityGroup
    EnsureRedisCluster $cacheSg
}

$endpoint = GetRedisEndpoint
if (-not $endpoint) { Fail "No se obtuvo endpoint Redis." }
Ok "Redis endpoint: $endpoint"

if (-not $SkipProdSetenv) {
    SetRedisEnvVars $endpoint $ProdEnv @()
}

EnsureAiEnvironment $endpoint

if (-not $SkipDeploy) {
    RunEb @("deploy", $ProdEnv, "--label", ("redis-stack-prod-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))) "deploy $ProdEnv"
    $aiList = (& eb list --region $Region $(if ($AwsProfile) { @("--profile", $AwsProfile) }) 2>&1 | Out-String)
    if ($aiList -match $AiEnv) {
        RunEb @("deploy", $AiEnv, "--label", ("redis-stack-ai-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))) "deploy $AiEnv"
    }
}

Write-Host ""
Ok "Stack listo."
Write-Host "  Redis: redis://${endpoint}:6379/0"
Write-Host "  Verificar:"
Write-Host "    eb health $ProdEnv"
Write-Host "    eb health $AiEnv"
Write-Host "    python scripts/smoke_nat_celery.py --remote $ProdEnv"
Write-Host "  Costo delta ~USD 26-32/mes (t3.small + cache.t4g.micro)"
