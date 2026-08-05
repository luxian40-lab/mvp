# Actualiza wallpaper_aula_url de Cenipalma a una URL S3 ya subida.
param(
    [string]$Environment = 'eki-prod-final',
    [string]$Url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/portal/wallpapers/2026/08/cliente_10_cenipalma_aprende_v2.jpg'
)

$ErrorActionPreference = 'Stop'
$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()
from core.models import Cliente
cli = Cliente.objects.get(nombre='Cenipalma')
cli.wallpaper_aula_url = '''$Url'''
cli.save(update_fields=['wallpaper_aula_url'])
print('ok', cli.id, cli.wallpaper_aula_url)
"@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key 2>/dev/null)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo $pyB64 | base64 -d > /tmp/set_wp_url.py
python /tmp/set_wp_url.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw 'set url failed' }
