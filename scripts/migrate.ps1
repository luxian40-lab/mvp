#Requires -Version 5.1
<#
.SYNOPSIS
  Ejecuta Django migrate con el venv del repo (desde Cursor o PowerShell).
  manage.py carga automáticamente .env y .env.local en la raíz del proyecto.

.PARAMETER SqliteLocal
  Usa mvp_project.settings y quita DATABASE_URL / DB_* en esta sesión → SQLite en db.sqlite3.

.PARAMETER MigrateArgs
  Resto de argumentos para manage.py migrate (por defecto --noinput).

.EJEMPLO
  .\scripts\migrate.ps1
  .\scripts\migrate.ps1 -SqliteLocal
  .\scripts\migrate.ps1 show
#>
param(
    [switch]$SqliteLocal,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $MigrateArgs = @('--noinput')
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Error "No existe .venv. Creá el entorno en la raíz del repo: py -3 -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt"
}

if ($SqliteLocal) {
    $env:DJANGO_SETTINGS_MODULE = 'mvp_project.settings'
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:DB_NAME, Env:DB_USER, Env:DB_PASSWORD, Env:DB_HOST -ErrorAction SilentlyContinue
    Write-Host '[migrate.ps1] Modo SQLite local (mvp_project.settings, sin DATABASE_URL).' -ForegroundColor Cyan
}
else {
    if (-not $env:DJANGO_SETTINGS_MODULE) {
        $env:DJANGO_SETTINGS_MODULE = 'mvp_project.settings_production'
    }
    Write-Host "[migrate.ps1] DJANGO_SETTINGS_MODULE=$($env:DJANGO_SETTINGS_MODULE)" -ForegroundColor Cyan
    if ($env:POSTGRES_CONNECT_TIMEOUT) {
        Write-Host "[migrate.ps1] POSTGRES_CONNECT_TIMEOUT=$($env:POSTGRES_CONNECT_TIMEOUT)" -ForegroundColor DarkGray
    }
}

& $py manage.py migrate @MigrateArgs
exit $LASTEXITCODE
