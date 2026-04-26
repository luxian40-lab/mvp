#Requires -Version 5.1
<#
.SYNOPSIS
  Prueba TCP/SSL a Postgres con el venv y variables de .env (manage.py también carga .env).
#>
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot
$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Error "Creá el venv: py -3 -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt"
}
& $py (Join-Path $repoRoot 'scripts\test_pg_connection.py')
exit $LASTEXITCODE
