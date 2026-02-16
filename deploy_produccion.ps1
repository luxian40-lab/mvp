# ================================
# Script de Despliegue a Producción
# ================================

Write-Host "🚀 Preparando despliegue a eki-prod-final..." -ForegroundColor Cyan
Write-Host ""

# ⚠️ VERIFICACIÓN DE CONFIGURACIÓN
Write-Host "=" -Repeat 70 -ForegroundColor Cyan
Write-Host "🔍 VERIFICACIÓN PRE-DESPLIEGUE" -ForegroundColor Cyan
Write-Host "=" -Repeat 70 -ForegroundColor Cyan
Write-Host ""

# Verificar .env
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "OPENAI_API_KEY=sk-proj-") {
        Write-Host "✅ OPENAI_API_KEY encontrada en .env" -ForegroundColor Green
    } else {
        Write-Host "⚠️ OPENAI_API_KEY no encontrada en .env" -ForegroundColor Yellow
        $continuar = Read-Host "¿Deseas continuar de todas formas? (si/no)"
        if ($continuar -ne "si") {
            Write-Host "❌ Abortando despliegue." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "⚠️ Archivo .env no encontrado" -ForegroundColor Yellow
    Write-Host "   La aplicación usará variables de entorno de AWS EB" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📦 Iniciando despliegue..." -ForegroundColor Cyan
Write-Host ""

# 1. Verificar archivos críticos
Write-Host "1️⃣ Verificando archivos críticos..." -ForegroundColor Yellow
$archivos_criticos = @(
    "manage.py",
    "mvp_project\wsgi.py",
    "mvp_project\settings.py",
    "mvp_project\settings_production.py",
    "requirements.txt",
    "requirements-constraints.txt",
    "runtime.txt",
    "Procfile",
    ".ebextensions\01_django.config",
    ".platform\hooks\postdeploy\99_migrate.sh",
    ".ebignore",
    "core\agente_cursos.py"
)

$faltantes = @()
foreach ($archivo in $archivos_criticos) {
    if (!(Test-Path $archivo)) {
        $faltantes += $archivo
    }
}

if ($faltantes.Count -gt 0) {
    Write-Host "❌ Archivos faltantes:" -ForegroundColor Red
    $faltantes | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "✅ Todos los archivos críticos presentes" -ForegroundColor Green

# 2. Desplegar a AWS Elastic Beanstalk
Write-Host ""
Write-Host "2️⃣ Creando versión de aplicación..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$version_label = "eki-v$timestamp"

# Comprimir archivos (excluyendo lo que está en .ebignore)
Write-Host "Comprimiendo aplicación..." -ForegroundColor Cyan
$zip_name = "deploy-$version_label.zip"

# Usar eb deploy si está disponible
$eb_available = Get-Command eb -ErrorAction SilentlyContinue

if ($eb_available) {
    Write-Host "Usando EB CLI para desplegar..." -ForegroundColor Cyan
    eb deploy eki-prod-final --label $version_label
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Despliegue completado exitosamente" -ForegroundColor Green
    } else {
        Write-Host "❌ Error en el despliegue" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "⚠️ EB CLI no disponible. Usando AWS CLI..." -ForegroundColor Yellow
    
    # Comprimir manualmente
    Compress-Archive -Path * -DestinationPath $zip_name -Force
    
    Write-Host "Subiendo a S3..." -ForegroundColor Cyan
    aws s3 cp $zip_name "s3://elasticbeanstalk-us-east-2-ACCOUNT-ID/eki-prod/$zip_name"
    
    Write-Host "Creando versión de aplicación..." -ForegroundColor Cyan
    aws elasticbeanstalk create-application-version `
        --application-name eki-mvp-python `
        --version-label $version_label `
        --source-bundle "S3Bucket=elasticbeanstalk-us-east-2-ACCOUNT-ID,S3Key=eki-prod/$zip_name"
    
    Write-Host "Actualizando entorno..." -ForegroundColor Cyan
    aws elasticbeanstalk update-environment `
        --environment-name eki-prod-final `
        --version-label $version_label
    
    Write-Host "✅ Comando de despliegue enviado" -ForegroundColor Green
}

# 3. Actualizar variables de entorno (si es necesario)
Write-Host ""
Write-Host "3️⃣ ¿Necesitas actualizar la OPENAI_API_KEY en AWS? (si/no)" -ForegroundColor Yellow
$actualizar_key = Read-Host

if ($actualizar_key -eq "si") {
    Write-Host "Ingresa la NUEVA API key de OpenAI:" -ForegroundColor Yellow
    $nueva_key = Read-Host -AsSecureString
    $nueva_key_plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($nueva_key))
    
    Write-Host "Actualizando OPENAI_API_KEY en AWS EB..." -ForegroundColor Cyan
    aws elasticbeanstalk update-environment `
        --environment-name eki-prod-final `
        --option-settings "Namespace=aws:elasticbeanstalk:application:environment,OptionName=OPENAI_API_KEY,Value=$nueva_key_plain"
    
    Write-Host "✅ Variable de entorno actualizada" -ForegroundColor Green
}

# 4. Monitorear despliegue
Write-Host ""
Write-Host "4️⃣ Monitoreando estado del entorno..." -ForegroundColor Yellow
Write-Host "Esperando 30 segundos..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

aws elasticbeanstalk describe-environments --environment-names eki-prod-final --query "Environments[0].[EnvironmentName, Status, Health, VersionLabel]" --output table

Write-Host ""
Write-Host "=" -Repeat 70 -ForegroundColor Green
Write-Host "🎉 DESPLIEGUE COMPLETADO" -ForegroundColor Green
Write-Host "=" -Repeat 70 -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Yellow
Write-Host "1. Verificar salud del entorno en AWS Console" -ForegroundColor White
Write-Host "2. Revisar logs con AWS CLI" -ForegroundColor White
Write-Host "3. Probar la plataforma en: http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com" -ForegroundColor White
Write-Host "4. Verificar que agentes IA funcionan correctamente" -ForegroundColor White
Write-Host ""
Write-Host "Archivo de seguridad: SEGURIDAD_API_KEY.md" -ForegroundColor Cyan
Write-Host ""
