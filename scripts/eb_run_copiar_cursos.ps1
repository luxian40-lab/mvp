# Ejecuta copiar_cursos en EB (carga DB_* vía get-config).
param(
    [int]$OrigenId = 0,
    [string]$OrigenNombre = '',
    [switch]$Reset
)
$pyArgs = @('copiar_cursos')
if ($Reset) { $pyArgs += '--reset' }
if ($OrigenId -gt 0) { $pyArgs += "--origen-id=$OrigenId" }
elseif ($OrigenNombre) { $pyArgs += "--origen-nombre=$OrigenNombre" }
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate && python manage.py $($pyArgs -join ' ')
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
