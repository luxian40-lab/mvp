# ========================================
# SCRIPT DE BACKUP ANTES DEL DEPLOYMENT (Windows)
# ========================================
# Este script crea un backup completo de tu base de datos SQLite
# Ejecútalo ANTES de hacer el deploy a AWS
# Uso: .\backup_bd.ps1

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "backups"
$backupFile = "$backupDir\backup_$timestamp.sqlite3"

Write-Host "🔄 Creando backup de la base de datos..." -ForegroundColor Cyan

# Crear directorio de backups si no existe
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

# Copiar base de datos
if (Test-Path "db.sqlite3") {
    Copy-Item "db.sqlite3" $backupFile
    Write-Host "✅ Backup creado: $backupFile" -ForegroundColor Green
    
    # Listar backups existentes
    Write-Host ""
    Write-Host "📦 Backups disponibles:" -ForegroundColor Yellow
    Get-ChildItem $backupDir -Filter *.sqlite3 | Format-Table Name, Length, LastWriteTime -AutoSize
    
    Write-Host ""
    Write-Host "✅ Backup completado exitosamente" -ForegroundColor Green
    Write-Host "⚠️  Guarda este archivo en un lugar seguro antes del deployment" -ForegroundColor Yellow
} else {
    Write-Host "❌ ERROR: No se encontró db.sqlite3" -ForegroundColor Red
    exit 1
}
