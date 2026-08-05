# Sube wallpaper Cenipalma reforzado a S3 y lo asigna al Cliente.
# Uso: .\scripts\eb_set_cenipalma_wallpaper.ps1
param(
    [string]$Environment = 'eki-prod-final',
    [string]$Fixture = 'scripts/fixtures/cenipalma-aprende-wallpaper.png'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$path = Join-Path $root $Fixture
if (-not (Test-Path $path)) { throw "Missing $path" }
$bytes = [IO.File]::ReadAllBytes($path)
$b64img = [Convert]::ToBase64String($bytes)
Write-Host "[INFO] fixture $($bytes.Length) bytes" -ForegroundColor Cyan

$py = @"
import base64, os, django
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Cliente

raw = base64.b64decode('''$b64img''')
assert len(raw) > 1000, 'image too small'
cli = Cliente.objects.filter(nombre='Cenipalma').first()
assert cli, 'FAIL Cenipalma'
now = timezone.now()
key = f'portal/wallpapers/{now:%Y/%m}/cliente_{cli.id}_{now:%Y%m%d%H%M%S}_cenipalma_aprende.png'
saved = default_storage.save(key, ContentFile(raw, name='cenipalma_aprende.png'))
try:
    url = default_storage.url(saved)
except Exception:
    url = f'https://eki-produccion.s3.us-east-2.amazonaws.com/{saved}'
if url.startswith('//'):
    url = 'https:' + url
cli.wallpaper_aula_url = url
cli.save(update_fields=['wallpaper_aula_url'])
print('wallpaper_url', cli.wallpaper_aula_url)
print('QA_PASS wallpaper_set')
"@

$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "`$key=`"`$(`$GC environment -k `$key 2>/dev/null)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo $pyB64 | base64 -d > /tmp/set_cenipalma_wallpaper.py
python /tmp/set_cenipalma_wallpaper.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Set Cenipalma wallpaper en $Environment" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "wallpaper set failed" }
