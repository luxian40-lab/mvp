@echo off
cd /d "%~dp0"
echo.
echo ============================================================
echo    CREANDO CONVERSACION DE PRUEBA
echo ============================================================
echo.
echo Este script creara una conversacion de ejemplo entre
echo un estudiante y el bot de IA para que puedas ver como
echo se muestra en la interfaz de conversaciones.
echo.

.venv\Scripts\python.exe crear_conversacion_prueba.py

echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
