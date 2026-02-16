# ========================================
# SCRIPT DE PRE-DEPLOYMENT - CHECKLIST AUTOMÁTICO
# ========================================
# Este script verifica que todo esté listo antes del deployment
# Uso: .\pre_deploy_check.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 69 -ForegroundColor Cyan
Write-Host "🚀 CHECKLIST DE PRE-DEPLOYMENT - EKI MVP" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

$errores = 0
$warnings = 0

# 1. Verificar archivos críticos
Write-Host "📋 1. Verificando archivos críticos..." -ForegroundColor Cyan
$archivosRequeridos = @(
    "requirements.txt",
    "Procfile",
    "manage.py",
    ".gitignore",
    ".ebextensions\django.config",
    ".platform\hooks\postdeploy\01_migrate.sh",
    ".env.example"
)

foreach ($archivo in $archivosRequeridos) {
    if (Test-Path $archivo) {
        Write-Host "   ✅ $archivo" -ForegroundColor Green
    } else {
        Write-Host "   ❌ FALTA: $archivo" -ForegroundColor Red
        $errores++
    }
}

# 2. Verificar que .env NO esté en Git
Write-Host ""
Write-Host "📋 2. Verificando .gitignore..." -ForegroundColor Cyan
if (Test-Path ".gitignore") {
    $gitignoreContent = Get-Content ".gitignore" -Raw
    if ($gitignoreContent -match "\.env") {
        Write-Host "   ✅ .env está en .gitignore" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  WARNING: .env NO está en .gitignore" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "   ❌ No existe .gitignore" -ForegroundColor Red
    $errores++
}

# 3. Verificar Django check
Write-Host ""
Write-Host "📋 3. Verificando Django..." -ForegroundColor Cyan
try {
    & .\.venv\Scripts\python.exe manage.py check --quiet
    Write-Host "   ✅ Django check: 0 errores" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Django check falló" -ForegroundColor Red
    $errores++
}

# 4. Verificar dependencias
Write-Host ""
Write-Host "📋 4. Verificando dependencias críticas..." -ForegroundColor Cyan
$dependenciasCriticas = @("Django", "gunicorn", "psycopg2-binary", "boto3", "twilio")

foreach ($dep in $dependenciasCriticas) {
    $instalado = & .\.venv\Scripts\pip.exe list | Select-String -Pattern "^$dep\s"
    if ($instalado) {
        Write-Host "   ✅ $dep instalado" -ForegroundColor Green
    } else {
        Write-Host "   ❌ FALTA: $dep" -ForegroundColor Red
        $errores++
    }
}

# 5. Verificar que db.sqlite3 exista (para backup)
Write-Host ""
Write-Host "Verificando base de datos local..." -ForegroundColor Cyan
if (Test-Path "db.sqlite3") {
    $dbSize = (Get-Item "db.sqlite3").Length / 1MB
    $dbSizeRounded = [math]::Round($dbSize, 2)
    Write-Host "   OK db.sqlite3 existe $dbSizeRounded MB" -ForegroundColor Green
} else {
    Write-Host "   WARNING db.sqlite3 no existe" -ForegroundColor Yellow
    $warnings++
}

# 6. Verificar .env.example
Write-Host ""
Write-Host "📋 6. Verificando .env.example..." -ForegroundColor Cyan
if (Test-Path ".env.example") {
    $envExample = Get-Content ".env.example" -Raw
    $variablesRequeridas = @("SECRET_KEY", "DATABASE_URL", "AWS_ACCESS_KEY_ID", "TWILIO_ACCOUNT_SID", "OPENAI_API_KEY")
    
    foreach ($var in $variablesRequeridas) {
        if ($envExample -match $var) {
            Write-Host "   ✅ $var documentada" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  FALTA documentar: $var" -ForegroundColor Yellow
            $warnings++
        }
    }
} else {
    Write-Host "   ❌ .env.example no existe" -ForegroundColor Red
    $errores++
}

# Resumen final
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "📊 RESUMEN" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Cyan

if ($errores -eq 0 -and $warnings -eq 0) {
    Write-Host "TODO LISTO PARA DEPLOYMENT" -ForegroundColor Green
    Write-Host ""
    Write-Host "Proximos pasos:" -ForegroundColor Cyan
    Write-Host "1. Ejecuta: .\backup_bd.ps1 (hacer backup)" -ForegroundColor White
    Write-Host "2. Ejecuta: python generar_secret_key.py (generar SECRET_KEY)" -ForegroundColor White
    Write-Host "3. Configura RDS PostgreSQL en AWS Console" -ForegroundColor White
    Write-Host "4. Ejecuta: eb init (inicializar Elastic Beanstalk)" -ForegroundColor White
    exit 0
} elseif ($errores -eq 0) {
    Write-Host "LISTO CON ADVERTENCIAS: $warnings warnings" -ForegroundColor Yellow
    Write-Host "Puedes continuar, pero revisa las advertencias arriba" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "NO LISTO: $errores errores, $warnings warnings" -ForegroundColor Red
    Write-Host "Debes corregir los errores antes de hacer deployment" -ForegroundColor Red
    exit 1
}
