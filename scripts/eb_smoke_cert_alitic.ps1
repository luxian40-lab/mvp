# Smoke certificado Alitic: plantilla HX → OK → diploma PNG real (prod).
# Uso:
#   .\scripts\eb_smoke_cert_alitic.ps1
#   .\scripts\eb_smoke_cert_alitic.ps1 -SimularOk
param(
    [string]$Telefono = '3026480629',
    [string]$Environment = 'eki-prod-final',
    [string]$ContentSid = 'HX6b8ed985eee273c3850452c03608cfa9',
    [switch]$SimularOk
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }
$simOk = if ($SimularOk) { '1' } else { '0' }

$py = Get-Content -Raw "$PSScriptRoot\_qa_smoke_cert_alitic.py"
$py = $py -replace 'PHONE_SUFFIX = "3026480629"', "PHONE_SUFFIX = `"$($digits.Substring($digits.Length - 10))`""
$py = $py -replace 'CONTENT_SID = "HX6b8ed985eee273c3850452c03608cfa9"', "CONTENT_SID = `"$ContentSid`""

$bash = @"
$(Get-EbEnvProdBash)
export QA_SIMULAR_OK=$simOk
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
cat > /tmp/qa_smoke_cert_alitic.py << 'PYEOF'
$($py -replace "'", "'\\''")
PYEOF
python /tmp/qa_smoke_cert_alitic.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Smoke cert Alitic en $Environment tel=$digits simular_ok=$simOk" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "smoke cert Alitic failed" }
