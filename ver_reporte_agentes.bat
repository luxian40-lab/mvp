@echo off
REM Script para ver el reporte de uso de agentes IA

echo.
echo ========================================
echo    REPORTE DE AGENTES IA (Huaku Style)
echo ========================================
echo.

cd /d "%~dp0"

call .venv\Scripts\activate.bat

python manage.py reporte_agentes --detallado

echo.
pause
