@echo off
REM ============================================
REM ROTACIÓN DE EMERGENCIA - CREDENCIALES TWILIO
REM ============================================
echo.
echo ========================================
echo     ROTACIÓN DE CREDENCIALES TWILIO
echo ========================================
echo.
echo PASO 1: Ve a Twilio Console
echo   URL: https://console.twilio.com/us1/account/keys-credentials/api-keys
echo.
echo PASO 2: Crear nuevo Auth Token
echo   1. Click "Create new API key"
echo   2. Friendly name: "eki-mvp-feb2026"
echo   3. Key type: Standard
echo   4. Click "Create"
echo   5. COPIA INMEDIATAMENTE el SID y SECRET (solo se muestra una vez)
echo.
echo PASO 3: Revocar credenciales antiguas
echo   URL: https://console.twilio.com/us1/account/keys-credentials/api-keys
echo   1. Busca claves antiguas
echo   2. Click "..." y "Delete"
echo.
pause
echo.
echo PASO 4: Actualizar en Elastic Beanstalk
echo.
set /p NEW_TOKEN="Pega el NUEVO Auth Token aqui: "
echo.
echo Actualizando EB...
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe setenv TWILIO_AUTH_TOKEN="%NEW_TOKEN%"
echo.
echo Reiniciando aplicación...
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe restart
echo.
echo ========================================
echo   ROTACIÓN COMPLETADA
echo ========================================
echo.
pause
