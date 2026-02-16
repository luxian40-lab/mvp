@echo off
REM Script para ejecutar seguimiento automático de estudiantes
REM Se ejecutará diariamente para detectar inactivos y enviar motivación

echo.
echo ========================================
echo    SEGUIMIENTO PROACTIVO DE ESTUDIANTES
echo ========================================
echo.

cd /d "%~dp0"

echo [%date% %time%] Activando entorno virtual...
call .venv\Scripts\activate.bat

echo [%date% %time%] Ejecutando seguimiento de estudiantes...
python manage.py seguimiento_estudiantes

echo.
echo [%date% %time%] Seguimiento completado
echo ========================================
echo.

REM Guardar log
echo [%date% %time%] Seguimiento ejecutado >> logs\seguimiento.log

pause
