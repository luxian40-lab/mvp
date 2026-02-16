# Script PowerShell para commit y push de optimizaciones

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PREPARANDO COMMIT - OPTIMIZACIONES RENDER" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Verificar que estamos en git
if (-not (Test-Path ".git" -PathType Container)) {
    Write-Host "ERROR: No es un repositorio git" -ForegroundColor Red
    Write-Host "Ejecuta primero: git init" -ForegroundColor Yellow
    exit 1
}

# Mostrar status
Write-Host ""
Write-Host "Estado actual del repositorio:" -ForegroundColor Cyan
git status --short

# Archivos principales
Write-Host ""
Write-Host "Archivos principales en este commit:" -ForegroundColor Cyan
Write-Host "  - Dockerfile.render (optimizado para 512MB)" -ForegroundColor White
Write-Host "  - requirements.render.txt (con S3 para videos)" -ForegroundColor White
Write-Host "  - render.yaml (configuracion automatica)" -ForegroundColor White
Write-Host "  - .ebextensions/*.config (AWS EB optimizado)" -ForegroundColor White
Write-Host "  - scripts/verification/* (verificadores)" -ForegroundColor White
Write-Host "  - Documentacion completa" -ForegroundColor White

# Confirmar
Write-Host ""
$response = Read-Host "Hacer commit de estos cambios? (y/n)"

if ($response -ne "y" -and $response -ne "Y") {
    Write-Host "Cancelado" -ForegroundColor Yellow
    exit 0
}

# Agregar archivos
Write-Host ""
Write-Host "Agregando archivos..." -ForegroundColor Cyan

git add Dockerfile.render
git add requirements.render.txt
git add render.yaml
git add .ebextensions/
git add .platform/
git add scripts/verification/
git add OPTIMIZACION_RENDER.md
git add OPCIONES_ECONOMICAS.md
git add GUIA_DEPLOYMENT_EB.md
git add AWS_DEPLOYMENT_DECISION.md
git add RECOMENDACION_INSTANCIA.md
git add RESUMEN_EJECUTIVO_AWS.md
git add LEEME_PRIMERO.md
git add deploy_eb.sh
git add configure_eb_env.sh
git add pre_deploy_check.sh
git add commit_changes.sh
git add commit_changes.ps1

# Commit message
$commitMessage = @"
Optimizaciones para deployment en Render y AWS

## Optimizaciones Render Standard (512MB RAM)
- Dockerfile.render: 1 worker, optimizado para memoria
- requirements.render.txt: dependencias minimas + S3 para videos
- render.yaml: configuracion automatica con variables de entorno
- Reduccion de ~500MB en uso de RAM

## Configuracion AWS Elastic Beanstalk
- .ebextensions/ limpiados y optimizados
- t3.medium (4GB) por estabilidad comprobada
- Scripts automatizados: deploy_eb.sh, configure_eb_env.sh
- Verificadores: BOM, AWS ready, dependencias

## Mejoras Generales
- Removido BOM de archivos criticos
- Variables de entorno seguras (no van a git)
- Documentacion completa para ambas plataformas
- Codigo limpio sin emojis

## Archivos Principales
- Dockerfile.render (512MB optimized)
- requirements.render.txt (con boto3/s3)
- render.yaml (auto-deploy config)
- deploy_eb.sh (AWS deployment)
- scripts/verification/ (validadores)

## Costos
- Render Standard: ~`$14/mes (web + db)
- AWS EB Single: ~`$75/mes
- AWS EB Reserved: ~`$51/mes

Configurado para ambas plataformas segun necesidad y presupuesto.
"@

# Crear commit
Write-Host ""
Write-Host "Creando commit..." -ForegroundColor Cyan

git commit -m $commitMessage

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Commit creado exitosamente" -ForegroundColor Green
    
    # Ver el commit
    Write-Host ""
    Write-Host "Detalle del commit:" -ForegroundColor Cyan
    git log -1 --stat
    
    # Preguntar por push
    Write-Host ""
    $response = Read-Host "Push a origin/main? (y/n)"
    
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host ""
        Write-Host "Pushing a origin/main..." -ForegroundColor Cyan
        git push origin main
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "==========================================" -ForegroundColor Green
            Write-Host "PUSH EXITOSO" -ForegroundColor Green
            Write-Host "==========================================" -ForegroundColor Green
            Write-Host ""
            Write-Host "Proximos pasos:" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Para Render:" -ForegroundColor Yellow
            Write-Host "  1. Ir a render.com dashboard" -ForegroundColor White
            Write-Host "  2. New -> Blueprint" -ForegroundColor White
            Write-Host "  3. Connect GitHub repo" -ForegroundColor White
            Write-Host "  4. Render detecta render.yaml" -ForegroundColor White
            Write-Host "  5. Configurar variables de entorno:" -ForegroundColor White
            Write-Host "     - SECRET_KEY" -ForegroundColor Gray
            Write-Host "     - TWILIO_ACCOUNT_SID" -ForegroundColor Gray
            Write-Host "     - TWILIO_AUTH_TOKEN" -ForegroundColor Gray
            Write-Host "     - OPENAI_API_KEY" -ForegroundColor Gray
            Write-Host "     - AWS_ACCESS_KEY_ID" -ForegroundColor Gray
            Write-Host "     - AWS_SECRET_ACCESS_KEY" -ForegroundColor Gray
            Write-Host "     - AWS_STORAGE_BUCKET_NAME" -ForegroundColor Gray
            Write-Host "  6. Deploy!" -ForegroundColor White
            Write-Host ""
            Write-Host "Para AWS:" -ForegroundColor Yellow
            Write-Host "  1. eb init (si no lo has hecho)" -ForegroundColor White
            Write-Host "  2. bash configure_eb_env.sh" -ForegroundColor White
            Write-Host "  3. bash deploy_eb.sh" -ForegroundColor White
            Write-Host ""
        } else {
            Write-Host "ERROR: Push fallido" -ForegroundColor Red
            Write-Host "Verifica tu conexion o permisos" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Push cancelado. Para push manual:" -ForegroundColor Yellow
        Write-Host "  git push origin main" -ForegroundColor White
    }
} else {
    Write-Host "ERROR: Commit fallido" -ForegroundColor Red
    exit 1
}
