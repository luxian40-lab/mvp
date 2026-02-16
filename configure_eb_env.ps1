# Script para configurar variables de entorno en Elastic Beanstalk
# Uso: .\configure_eb_env.ps1

Write-Host "Configurando variables de entorno en Elastic Beanstalk..." -ForegroundColor Cyan

$ebExe = "C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe"

# Leer .env.production
$envFile = Get-Content .env.production | Where-Object { $_ -match '^\s*[A-Z_]+=.+' -and $_ -notmatch '^\s*#' }

$envVars = @()
foreach ($line in $envFile) {
    if ($line -match '^([A-Z_]+)=(.+)$') {
        $key = $matches[1]
        $value = $matches[2].Trim()
        
        # Escapar caracteres especiales para shell
        $value = $value -replace '"', '\"'
        
        $envVars += "$key=$value"
    }
}

# Unir todas las variables
$envString = $envVars -join ","

Write-Host "Variables a configurar:" -ForegroundColor Yellow
foreach ($var in $envVars) {
    $keyOnly = $var -split "=" | Select-Object -First 1
    Write-Host "  - $keyOnly" -ForegroundColor Gray
}

Write-Host "`nAplicando configuración a EB..." -ForegroundColor Cyan

# Ejecutar eb setenv
& $ebExe setenv $envString

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Variables configuradas exitosamente" -ForegroundColor Green
} else {
    Write-Host "`n✗ Error configurando variables" -ForegroundColor Red
    exit 1
}
