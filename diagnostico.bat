@echo off
chcp 65001 > nul
color 0E
title 🔍 Diagnóstico del Sistema Eki

echo.
echo ═══════════════════════════════════════════════════════════════
echo          🔍 DIAGNÓSTICO DEL SISTEMA EKI 🔍
echo ═══════════════════════════════════════════════════════════════
echo.

REM Activar entorno virtual
call .venv\Scripts\activate.bat

echo 📋 Verificando estado del sistema...
echo.
echo ═══════════════════════════════════════════════════════════════
echo  1. DJANGO - Verificando configuración
echo ═══════════════════════════════════════════════════════════════
python manage.py check --deploy
echo.

echo ═══════════════════════════════════════════════════════════════
echo  2. NGROK - Verificando proceso
echo ═══════════════════════════════════════════════════════════════
powershell -Command "Get-Process | Where-Object {$_.ProcessName -like '*ngrok*'} | Format-Table -AutoSize"
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Ngrok NO está corriendo
    echo    Solución: Ejecuta iniciar_sistema_completo.bat
) else (
    echo ✅ Ngrok está corriendo
)
echo.

echo ═══════════════════════════════════════════════════════════════
echo  3. VARIABLES DE ENTORNO - Verificando .env
echo ═══════════════════════════════════════════════════════════════
if exist .env (
    echo ✅ Archivo .env existe
    echo.
    echo    Verificando claves configuradas:
    findstr /C:"TWILIO_ACCOUNT_SID" .env >nul && echo    ✅ TWILIO_ACCOUNT_SID configurada || echo    ❌ TWILIO_ACCOUNT_SID NO configurada
    findstr /C:"TWILIO_AUTH_TOKEN" .env >nul && echo    ✅ TWILIO_AUTH_TOKEN configurada || echo    ❌ TWILIO_AUTH_TOKEN NO configurada
    findstr /C:"OPENAI_API_KEY" .env >nul && echo    ✅ OPENAI_API_KEY configurada || echo    ❌ OPENAI_API_KEY NO configurada
    findstr /C:"COHERE_API_KEY" .env >nul && echo    ✅ COHERE_API_KEY configurada || echo    ❌ COHERE_API_KEY NO configurada
) else (
    echo ❌ Archivo .env NO existe
    echo    Solución: Copia .env.example a .env y configura las claves
)
echo.

echo ═══════════════════════════════════════════════════════════════
echo  4. BASE DE DATOS - Verificando migraciones
echo ═══════════════════════════════════════════════════════════════
python manage.py showmigrations core | findstr /C:"[X]" >nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Migraciones aplicadas
) else (
    echo ❌ Hay migraciones pendientes
    echo    Solución: python manage.py migrate
)
echo.

echo ═══════════════════════════════════════════════════════════════
echo  5. SERVIDOR WEB - Verificando puerto 8000
echo ═══════════════════════════════════════════════════════════════
netstat -an | findstr ":8000" >nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Servidor corriendo en puerto 8000
) else (
    echo ❌ Servidor NO está corriendo
    echo    Solución: python manage.py runserver
)
echo.

echo ═══════════════════════════════════════════════════════════════
echo  6. MENSAJES DE WHATSAPP - Últimos registros
echo ═══════════════════════════════════════════════════════════════
python -c "from core.models import WhatsappLog; logs = WhatsappLog.objects.all().order_by('-fecha')[:5]; print(f'Total de mensajes: {WhatsappLog.objects.count()}'); [print(f'{log.fecha.strftime(\"%%Y-%%m-%%d %%H:%%M\")} | {log.tipo} | {log.mensaje[:50]}') for log in logs] if logs else print('Sin mensajes')"
echo.

echo ═══════════════════════════════════════════════════════════════
echo  📊 RESUMEN DEL DIAGNÓSTICO
echo ═══════════════════════════════════════════════════════════════
echo.
echo  Si todos los checks están en ✅ el sistema debería funcionar.
echo.
echo  ❌ Si alguno está en rojo:
echo     1. Lee el mensaje de error
echo     2. Sigue la solución sugerida
echo     3. Ejecuta este diagnóstico de nuevo
echo.
echo  📖 Para más ayuda consulta: SOLUCION_BOT_NO_RESPONDE.md
echo.
echo ═══════════════════════════════════════════════════════════════
echo.
pause
