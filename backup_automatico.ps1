# Script de Backup Automático para Eki MVP
# Crea backups diarios de la base de datos y los reportes

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  EKI MVP - Backup Automático" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Obtener directorio del script
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "[1/3] Creando backup de base de datos..." -ForegroundColor Yellow

try {
    # Ejecutar comando de Django para backup
    & "$SCRIPT_DIR\.venv\Scripts\python.exe" manage.py backup_db --keep-days=7
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Backup de base de datos completado" -ForegroundColor Green
    } else {
        Write-Host "❌ Error al crear backup de base de datos" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/3] Verificando espacio en disco..." -ForegroundColor Yellow

# Obtener tamaño del directorio de backups
$backupDir = Join-Path $SCRIPT_DIR "backups"
if (Test-Path $backupDir) {
    $backupSize = (Get-ChildItem $backupDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    $backupCount = (Get-ChildItem $backupDir -Filter "*.sqlite3").Count
    
    Write-Host "📊 Directorio de backups:" -ForegroundColor Cyan
    Write-Host "   Tamaño total: $($backupSize.ToString('0.##')) MB" -ForegroundColor White
    Write-Host "   Archivos: $backupCount backups" -ForegroundColor White
    
    # Alertar si excede 100 MB
    if ($backupSize -gt 100) {
        Write-Host "⚠️  ADVERTENCIA: El directorio de backups ocupa más de 100 MB" -ForegroundColor Yellow
        Write-Host "   Considera reducir el periodo de retención" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Directorio de backups no encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/3] Generando resumen de backup..." -ForegroundColor Yellow

# Crear archivo de log
$logFile = Join-Path $SCRIPT_DIR "backups\backup_log.txt"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$logContent = @"
============================================
Backup Ejecutado: $timestamp
============================================
Backups totales: $backupCount
Espacio usado: $($backupSize.ToString('0.##')) MB
Estado: Exitoso ✅
============================================

"@

Add-Content -Path $logFile -Value $logContent

Write-Host "✅ Log de backup actualizado" -ForegroundColor Green
Write-Host "   Archivo: backups\backup_log.txt" -ForegroundColor White

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Backup Completado Exitosamente" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximo backup: Mañana a las $(Get-Date -Format 'HH:mm')" -ForegroundColor Cyan
Write-Host ""
