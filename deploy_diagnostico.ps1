# Deploy script para diagnóstico S3
$ErrorActionPreference = "Stop"

$appName = "eki-mvp"
$envName = "eki-prod-final"
$versionLabel = "app-diagnostico-storage-completo"
$region = "us-east-2"
$bucket = "elasticbeanstalk-us-east-2-178773630934"

Write-Host "`n=== PREPARANDO DEPLOYMENT DIAGNOSTICO S3 ===" -ForegroundColor Cyan

# 1. Crear archivo ZIP
Write-Host "`n[1/4] Creando archivo ZIP..." -ForegroundColor Yellow
$zipFile = "$versionLabel.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }

# Comprimir todos los archivos necesarios
$filesToInclude = @()

# Archivos raíz
if (Test-Path "manage.py") { $filesToInclude += "manage.py" }
if (Test-Path "requirements.txt") { $filesToInclude += "requirements.txt" }
if (Test-Path "Procfile") { $filesToInclude += "Procfile" }

# Directorios
if (Test-Path "core") { $filesToInclude += "core" }
if (Test-Path "mvp_project") { $filesToInclude += "mvp_project" }
if (Test-Path ".ebextensions") { $filesToInclude += ".ebextensions" }
if (Test-Path ".platform") { $filesToInclude += ".platform" }

Write-Host "Archivos a incluir: $($filesToInclude -join ', ')" -ForegroundColor Cyan

Compress-Archive -Path $filesToInclude -DestinationPath $zipFile -Force

Write-Host "[OK] ZIP creado: $zipFile" -ForegroundColor Green

# 2. Subir a S3
Write-Host "`n[2/4] Subiendo a S3..." -ForegroundColor Yellow
aws s3 cp $zipFile "s3://$bucket/$appName/$zipFile" --region $region
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo al subir a S3" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Subido a S3" -ForegroundColor Green

# 3. Crear versión de aplicación
Write-Host "`n[3/4] Creando versión de aplicación..." -ForegroundColor Yellow
aws elasticbeanstalk create-application-version `
    --application-name $appName `
    --version-label $versionLabel `
    --source-bundle "S3Bucket=$bucket,S3Key=$appName/$zipFile" `
    --region $region

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo al crear versión" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Versión creada" -ForegroundColor Green

# 4. Desplegar al entorno
Write-Host "`n[4/4] Desplegando a $envName..." -ForegroundColor Yellow
aws elasticbeanstalk update-environment `
    --environment-name $envName `
    --version-label $versionLabel `
    --region $region

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo al desplegar" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== DEPLOYMENT INICIADO ===" -ForegroundColor Cyan
Write-Host "Versión: $versionLabel" -ForegroundColor White
Write-Host "Entorno: $envName" -ForegroundColor White
Write-Host "`nMonitorea el progreso en:" -ForegroundColor Yellow
Write-Host "https://us-east-2.console.aws.amazon.com/elasticbeanstalk/home?region=us-east-2#/environment/dashboard?applicationName=$appName&environmentId=$envName" -ForegroundColor Cyan

Write-Host "`n[SIGUIENTE PASO]" -ForegroundColor Yellow
Write-Host "1. Espera a que el deployment termine (Verde)" -ForegroundColor White
Write-Host "2. Sube un archivo en el admin de Django" -ForegroundColor White
Write-Host "3. Revisa los logs con:" -ForegroundColor White
Write-Host "   aws elasticbeanstalk retrieve-environment-info --environment-name $envName --info-type tail --region $region" -ForegroundColor Cyan
