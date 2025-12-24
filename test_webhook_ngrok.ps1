# Script para probar que el webhook funciona CON la advertencia de ngrok
# Simula cómo Twilio envía los datos

$webhookUrl = "https://unpalsied-understandingly-lizeth.ngrok-free.dev/webhook/whatsapp/"

$payload = @{
    entry = @(
        @{
            changes = @(
                @{
                    value = @{
                        messages = @(
                            @{
                                from = "whatsapp:+573001234567"
                                id = "TEST_" + (Get-Date -Format "yyyyMMddHHmmss")
                                text = @{
                                    body = "Hola, ¿cómo estás?"
                                }
                            }
                        )
                    }
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "🧪 PROBANDO WEBHOOK CON NGROK" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Enviando POST a: $webhookUrl" -ForegroundColor Yellow
Write-Host ""

try {
    # Enviamos con el header que evita la advertencia de ngrok
    $response = Invoke-WebRequest `
        -Uri $webhookUrl `
        -Method POST `
        -Body $payload `
        -ContentType "application/json" `
        -Headers @{
            "ngrok-skip-browser-warning" = "true"
            "User-Agent" = "TwilioProxy/1.1"
        } `
        -UseBasicParsing `
        -TimeoutSec 30
    
    Write-Host "✅ Respuesta recibida:" -ForegroundColor Green
    Write-Host "   Status Code: $($response.StatusCode)" -ForegroundColor Green
    
    if ($response.StatusCode -eq 200) {
        Write-Host ""
        Write-Host "🎉 ¡WEBHOOK FUNCIONANDO!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📝 Verifica ahora en:" -ForegroundColor Cyan
        Write-Host "   1. Logs de Django (deberías ver el POST)" -ForegroundColor White
        Write-Host "   2. Admin de WhatsApp Logs: http://localhost:8000/admin/core/whatsapplog/" -ForegroundColor White
        Write-Host "   3. Deberías ver 2 registros:" -ForegroundColor White
        Write-Host "      - INCOMING: El mensaje que enviaste" -ForegroundColor White
        Write-Host "      - SENT: La respuesta de la IA" -ForegroundColor White
    }
    
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔍 Verifica que:" -ForegroundColor Yellow
    Write-Host "   1. Django esté corriendo en puerto 8000" -ForegroundColor White
    Write-Host "   2. ngrok esté corriendo" -ForegroundColor White
    Write-Host "   3. La variable OPENAI_API_KEY esté en el .env" -ForegroundColor White
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
