# Seed Cenipalma en prod: org + 2 WA + 10x clases + grupos + inscripción.
# Uso: .\scripts\eb_setup_cenipalma_piloto.ps1
#      .\scripts\eb_setup_cenipalma_piloto.ps1 -AsignarCliente
param(
    [string]$Telefono = '3026480629',
    [string]$Environment = 'eki-prod-final',
    [switch]$AsignarCliente
)

$ErrorActionPreference = 'Stop'
$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }
$flag = if ($AsignarCliente) { ' --asignar-cliente' } else { '' }

$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
python manage.py migrate core 0130 --noinput || python manage.py migrate --noinput
python manage.py setup_cenipalma_piloto --telefono $digits$flag
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Seed Cenipalma en $Environment tel=$digits asignar=$AsignarCliente" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "eb ssh seed failed" }
Write-Host "[OK] Seed Cenipalma listo" -ForegroundColor Green
