@echo off
echo ======================================================================
echo                MENU DE GAMIFICACION - EKI
echo ======================================================================
echo.
echo Selecciona una opcion:
echo.
echo 1. Crear/Recrear sistema de gamificacion (badges y configuracion)
echo 2. Agregar datos de ejemplo (estudiantes con progreso)
echo 3. Ver estadisticas de gamificacion
echo 4. Salir
echo.
set /p opcion="Ingresa el numero de tu opcion: "

if "%opcion%"=="1" goto opcion1
if "%opcion%"=="2" goto opcion2
if "%opcion%"=="3" goto opcion3
if "%opcion%"=="4" goto salir
goto menu

:opcion1
echo.
echo ======================================================================
echo       CREANDO SISTEMA DE GAMIFICACION
echo ======================================================================
echo.
.venv\Scripts\python.exe crear_datos_gamificacion.py
echo.
echo Presiona cualquier tecla para volver al menu...
pause >nul
goto menu

:opcion2
echo.
echo ======================================================================
echo       CREANDO DATOS DE EJEMPLO
echo ======================================================================
echo.
.venv\Scripts\python.exe crear_datos_ejemplo_gamificacion.py
echo.
echo Presiona cualquier tecla para volver al menu...
pause >nul
goto menu

:opcion3
echo.
echo ======================================================================
echo       ESTADISTICAS DE GAMIFICACION
echo ======================================================================
echo.
.venv\Scripts\python.exe -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production'); import django; django.setup(); from core.gamificacion import PerfilGamificacion, Badge, BadgeEstudiante; print(f'\nTotal Badges: {Badge.objects.count()}'); print(f'Total Perfiles: {PerfilGamificacion.objects.count()}'); print(f'Badges Otorgados: {BadgeEstudiante.objects.count()}'); top = PerfilGamificacion.objects.order_by('-puntos_totales')[:5]; print('\nTop 5 Estudiantes:'); [print(f'  {i+1}. {p.estudiante.nombre}: {p.puntos_totales} pts (Nivel {p.nivel})') for i, p in enumerate(top)]"
echo.
echo Presiona cualquier tecla para volver al menu...
pause >nul
goto menu

:salir
echo.
echo Saliendo...
exit /b

:menu
cls
goto :eof
