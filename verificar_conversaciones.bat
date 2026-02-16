@echo off
cd /d "%~dp0"
echo.
echo ============================================================
echo    VERIFICANDO CONVERSACIONES EN BASE DE DATOS
echo ============================================================
echo.

.venv\Scripts\python.exe verificar_conversaciones.py

echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
