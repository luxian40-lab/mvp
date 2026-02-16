@echo off
chcp 65001 >nul
cd /d "%~dp0"
color 0A

:MENU
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║          🌱 EKI MVP - MENÚ DE ADMINISTRACIÓN 🌱           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo   [1] 🚀 Iniciar Sistema Completo (Django + ngrok)
echo   [2] 🛑 Detener Sistema
echo.
echo   [3] 📦 Migrar Base de Datos
echo   [4] 🏷️  Crear Temas de Campañas
echo   [5] 💬 Crear Conversación de Prueba
echo   [6] 🔍 Verificar Estado de Conversaciones
echo.
echo   [7] 🤖 Ver Reporte de Agentes IA
echo   [8] 📊 Diagnóstico del Sistema
echo   [9] 🔄 Ejecutar Seguimiento Proactivo
echo.
echo   [0] ❌ Salir
echo.
echo ════════════════════════════════════════════════════════════
set /p opcion="   Selecciona una opción [0-9]: "

if "%opcion%"=="1" goto INICIAR_SISTEMA
if "%opcion%"=="2" goto DETENER_SISTEMA
if "%opcion%"=="3" goto MIGRAR
if "%opcion%"=="4" goto TEMAS
if "%opcion%"=="5" goto CONVERSACION
if "%opcion%"=="6" goto VERIFICAR
if "%opcion%"=="7" goto REPORTE_AGENTES
if "%opcion%"=="8" goto DIAGNOSTICO
if "%opcion%"=="9" goto SEGUIMIENTO
if "%opcion%"=="0" goto SALIR

echo.
echo   ❌ Opción inválida. Presiona cualquier tecla para continuar...
pause >nul
goto MENU

:INICIAR_SISTEMA
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🚀 INICIANDO SISTEMA COMPLETO
echo ════════════════════════════════════════════════════════════
echo.
echo   📋 Verificando sistema...
.venv\Scripts\python.exe manage.py check

echo.
echo   📦 Aplicando migraciones...
.venv\Scripts\python.exe manage.py migrate

echo.
echo   🌐 Iniciando Django en http://127.0.0.1:8000/
start "Django Server" cmd /k ".venv\Scripts\python.exe manage.py runserver"

echo.
echo   🔗 Iniciando ngrok tunnel...
start "ngrok" cmd /k "ngrok http 8000"

echo.
echo   ✅ Sistema iniciado correctamente
echo.
echo   📍 Django: http://127.0.0.1:8000/admin/
echo   📍 ngrok: http://127.0.0.1:4040/
echo.
echo   💡 Tip: Configura el webhook de Twilio con la URL de ngrok
echo.
pause
goto MENU

:DETENER_SISTEMA
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🛑 DETENIENDO SISTEMA
echo ════════════════════════════════════════════════════════════
echo.
taskkill /FI "WINDOWTITLE eq Django Server*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ngrok*" /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1
taskkill /IM ngrok.exe /F >nul 2>&1
echo.
echo   ✅ Sistema detenido
echo.
pause
goto MENU

:MIGRAR
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   📦 MIGRANDO BASE DE DATOS
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe manage.py makemigrations
echo.
.venv\Scripts\python.exe manage.py migrate
echo.
echo   ✅ Migraciones completadas
echo.
pause
goto MENU

:TEMAS
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🏷️  CREANDO TEMAS DE CAMPAÑAS
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe crear_temas_campana.py
echo.
pause
goto MENU

:CONVERSACION
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   💬 CREANDO CONVERSACIÓN DE PRUEBA
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe crear_conversacion_prueba.py
echo.
pause
goto MENU

:VERIFICAR
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🔍 VERIFICANDO CONVERSACIONES
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe verificar_conversaciones.py
echo.
pause
goto MENU

:REPORTE_AGENTES
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🤖 REPORTE DE AGENTES IA
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe manage.py reporte_agentes
echo.
pause
goto MENU

:DIAGNOSTICO
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   📊 DIAGNÓSTICO DEL SISTEMA
echo ════════════════════════════════════════════════════════════
echo.
echo   🔍 Verificando Python y Django...
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m django --version

echo.
echo   🔍 Verificando configuración...
.venv\Scripts\python.exe manage.py check

echo.
echo   🔍 Verificando base de datos...
.venv\Scripts\python.exe manage.py showmigrations

echo.
echo   🔍 Estadísticas de la base de datos...
.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings'); django.setup(); from core.models import Estudiante, WhatsappLog, Campana, Plantilla; print(f'  - Estudiantes: {Estudiante.objects.count()}'); print(f'  - Mensajes WhatsApp: {WhatsappLog.objects.count()}'); print(f'  - Campañas: {Campana.objects.count()}'); print(f'  - Plantillas: {Plantilla.objects.count()}')"

echo.
echo   ✅ Diagnóstico completado
echo.
pause
goto MENU

:SEGUIMIENTO
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   🔄 EJECUTANDO SEGUIMIENTO PROACTIVO
echo ════════════════════════════════════════════════════════════
echo.
.venv\Scripts\python.exe manage.py seguimiento_proactivo
echo.
pause
goto MENU

:SALIR
cls
echo.
echo ════════════════════════════════════════════════════════════
echo   👋 ¡Hasta pronto!
echo ════════════════════════════════════════════════════════════
echo.
timeout /t 2 >nul
exit
