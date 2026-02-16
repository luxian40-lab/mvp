@echo off
REM Menu principal para gestionar el sistema de agentes IA

:menu
cls
echo.
echo ========================================
echo    SISTEMA DE AGENTES IA - EKI
echo    (Estilo Huaku)
echo ========================================
echo.
echo  1. Iniciar servidor Eki
echo  2. Detener servidor Eki
echo.
echo  3. Ejecutar seguimiento de estudiantes
echo  4. Ver reporte de agentes
echo  5. Programar seguimiento automático
echo.
echo  6. Ver guía completa
echo  7. Salir
echo.
echo ========================================
echo.

set /p opcion="Selecciona una opción (1-7): "

if "%opcion%"=="1" goto iniciar
if "%opcion%"=="2" goto detener
if "%opcion%"=="3" goto seguimiento
if "%opcion%"=="4" goto reporte
if "%opcion%"=="5" goto programar
if "%opcion%"=="6" goto guia
if "%opcion%"=="7" goto salir

echo.
echo Opción inválida. Presiona una tecla para continuar...
pause >nul
goto menu

:iniciar
echo.
echo Iniciando servidor...
call iniciar_eki.bat
goto menu

:detener
echo.
echo Deteniendo servidor...
call detener_eki.bat
goto menu

:seguimiento
echo.
call ejecutar_seguimiento.bat
goto menu

:reporte
echo.
call ver_reporte_agentes.bat
goto menu

:programar
echo.
echo NOTA: Requiere permisos de administrador
echo.
powershell -Command "Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0programar_seguimiento.ps1\"' -Verb RunAs"
echo.
echo Proceso iniciado en ventana de administrador...
pause
goto menu

:guia
echo.
echo Abriendo guía...
start GUIA_AGENTES_IA.md
goto menu

:salir
echo.
echo Saliendo...
exit
