# Script de Despliegue a Produccion - EKI MVP
# Fecha: Feb 2026

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Preparando despliegue a eki-prod-final..." -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Verificar .env
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "OPENAI_API_KEY=sk-proj-") {
        Write-Host "[OK] OPENAI_API_KEY encontrada en .env" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] OPENAI_API_KEY no encontrada en .env" -ForegroundColor Yellow
        $continuar = Read-Host "Deseas continuar de todas formas? (si/no)"
        if ($continuar -ne "si") {
            Write-Host "[ERROR] Abortando despliegue." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "[WARNING] Archivo .env no encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Iniciando despliegue..." -ForegroundColor Cyan
Write-Host ""

# 1. Verificar archivos criticos
Write-Host "1. Verificando archivos criticos..." -ForegroundColor Yellow
$archivos_criticos = @(
    "manage.py",
    "mvp_project\wsgi.py",
    "mvp_project\settings.py",
    "requirements.txt",
    "Procfile",
    "core\agente_cursos.py"
)

$faltantes = @()
foreach ($archivo in $archivos_criticos) {
    if (!(Test-Path $archivo)) {
        $faltantes += $archivo
    }
}

if ($faltantes.Count -gt 0) {
    Write-Host "[ERROR] Archivos faltantes:" -ForegroundColor Red
    $faltantes | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "[OK] Todos los archivos criticos presentes" -ForegroundColor Green

# 2. Desplegar a AWS Elastic Beanstalk
Write-Host ""
Write-Host "2. Desplegando a AWS EB..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$version_label = "eki-v$timestamp"

# Verificar si EB CLI esta disponible
$eb_available = Get-Command eb -ErrorAction SilentlyContinue

if ($eb_available) {
    Write-Host "Usando EB CLI para desplegar..." -ForegroundColor Cyan
    eb deploy eki-prod-final --label $version_label
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Despliegue completado exitosamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Error en el despliegue" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[WARNING] EB CLI no disponible. Usa AWS Console o AWS CLI manualmente" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Comandos sugeridos:" -ForegroundColor Cyan
    Write-Host "1. Comprimir archivos:" -ForegroundColor White
    Write-Host "   Compress-Archive -Path * -DestinationPath deploy.zip -Force" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Subir a S3 y actualizar EB via AWS Console" -ForegroundColor White
    exit 0
}

# 3. Actualizar variables de entorno
Write-Host ""
Write-Host "3. Necesitas actualizar OPENAI_API_KEY en AWS? (si/no)" -ForegroundColor Yellow
$actualizar_key = Read-Host

if ($actualizar_key -eq "si") {
    Write-Host "Ingresa la API key de OpenAI:" -ForegroundColor Yellow
    $nueva_key = Read-Host -MaskInput
    
    Write-Host "Actualizando OPENAI_API_KEY en AWS EB..." -ForegroundColor Cyan
    aws elasticbeanstalk update-environment --environment-name eki-prod-final --option-settings "Namespace=aws:elasticbeanstalk:application:environment,OptionName=OPENAI_API_KEY,Value=$nueva_key"
    
    Write-Host "[OK] Variable de entorno actualizada" -ForegroundColor Green
}

# 4. Monitorear despliegue
Write-Host ""
Write-Host "4. Monitoreando estado del entorno..." -ForegroundColor Yellow
Write-Host "Esperando 30 segundos..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

aws elasticbeanstalk describe-environments --environment-names eki-prod-final --query "Environments[0].[EnvironmentName, Status, Health, VersionLabel]" --output table

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "DESPLIEGUE COMPLETADO" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Yellow
Write-Host "1. Verificar salud del entorno en AWS Console" -ForegroundColor White
Write-Host "2. Revisar logs con AWS CLI" -ForegroundColor White
Write-Host "3. Probar la plataforma" -ForegroundColor White
Write-Host "4. Verificar que agentes IA funcionan" -ForegroundColor White
Write-Host ""
