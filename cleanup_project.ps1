# Script de limpieza para PowerShell
# Elimina archivos temporales y carpetas de logs

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "LIMPIEZA DEL PROYECTO EKI MVP" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

$deletedCount = 0
$errorCount = 0

# Eliminar carpetas temporales de deployment
$foldersToDelete = @(
    "tmp_deploy_20260129103648",
    "tmp_deploy_20260129123049",
    "prod_env_log_1__unzipped",
    "prod_env_log_2__unzipped",
    ".venv-build"
)

Write-Host "Eliminando carpetas temporales..." -ForegroundColor Yellow
foreach ($folder in $foldersToDelete) {
    if (Test-Path $folder) {
        try {
            Remove-Item -Path $folder -Recurse -Force -ErrorAction Stop
            Write-Host "[OK] Eliminada: $folder" -ForegroundColor Green
            $deletedCount++
        } catch {
            Write-Host "[ERROR] No se pudo eliminar: $folder" -ForegroundColor Red
            $errorCount++
        }
    }
}

# Eliminar ZIPs viejos
$zipsToDelete = @(
    "deploy-clean-deploy-fixed-clean-20260129_141135.zip",
    "deploy-fixed-clean-20260129125126.zip",
    "deploy_20260129012639.zip",
    "deploy_20260129014933.zip",
    "dockerrun-*.zip",
    "maintenance-*.zip",
    "prod_env_log_*.zip",
    "bundle.zip"
)

Write-Host "`nEliminando ZIPs viejos..." -ForegroundColor Yellow
foreach ($zip in $zipsToDelete) {
    $files = Get-ChildItem -Path . -Filter $zip -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item -Path $file.FullName -Force
            Write-Host "[OK] Eliminado: $($file.Name)" -ForegroundColor Green
            $deletedCount++
        } catch {
            Write-Host "[ERROR] $($file.Name)" -ForegroundColor Red
            $errorCount++
        }
    }
}

# Eliminar JSONs de debug
$jsonsToDelete = @(
    "*_env_logs.json",
    "*_events*.json",
    "*_resources*.json",
    "inspect_*.json",
    "debug_*.json",
    "params*.json",
    "ssm_*.json",
    "ec2_*.json",
    "eb_*.json",
    "maint_*.json",
    "prod_*.json",
    "find_*.json",
    "http_*.json",
    "describe_*.json",
    "available_*.json",
    "app_versions.json",
    "create_env_result.json",
    "swap_result.json",
    "role_check.json"
)

Write-Host "`nEliminando JSONs de debug..." -ForegroundColor Yellow
foreach ($pattern in $jsonsToDelete) {
    $files = Get-ChildItem -Path . -Filter $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item -Path $file.FullName -Force
            Write-Host "[OK] Eliminado: $($file.Name)" -ForegroundColor Green
            $deletedCount++
        } catch {
            Write-Host "[ERROR] $($file.Name)" -ForegroundColor Red
            $errorCount++
        }
    }
}

# Eliminar TXTs de debug
$txtsToDelete = @(
    "create_env_debug*.txt",
    "curl_head.txt",
    "downloaded_logs_list.txt",
    "eb-deploy.txt",
    "eb-logs.txt",
    "eb_combined.txt",
    "prod_env_*.txt",
    "produccion_*.txt",
    "ssm_*.txt",
    "monitor_*.log"
)

Write-Host "`nEliminando TXTs de debug..." -ForegroundColor Yellow
foreach ($pattern in $txtsToDelete) {
    $files = Get-ChildItem -Path . -Filter $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item -Path $file.FullName -Force
            Write-Host "[OK] Eliminado: $($file.Name)" -ForegroundColor Green
            $deletedCount++
        } catch {
            Write-Host "[ERROR] $($file.Name)" -ForegroundColor Red
            $errorCount++
        }
    }
}

# Resumen
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "RESUMEN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Elementos eliminados: $deletedCount" -ForegroundColor Green
Write-Host "Errores: $errorCount" -ForegroundColor Red

if ($deletedCount -gt 0) {
    Write-Host "`nProyecto limpiado exitosamente!" -ForegroundColor Green
} else {
    Write-Host "`nNo se encontraron archivos para eliminar o todos ya fueron eliminados." -ForegroundColor Yellow
}
