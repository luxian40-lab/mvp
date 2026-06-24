# Configura prueba de empleabilidad en EB (carga DB_* vía get-config).
param(
    [Parameter(Mandatory = $true)]
    [int]$ClienteId,
    [string]$Telefono = '',
    [switch]$ReemplazarAliados,
    [switch]$SimularUbicacion,
    [string]$CompletarCodigo = '',
    [double]$Lat = 4.926,
    [double]$Lng = -74.173
)
$pyArgs = @('setup_prueba_empleabilidad', "--cliente-id=$ClienteId", "--lat=$Lat", "--lng=$Lng")
if ($Telefono) { $pyArgs += "--telefono=$Telefono" }
if ($ReemplazarAliados) { $pyArgs += '--reemplazar-aliados' }
if ($SimularUbicacion) { $pyArgs += '--simular-ubicacion' }
if ($CompletarCodigo) { $pyArgs += "--completar-codigo=$CompletarCodigo" }
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
