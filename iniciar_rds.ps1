# Script para iniciar el RDS eki-database
# Requiere credenciales de AWS con permisos RDS

Write-Host "🔍 Verificando estado del RDS eki-database..." -ForegroundColor Yellow

$status = aws rds describe-db-instances `
    --db-instance-identifier eki-database `
    --query 'DBInstances[0].DBInstanceStatus' `
    --output text

Write-Host "Estado actual: $status" -ForegroundColor Cyan

if ($status -eq "stopped") {
    Write-Host "⚠️  El RDS está detenido. Intentando iniciar..." -ForegroundColor Red
    
    $result = aws rds start-db-instance --db-instance-identifier eki-database 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ RDS iniciando correctamente. Esto puede tardar 5-10 minutos." -ForegroundColor Green
        Write-Host "📊 Esperando a que esté disponible..." -ForegroundColor Yellow
        
        aws rds wait db-instance-available --db-instance-identifier eki-database
        
        Write-Host "✅ RDS disponible!" -ForegroundColor Green
    } else {
        Write-Host "❌ Error al iniciar RDS:" -ForegroundColor Red
        Write-Host $result -ForegroundColor Red
        Write-Host ""
        Write-Host "SOLUCIÓN ALTERNATIVA:" -ForegroundColor Yellow
        Write-Host "1. Ve a AWS Console: https://us-east-2.console.aws.amazon.com/rds/" -ForegroundColor Cyan
        Write-Host "2. Selecciona 'eki-database'" -ForegroundColor Cyan
        Write-Host "3. Click en 'Actions' > 'Start'" -ForegroundColor Cyan
        Write-Host "4. Espera 5-10 minutos" -ForegroundColor Cyan
        Write-Host "5. Vuelve a ejecutar las migraciones" -ForegroundColor Cyan
    }
} elseif ($status -eq "available") {
    Write-Host "✅ El RDS ya está disponible!" -ForegroundColor Green
} elseif ($status -eq "starting") {
    Write-Host "⏳ El RDS ya está iniciando. Esperando..." -ForegroundColor Yellow
    aws rds wait db-instance-available --db-instance-identifier eki-database
    Write-Host "✅ RDS disponible!" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Estado del RDS: $status" -ForegroundColor Cyan
}

# Verificar endpoint
$endpoint = aws rds describe-db-instances `
    --db-instance-identifier eki-database `
    --query 'DBInstances[0].Endpoint.Address' `
    --output text

Write-Host ""
Write-Host "📍 Endpoint: $endpoint" -ForegroundColor Green
Write-Host "🔌 Puerto: 5432" -ForegroundColor Green
Write-Host "🗄️  Base de datos: ekidb" -ForegroundColor Green
