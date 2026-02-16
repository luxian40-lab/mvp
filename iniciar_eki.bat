@echo off
title Eki MVP - Menu Principal
color 0B

:MENU
cls
echo.
echo ================================================================
echo    EKI MVP - Sistema de Mensajeria Educativa para Campesinos
echo ================================================================
echo.
echo  [1] Iniciar Sistema Completo (Django + Ngrok)
echo  [2] Solo Django (desarrollo local)
echo  [3] Ver Plantillas de Ejemplo
echo  [4] Abrir Admin en Navegador
echo  [5] Crear Backup de Base de Datos
echo  [6] Ver Documentacion
echo  [7] Ejecutar Seguimiento Proactivo
echo  [8] Ver Reporte de Agentes IA
echo  [9] Salir
echo.
echo ================================================================
echo.
set /p opcion="Selecciona una opcion (1-9): "

if "%opcion%"=="1" goto INICIAR_COMPLETO
if "%opcion%"=="2" goto SOLO_DJANGO
if "%opcion%"=="3" goto VER_PLANTILLAS
if "%opcion%"=="4" goto ABRIR_ADMIN
if "%opcion%"=="5" goto BACKUP
if "%opcion%"=="6" goto DOCUMENTACION
if "%opcion%"=="7" goto SEGUIMIENTO
if "%opcion%"=="8" goto REPORTE_AGENTES
if "%opcion%"=="9" goto SALIR

echo.
echo Opcion invalida. Intenta de nuevo.
timeout /t 2 /nobreak >nul
goto MENU

:INICIAR_COMPLETO
cls
echo.
echo ============================================
echo    Iniciando Sistema Completo...
echo ============================================
echo.
cd /d "%~dp0"

echo [1/2] Iniciando servidor Django...
start "Eki - Django Server" cmd /k ".\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak >nul

echo [2/2] Iniciando ngrok tunnel...
start "Eki - Ngrok Tunnel" cmd /k "ngrok http 8000"
timeout /t 2 /nobreak >nul

echo.
echo ============================================
echo    SISTEMA INICIADO CORRECTAMENTE
echo ============================================
echo.
echo  Admin:   http://localhost:8000/admin
echo  Usuario: admin
echo  Pass:    admin123
echo.
echo  ACCESOS RAPIDOS:
echo  - Plantillas:  /admin/core/plantilla/
echo  - Estudiantes: /admin/core/estudiante/
echo  - Reportes:    Seleccionar + Exportar Excel
echo.
echo  Ngrok: Copia URL https://xxxxx.ngrok-free.app
echo         y configurala en Twilio webhook
echo.
echo ============================================
echo.
pause
goto MENU

:SOLO_DJANGO
cls
echo.
echo ============================================
echo    Iniciando Django (solo local)...
echo ============================================
echo.
cd /d "%~dp0"
start "Eki - Django Server" cmd /k ".\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak >nul

echo.
echo  Django:  http://localhost:8000/admin
echo  Usuario: admin
echo.
echo  Presiona cualquier tecla para volver al menu
pause >nul
goto MENU

:VER_PLANTILLAS
cls
echo.
echo ============================================
echo    Plantillas de Ejemplo
echo ============================================
echo.
cd /d "%~dp0"
.\.venv\Scripts\python.exe demo_plantillas.py
echo.
pause
goto MENU

:ABRIR_ADMIN
cls
echo.
echo Abriendo Admin en navegador...
start http://localhost:8000/admin
timeout /t 2 /nobreak >nul
goto MENU

:BACKUP
cls
echo.
echo ============================================
echo    Creando Backup de Base de Datos
echo ============================================
echo.
cd /d "%~dp0"

if not exist "backups" mkdir backups

set FECHA=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set FECHA=%FECHA: =0%

copy db.sqlite3 "backups\db_backup_%FECHA%.sqlite3"

echo.
echo  Backup creado: backups\db_backup_%FECHA%.sqlite3
echo.
echo  Presiona cualquier tecla para continuar
pause >nul
goto MENU

:DOCUMENTACION
cls
echo.
echo ============================================
echo    Documentacion Disponible
echo ============================================
echo.
echo  [1] Guia Completa de Plantillas y Reportes
echo  [2] Guia Rapida de Referencia
echo  [3] Checklist para Cliente
echo  [4] Resumen de Mejoras
echo  [5] Guia de Agentes IA
echo  [6] Volver al Menu
echo.
set /p doc="Selecciona documento (1-6): "

if "%doc%"=="1" start GUIA_PLANTILLAS_Y_REPORTES.md
if "%doc%"=="2" start GUIA_RAPIDA_ADMIN.md
if "%doc%"=="3" start CHECKLIST_CLIENTE.md
if "%doc%"=="4" start RESUMEN_MEJORAS_PLANTILLAS_REPORTES.md
if "%doc%"=="5" start GUIA_AGENTES_IA.md
if "%doc%"=="6" goto MENU

timeout /t 1 /nobreak >nul
goto DOCUMENTACION

:SEGUIMIENTO
cls
echo.
echo ============================================
echo    Ejecutando Seguimiento Proactivo
echo ============================================
echo.
cd /d "%~dp0"
.\.venv\Scripts\python.exe manage.py seguimiento_estudiantes
echo.
pause
goto MENU

:REPORTE_AGENTES
cls
echo.
echo ============================================
echo    Reporte de Uso de Agentes IA
echo ============================================
echo.
cd /d "%~dp0"
.\.venv\Scripts\python.exe manage.py reporte_agentes
echo.
pause
goto MENU

:SALIR
cls
echo.
echo Cerrando sistema...
echo.
timeout /t 1 /nobreak >nul
exit
