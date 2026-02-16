@echo off
chcp 65001 > nul
color 0A
title 🚀 Sistema Eki - Inicio Completo

echo.
echo ═══════════════════════════════════════════════════════════════
echo          🌱 EKI - SISTEMA COMPLETO DE CHATBOT 🌱
echo ═══════════════════════════════════════════════════════════════
echo.
echo  Este script inicia:
echo  1. Servidor Django (Backend)
echo  2. Ngrok (Túnel para webhooks)
echo.
echo  ⚠️  IMPORTANTE: Necesitas tener ngrok instalado
echo      Descárgalo de: https://ngrok.com/download
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

REM Activar entorno virtual
call .venv\Scripts\activate.bat

echo 📡 Iniciando servidor Django en puerto 8000...
echo.
start "🖥️ Django Server" cmd /k "call .venv\Scripts\activate.bat && python manage.py runserver"

timeout /t 3 /nobreak > nul

echo 🌐 Iniciando ngrok...
echo.
start "🌐 Ngrok Tunnel" cmd /k "ngrok http 8000"

echo.
echo ═══════════════════════════════════════════════════════════════
echo  ✅ Sistema iniciado correctamente
echo ═══════════════════════════════════════════════════════════════
echo.
echo  📋 SIGUIENTES PASOS:
echo.
echo  1. Espera a que ngrok muestre la URL (algo como: https://xxxx.ngrok.io)
echo.
echo  2. Copia esa URL y agrégala en Twilio:
echo     👉 https://console.twilio.com/
echo     👉 Messaging → WhatsApp Sandbox Settings
echo     👉 When a message comes in: https://TU-URL.ngrok.io/webhook/whatsapp/
echo.
echo  3. Prueba enviando un mensaje al número de WhatsApp:
echo     📱 +1 415 523 8886
echo     💬 Prueba: "hola", "aguacate", "ayuda"
echo.
echo  4. Para ver conversaciones:
echo     🌐 http://localhost:8000/admin/conversaciones/
echo     👤 Usuario: admin
echo     🔐 Contraseña: admin123
echo.
echo ═══════════════════════════════════════════════════════════════
echo.
echo  ⚠️  Para DETENER todo: Cierra esta ventana y las ventanas abiertas
echo.
echo ═══════════════════════════════════════════════════════════════
echo.
pause
