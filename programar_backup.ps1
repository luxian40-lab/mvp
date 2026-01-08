# Programar Backup Automático en Windows Task Scheduler
# Ejecuta este script UNA VEZ para configurar backups diarios

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Configurar Backup Automático Diario" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si se ejecuta como administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  ADVERTENCIA: Se requieren permisos de administrador" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Haz clic derecho en este archivo y selecciona:" -ForegroundColor White
    Write-Host "'Ejecutar con PowerShell' como Administrador" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host "✅ Permisos de administrador verificados" -ForegroundColor Green
Write-Host ""

# Obtener rutas
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupScript = Join-Path $SCRIPT_DIR "backup_automatico.ps1"

# Configuración de la tarea
$taskName = "Eki_Backup_Automatico"
$hora = Read-Host "¿A qué hora quieres ejecutar el backup diario? (formato 24h, ej: 02:00)"

if (-not ($hora -match '^\d{2}:\d{2}$')) {
    Write-Host "❌ Formato de hora inválido. Usa formato HH:MM (ej: 02:00)" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Configurando tarea programada..." -ForegroundColor Yellow

try {
    # Eliminar tarea si ya existe
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "🗑️  Eliminando tarea existente..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    # Crear acción de la tarea
    $action = New-ScheduledTaskAction `
        -Execute "PowerShell.exe" `
        -Argument "-ExecutionPolicy Bypass -File `"$backupScript`"" `
        -WorkingDirectory $SCRIPT_DIR
    
    # Crear trigger (diario a la hora especificada)
    $trigger = New-ScheduledTaskTrigger -Daily -At $hora
    
    # Configuración de la tarea
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType ServiceAccount `
        -RunLevel Highest
    
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false
    
    # Registrar la tarea
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Backup automático diario de la base de datos Eki MVP" | Out-Null
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  ✅ Backup Automático Configurado" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📅 Programación:" -ForegroundColor Cyan
    Write-Host "   Frecuencia: Diaria" -ForegroundColor White
    Write-Host "   Hora: $hora" -ForegroundColor White
    Write-Host "   Retención: 7 días" -ForegroundColor White
    Write-Host ""
    Write-Host "🛠️  Gestión:" -ForegroundColor Cyan
    Write-Host "   Ver tarea: Abre 'Programador de tareas' de Windows" -ForegroundColor White
    Write-Host "   Buscar: $taskName" -ForegroundColor White
    Write-Host ""
    Write-Host "📂 Backups se guardarán en:" -ForegroundColor Cyan
    Write-Host "   $SCRIPT_DIR\backups\" -ForegroundColor White
    Write-Host ""
    
    # Preguntar si desea ejecutar backup ahora
    Write-Host "¿Deseas ejecutar el backup ahora para probar? (S/N)" -ForegroundColor Yellow
    $respuesta = Read-Host
    
    if ($respuesta -eq 'S' -or $respuesta -eq 's') {
        Write-Host ""
        Write-Host "Ejecutando backup de prueba..." -ForegroundColor Yellow
        & $backupScript
    }
    
} catch {
    Write-Host ""
    Write-Host "❌ Error al configurar tarea: $_" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

Write-Host ""
Write-Host "✅ Configuración completada" -ForegroundColor Green
Write-Host ""
pause
