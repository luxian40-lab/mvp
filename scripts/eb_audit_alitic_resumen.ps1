param([string]$Environment = 'eki-prod-final')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_eb_env_prod_bash.ps1"
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw "$PSScriptRoot\_audit_alitic_resumen.py")))
$bash = @"
$(Get-EbEnvProdBash)
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo '$pyB64' | base64 -d > /tmp/audit_alitic.py
python /tmp/audit_alitic.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Audit Alitic curso 7" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
