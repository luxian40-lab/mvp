# Script PowerShell para programar seguimiento automático en Windows
# Crea una tarea en Task Scheduler que se ejecuta todos los días a las 9:00 AM

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PROGRAMAR SEGUIMIENTO AUTOMÁTICO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si se ejecuta como administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  Este script requiere permisos de administrador" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ejecuta PowerShell como administrador y vuelve a correr este script" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit
}

# Ruta al script bat
$scriptPath = Join-Path $PSScriptRoot "ejecutar_seguimiento.bat"

if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ Error: No se encontró ejecutar_seguimiento.bat" -ForegroundColor Red
    Write-Host ""
    pause
    exit
}

Write-Host "📋 Configuración de la tarea:" -ForegroundColor Green
Write-Host "   • Nombre: Eki_Seguimiento_Estudiantes" -ForegroundColor White
Write-Host "   • Frecuencia: Diaria" -ForegroundColor White
Write-Host "   • Hora: 9:00 AM" -ForegroundColor White
Write-Host "   • Script: $scriptPath" -ForegroundColor White
Write-Host ""

# Preguntar confirmación
$confirm = Read-Host "¿Deseas programar esta tarea? (S/N)"

if ($confirm -ne "S" -and $confirm -ne "s") {
    Write-Host ""
    Write-Host "❌ Operación cancelada" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit
}

Write-Host ""
Write-Host "⏳ Creando tarea programada..." -ForegroundColor Yellow

try {
    # Eliminar tarea existente si existe
    $existingTask = Get-ScheduledTask -TaskName "Eki_Seguimiento_Estudiantes" -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName "Eki_Seguimiento_Estudiantes" -Confirm:$false
        Write-Host "   ℹ️  Tarea existente eliminada" -ForegroundColor Cyan
    }

    # Crear acción (ejecutar el .bat)
    $action = New-ScheduledTaskAction -Execute $scriptPath

    # Crear trigger (diario a las 9:00 AM)
    $trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

    # Configuración adicional
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    # Descripción
    $description = "Ejecuta seguimiento proactivo de estudiantes en Eki - Sistema educativo por WhatsApp (estilo Huaku)"

    # Registrar tarea
    Register-ScheduledTask `
        -TaskName "Eki_Seguimiento_Estudiantes" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description $description `
        -User $env:USERNAME `
        -RunLevel Highest

    Write-Host ""
    Write-Host "✅ ¡Tarea programada exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📅 La tarea se ejecutará:" -ForegroundColor Cyan
    Write-Host "   • Todos los días a las 9:00 AM" -ForegroundColor White
    Write-Host "   • Detectará estudiantes inactivos" -ForegroundColor White
    Write-Host "   • Enviará mensajes motivacionales" -ForegroundColor White
    Write-Host ""
    Write-Host "🔧 Para gestionar la tarea:" -ForegroundColor Yellow
    Write-Host "   1. Abre 'Programador de tareas' (Task Scheduler)" -ForegroundColor White
    Write-Host "   2. Busca 'Eki_Seguimiento_Estudiantes'" -ForegroundColor White
    Write-Host "   3. Puedes editar, deshabilitar o eliminar" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 Para ejecutar manualmente ahora:" -ForegroundColor Yellow
    Write-Host "   ejecutar_seguimiento.bat" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "❌ Error al crear la tarea: $_" -ForegroundColor Red
    Write-Host ""
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
pause
