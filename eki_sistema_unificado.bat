@echo off
chcp 65001 > nul
title EKI MVP - Sistema Unificado
color 0B

REM ================================================================
REM   EKI MVP - MENÚ UNIFICADO
REM   Todas las funcionalidades en un solo archivo
REM ================================================================

:MENU_PRINCIPAL
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🌾 EKI MVP - Sistema Educativo para Campesinos 🌾
echo ════════════════════════════════════════════════════════════════════
echo.
echo  ┌─ SISTEMA ──────────────────────────────────────────────────┐
echo  │  [1] Iniciar Sistema Completo (Django + Ngrok)            │
echo  │  [2] Solo Django (desarrollo local)                       │
echo  │  [3] Detener Sistema                                       │
echo  │  [4] Diagnóstico del Sistema                              │
echo  └────────────────────────────────────────────────────────────┘
echo.
echo  ┌─ BASE DE DATOS ────────────────────────────────────────────┐
echo  │  [5] Aplicar Migraciones                                   │
echo  │  [6] Crear Backup de Base de Datos                        │
echo  │  [7] Verificar Videos (Test multimedia)                   │
echo  └────────────────────────────────────────────────────────────┘
echo.
echo  ┌─ AGENTES IA ───────────────────────────────────────────────┐
echo  │  [8] Ejecutar Seguimiento Proactivo                       │
echo  │  [9] Ver Reporte de Agentes                               │
echo  │  [10] Crear Conversación de Prueba                        │
echo  └────────────────────────────────────────────────────────────┘
echo.
echo  ┌─ UTILIDADES ───────────────────────────────────────────────┐
echo  │  [11] Abrir Admin en Navegador                            │
echo  │  [12] Ver Conversaciones                                  │
echo  │  [13] Ver Plantillas de Ejemplo                           │
echo  │  [14] Ver Documentación                                   │
echo  └────────────────────────────────────────────────────────────┘
echo.
echo  [0] Salir
echo.
echo ════════════════════════════════════════════════════════════════════
echo.
set /p opcion="Selecciona una opción (0-14): "

if "%opcion%"=="1" goto INICIAR_COMPLETO
if "%opcion%"=="2" goto SOLO_DJANGO
if "%opcion%"=="3" goto DETENER_SISTEMA
if "%opcion%"=="4" goto DIAGNOSTICO
if "%opcion%"=="5" goto MIGRACIONES
if "%opcion%"=="6" goto BACKUP
if "%opcion%"=="7" goto TEST_VIDEOS
if "%opcion%"=="8" goto SEGUIMIENTO
if "%opcion%"=="9" goto REPORTE_AGENTES
if "%opcion%"=="10" goto CONVERSACION_PRUEBA
if "%opcion%"=="11" goto ABRIR_ADMIN
if "%opcion%"=="12" goto VER_CONVERSACIONES
if "%opcion%"=="13" goto VER_PLANTILLAS
if "%opcion%"=="14" goto DOCUMENTACION
if "%opcion%"=="0" goto SALIR

echo.
echo ❌ Opción inválida. Intenta de nuevo.
timeout /t 2 /nobreak >nul
goto MENU_PRINCIPAL

REM ================================================================
REM   1. INICIAR SISTEMA COMPLETO
REM ================================================================
:INICIAR_COMPLETO
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🚀 Iniciando Sistema Completo...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"

echo [1/4] Activando entorno virtual...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error al activar entorno virtual
    pause
    goto MENU_PRINCIPAL
)
echo ✅ Entorno virtual activado

echo.
echo [2/4] Aplicando migraciones...
python manage.py migrate
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error al aplicar migraciones
    pause
    goto MENU_PRINCIPAL
)
echo ✅ Migraciones aplicadas

echo.
echo [3/4] Iniciando servidor Django en segundo plano...
start "Django Server" cmd /k "cd /d "%~dp0" && .venv\Scripts\activate.bat && python manage.py runserver"
timeout /t 3 /nobreak >nul
echo ✅ Servidor Django iniciado

echo.
echo [4/4] Iniciando Ngrok...
start "Ngrok" cmd /k "ngrok http 8000"
timeout /t 3 /nobreak >nul
echo ✅ Ngrok iniciado

echo.
echo ════════════════════════════════════════════════════════════════════
echo ✅ SISTEMA INICIADO CORRECTAMENTE
echo ════════════════════════════════════════════════════════════════════
echo.
echo 📌 Accesos:
echo    - Admin Local: http://127.0.0.1:8000/admin/
echo    - Ngrok: Revisa la ventana de Ngrok para la URL pública
echo.
echo 💡 Configura el webhook en Twilio con la URL de Ngrok:
echo    https://tu-url-ngrok.ngrok.io/webhook/whatsapp/
echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   2. SOLO DJANGO
REM ================================================================
:SOLO_DJANGO
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🐍 Iniciando Solo Django...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"

call .venv\Scripts\activate.bat
python manage.py migrate
python manage.py runserver

pause
goto MENU_PRINCIPAL

REM ================================================================
REM   3. DETENER SISTEMA
REM ================================================================
:DETENER_SISTEMA
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🛑 Deteniendo Sistema...
echo ════════════════════════════════════════════════════════════════════
echo.

echo [1/2] Deteniendo Django...
taskkill /F /FI "WINDOWTITLE eq Django Server*" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Django detenido
) else (
    echo ℹ️ Django no estaba corriendo
)

echo.
echo [2/2] Deteniendo Ngrok...
taskkill /F /IM ngrok.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Ngrok detenido
) else (
    echo ℹ️ Ngrok no estaba corriendo
)

echo.
echo ════════════════════════════════════════════════════════════════════
echo ✅ Sistema detenido
echo ════════════════════════════════════════════════════════════════════
echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   4. DIAGNÓSTICO
REM ================================================================
:DIAGNOSTICO
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🔍 DIAGNÓSTICO DEL SISTEMA
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo ┌─ 1. DJANGO ──────────────────────────────────────────────────┐
python manage.py check --deploy
echo └──────────────────────────────────────────────────────────────┘
echo.

echo ┌─ 2. NGROK ───────────────────────────────────────────────────┐
powershell -Command "Get-Process | Where-Object {$_.ProcessName -like '*ngrok*'} | Format-Table -AutoSize" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Ngrok NO está corriendo
) else (
    echo ✅ Ngrok está corriendo
)
echo └──────────────────────────────────────────────────────────────┘
echo.

echo ┌─ 3. VARIABLES DE ENTORNO ────────────────────────────────────┐
if exist .env (
    echo ✅ Archivo .env existe
    findstr /C:"TWILIO_ACCOUNT_SID" .env >nul && echo    ✅ TWILIO_ACCOUNT_SID configurada || echo    ❌ TWILIO_ACCOUNT_SID NO configurada
    findstr /C:"TWILIO_AUTH_TOKEN" .env >nul && echo    ✅ TWILIO_AUTH_TOKEN configurada || echo    ❌ TWILIO_AUTH_TOKEN NO configurada
    findstr /C:"OPENAI_API_KEY" .env >nul && echo    ✅ OPENAI_API_KEY configurada || echo    ❌ OPENAI_API_KEY NO configurada
) else (
    echo ❌ Archivo .env NO existe
)
echo └──────────────────────────────────────────────────────────────┘
echo.

echo ┌─ 4. BASE DE DATOS ───────────────────────────────────────────┐
if exist db.sqlite3 (
    echo ✅ Base de datos existe
    python manage.py showmigrations --list | find "[ ]" >nul
    if %ERRORLEVEL% EQU 0 (
        echo ⚠️ Hay migraciones pendientes
    ) else (
        echo ✅ Todas las migraciones aplicadas
    )
) else (
    echo ❌ Base de datos NO existe
)
echo └──────────────────────────────────────────────────────────────┘
echo.

echo ┌─ 5. VIDEOS MULTIMEDIA ───────────────────────────────────────┐
python manage.py shell -c "from core.models import Modulo; total=Modulo.objects.count(); con_video=Modulo.objects.exclude(video_archivo='').exclude(video_url='').count(); print(f'Módulos: {total} | Con video: {con_video}')" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Sistema de videos configurado
) else (
    echo ⚠️ Ejecuta opción [7] para verificar videos
)
echo └──────────────────────────────────────────────────────────────┘
echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   5. MIGRACIONES
REM ================================================================
:MIGRACIONES
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    📦 Aplicando Migraciones...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo [1/2] Creando migraciones...
python manage.py makemigrations
echo.

echo [2/2] Aplicando migraciones...
python manage.py migrate
echo.

echo ✅ Migraciones completadas
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   6. BACKUP
REM ================================================================
:BACKUP
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    💾 Creando Backup...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"

if not exist backups mkdir backups

set fecha=%date:~-4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set fecha=%fecha: =0%

echo Copiando base de datos...
copy db.sqlite3 backups\db_backup_%fecha%.sqlite3

if %ERRORLEVEL% EQU 0 (
    echo ✅ Backup creado: backups\db_backup_%fecha%.sqlite3
) else (
    echo ❌ Error al crear backup
)
echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   7. VERIFICAR VIDEOS
REM ================================================================
:TEST_VIDEOS
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🎥 Verificando Funcionalidad de Videos...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python test_video_funcionalidad.py

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   8. SEGUIMIENTO PROACTIVO
REM ================================================================
:SEGUIMIENTO
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🤖 Ejecutando Seguimiento Proactivo...
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python manage.py seguimiento_estudiantes

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   9. REPORTE AGENTES
REM ================================================================
:REPORTE_AGENTES
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    📊 Reporte de Agentes IA
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python manage.py shell -c "from core.intent_detector import analizar_rendimiento_agentes; analizar_rendimiento_agentes()"

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   10. CONVERSACIÓN DE PRUEBA
REM ================================================================
:CONVERSACION_PRUEBA
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    💬 Crear Conversación de Prueba
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo Creando conversaciones de prueba con los agentes...
echo.

python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production'); django.setup(); from core.models import Estudiante, WhatsappLog; e = Estudiante.objects.first(); print(f'Estudiante: {e.nombre if e else \"Sin estudiantes\"}'); from core.message_handler import procesar_mensaje_entrante; mensajes = ['Hola', 'Quiero aprender sobre café', 'No entiendo nada', 'Gracias']; [procesar_mensaje_entrante(e.telefono, msg, 'twilio') for msg in mensajes if e]; print('✅ Conversaciones creadas')"

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   11. ABRIR ADMIN
REM ================================================================
:ABRIR_ADMIN
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    🌐 Abriendo Admin en Navegador...
echo ════════════════════════════════════════════════════════════════════
echo.

echo Verificando si Django está corriendo...
powershell -Command "$response = try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000' -TimeoutSec 2 -UseBasicParsing } catch { $null }; if ($response) { exit 0 } else { exit 1 }"

if %ERRORLEVEL% EQU 0 (
    echo ✅ Django está corriendo
    start http://127.0.0.1:8000/admin/
    echo ✅ Admin abierto en navegador
) else (
    echo ❌ Django NO está corriendo
    echo 💡 Ejecuta primero la opción [1] o [2]
)

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   12. VER CONVERSACIONES
REM ================================================================
:VER_CONVERSACIONES
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    💬 Verificando Conversaciones
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production'); django.setup(); from core.models import WhatsappLog; logs = WhatsappLog.objects.order_by('-fecha')[:10]; print(f'\n📊 Últimas 10 conversaciones:\n'); [print(f'{i+1}. {log.telefono} - {log.texto[:50]}... ({log.fecha.strftime(\"%%Y-%%m-%%d %%H:%%M\")})') for i, log in enumerate(logs)] if logs.exists() else print('Sin conversaciones aún')"

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   13. VER PLANTILLAS
REM ================================================================
:VER_PLANTILLAS
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    📝 Plantillas de Ejemplo
echo ════════════════════════════════════════════════════════════════════
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production'); django.setup(); from core.models import Plantilla; plantillas = Plantilla.objects.all()[:10]; print(f'\n📋 Plantillas disponibles:\n'); [print(f'{i+1}. {p.nombre}\n   Mensaje: {p.cuerpo_mensaje[:100]}...\n') for i, p in enumerate(plantillas)] if plantillas.exists() else print('Sin plantillas aún')"

echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   14. DOCUMENTACIÓN
REM ================================================================
:DOCUMENTACION
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    📚 DOCUMENTACIÓN DISPONIBLE
echo ════════════════════════════════════════════════════════════════════
echo.
echo  Archivos de documentación:
echo.
if exist README.md echo    ✅ README.md - Documentación general
if exist DOCUMENTACION_COMPLETA.md echo    ✅ DOCUMENTACION_COMPLETA.md - Doc completa del sistema
if exist GUIA_VIDEOS.md echo    ✅ GUIA_VIDEOS.md - Sistema de videos para campo
if exist GUIA_AUDIOS_WHATSAPP.md echo    ✅ GUIA_AUDIOS_WHATSAPP.md - Sistema de audios
if exist SOLUCION_ERRORES.md echo    ✅ SOLUCION_ERRORES.md - Troubleshooting
echo.
echo  Puedes abrir estos archivos en tu editor de código
echo.
pause
goto MENU_PRINCIPAL

REM ================================================================
REM   0. SALIR
REM ================================================================
:SALIR
cls
echo.
echo ════════════════════════════════════════════════════════════════════
echo    👋 Saliendo de EKI MVP
echo ════════════════════════════════════════════════════════════════════
echo.
echo ¿Deseas detener el sistema antes de salir? (S/N)
set /p detener="Respuesta: "

if /i "%detener%"=="S" (
    echo.
    echo Deteniendo sistema...
    taskkill /F /FI "WINDOWTITLE eq Django Server*" 2>nul
    taskkill /F /IM ngrok.exe 2>nul
    echo ✅ Sistema detenido
)

echo.
echo ¡Hasta pronto! 🌾
timeout /t 2 /nobreak >nul
exit
