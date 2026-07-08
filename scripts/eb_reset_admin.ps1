# Restablece acceso al admin Django en EB (eki-prod-final).
# No depende de una versión nueva desplegada: usa Django shell en el servidor.
#
# Uso:
#   .\scripts\eb_reset_admin.ps1 -List
#   .\scripts\eb_reset_admin.ps1 -Username admin -Password "MiClaveSegura2026!"
param(
    [string]$Environment = "eki-prod-final",
    [string]$Username = "admin",
    [string]$Password = "",
    [switch]$List
)

$ErrorActionPreference = "Stop"

if ($List) {
    $py = @"
from django.contrib.auth.models import User
print('=== USUARIOS CON ACCESO AL ADMIN ===')
qs = User.objects.filter(is_staff=True).order_by('username')
if not qs.exists():
    print('(ninguno)')
for u in qs:
    flags = []
    if u.is_superuser:
        flags.append('superuser')
    if not u.is_active:
        flags.append('INACTIVO')
    extra = f" ({', '.join(flags)})" if flags else ''
    print(f'{u.username} | {u.email}{extra}')
"@
} else {
    if (-not $Password) {
        Write-Host "[ERROR] Indique -Password con la contraseña nueva." -ForegroundColor Red
        Write-Host 'Ejemplo: .\scripts\eb_reset_admin.ps1 -Password "Eki@Admin2026!"' -ForegroundColor Yellow
        exit 1
    }
    $userEsc = $Username.Replace("'", "\'")
    $passEsc = $Password.Replace("'", "\'")
    $py = @'
from django.contrib.auth.models import User
username = 'USERNAME_PLACEHOLDER'
password = 'PASSWORD_PLACEHOLDER'
u = User.objects.filter(username=username).first()
if u:
    u.set_password(password)
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.save()
    print('OK: contrasena restablecida para ' + username)
else:
    User.objects.create_superuser(username, username + '@ekisolutions.com', password)
    print('OK: superusuario creado: ' + username)
'@.Replace('USERNAME_PLACEHOLDER', $userEsc).Replace('PASSWORD_PLACEHOLDER', $passEsc)
}

$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))

$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate && echo $pyB64 | base64 -d | python manage.py shell
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
