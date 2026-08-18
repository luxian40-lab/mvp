# Backfill cierre curso Alitic (curso 7) tras deploy cerrar_avance.
# Uso:
#   .\scripts\eb_backfill_alitic_cerrar_curso.ps1 -DryRun
#   .\scripts\eb_backfill_alitic_cerrar_curso.ps1
param(
    [string]$Environment = 'eki-prod-final',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$dry = if ($DryRun) { '1' } else { '0' }
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw "$PSScriptRoot\_backfill_alitic_cerrar_curso.py")))

$bash = @"
$(Get-EbEnvProdBash)
export DRY_RUN=$dry
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo '$pyB64' | base64 -d > /tmp/backfill_alitic_cerrar.py
python /tmp/backfill_alitic_cerrar.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Backfill cerrar curso Alitic env=$Environment dry=$DryRun" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "backfill failed" }
