@echo off
title Eki - Deteniendo Sistema
color 0C
echo.
echo ============================================
echo    EKI - Deteniendo Servicios
echo ============================================
echo.

echo Deteniendo servidor Django...
taskkill /F /FI "WINDOWTITLE eq Eki - Django Server*" >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo Deteniendo ngrok...
taskkill /F /FI "WINDOWTITLE eq Eki - Ngrok Tunnel*" >nul 2>&1
taskkill /F /IM ngrok.exe >nul 2>&1

echo.
echo ============================================
echo    SISTEMA DETENIDO
echo ============================================
echo.
timeout /t 2 /nobreak >nul
