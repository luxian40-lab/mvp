@echo off
REM Script para iniciar ngrok en Windows

echo ================================================
echo  INICIANDO NGROK PARA WEBHOOK WHATSAPP
echo ================================================
echo.

REM Verificar si ngrok está instalado
where ngrok >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ngrok no encontrado
    echo.
    echo Por favor instala ngrok:
    echo 1. Descarga de: https://ngrok.com/download
    echo 2. Descomprime ngrok.exe
    echo 3. Mueve a C:\ngrok\ngrok.exe
    echo 4. O agrega al PATH de Windows
    echo.
    pause
    exit /b 1
)

echo [OK] ngrok encontrado
echo.
echo Iniciando tunel HTTPS para puerto 8000...
echo.
echo IMPORTANTE:
echo - Copia la URL HTTPS que aparece (https://xxxxx.ngrok.io)
echo - Configurala en Twilio/Meta Console
echo - URL completa: https://xxxxx.ngrok.io/webhook/whatsapp/
echo.
echo Presiona CTRL+C para detener
echo.
echo ================================================
echo.

REM Iniciar ngrok
ngrok http 8000
