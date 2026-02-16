═══════════════════════════════════════════════════════════
  EKI - SISTEMA EDUCATIVO AGRÍCOLA - GUÍA RÁPIDA
═══════════════════════════════════════════════════════════

🚀 INICIO RÁPIDO (TODOS LOS DÍAS)
═══════════════════════════════════════════════════════════

1. Doble clic en:  iniciar_eki.bat
   
   ✅ Esto abre 2 ventanas:
      - Servidor Django (puerto 8000)
      - Ngrok (túnel público)

2. Espera 10 segundos

3. Copia la URL de ngrok:
   https://xxxx-xxxx-xxxx.ngrok-free.app

4. Ve a Twilio Console:
   https://console.twilio.com/
   
   Configuración → WhatsApp → Sandbox Settings
   Webhook URL: [PEGA_LA_URL_DE_NGROK]/webhook/whatsapp/

5. Accede al admin:
   http://localhost:8000/admin
   Usuario: admin
   Contraseña: admin123


🛑 APAGAR TODO
═══════════════════════════════════════════════════════════

Doble clic en:  detener_eki.bat


📱 PROBAR EL CHATBOT
═══════════════════════════════════════════════════════════

Envía desde WhatsApp al número Twilio:
+1 415 523 8886

Prueba estos mensajes:
- "hola"          → Menú principal
- "ver cursos"    → Lista de cursos disponibles
- "continuar"     → Seguir curso actual
- "listo"         → Completar módulo (Tutor IA valida)
- "progreso"      → Ver avance y puntos
- "ayuda"         → Ayuda (2 veces = ticket soporte)
- "menú"          → Volver al inicio


🎓 FLUJO EDUCATIVO
═══════════════════════════════════════════════════════════

Estudiante dice "listo" al terminar un módulo:
→ Módulo 0: Se completa directo (introductorio)
→ Módulo 1+: Tutor IA hace una pregunta de comprensión
   → Si aprueba: +60 pts (50 módulo + 10 bonus IA)
   → Si no aprueba: puede reintentar


🆘 SOPORTE AUTOMÁTICO
═══════════════════════════════════════════════════════════

Cuando un estudiante necesita ayuda:
1ª vez "ayuda"  → Muestra comandos disponibles
2ª vez "ayuda"  → Crea ticket de soporte automático

Los tickets se ven en:
→ Admin → Solicitudes de Soporte

También se activa con frases como:
"necesito ayuda", "soporte", "urgente", "emergencia"
→ IA empática responde primero
→ Si persiste → ticket + notificación por email


🤖 INTELIGENCIA ARTIFICIAL
═══════════════════════════════════════════════════════════

Tutor IA (GPT-4o-mini):
→ Valida comprensión de módulos con método sandwich
→ Evalúa respuestas y da feedback personalizado

Chat IA (GPT-3.5-turbo):
→ Responde preguntas de agricultura
→ Fallback a Cohere si OpenAI falla

IA Empática:
→ Responde con empatía antes de escalar a soporte


📊 PANELES DE ADMINISTRACIÓN
═══════════════════════════════════════════════════════════

Panel Admin: http://localhost:8000/admin

Paneles principales:
- 💬 Conversaciones   → Ver chats de cada estudiante
- 📊 Dashboard        → Estadísticas generales
- 👨‍🎓 Estudiantes      → Gestionar estudiantes
- 📚 Cursos/Módulos   → Contenido educativo
- 🎮 Gamificación     → Puntos, niveles, badges
- 🎨 Certificados     → Plantillas y certificados
- 🆘 Soporte          → Tickets de ayuda
- 📢 Campañas         → Envíos masivos WhatsApp
- 📋 Primera vez      → Documentación del equipo


🎮 GAMIFICACIÓN
═══════════════════════════════════════════════════════════

Puntos:
+50 pts  → Completar módulo
+10 pts  → Respuesta correcta Tutor IA
+200 pts → Completar curso

Niveles: 🌱→🌿→🍃→🌾→🌳→🌲→🎋→🌺→💎→👑
Cada nivel = 100 puntos

Badges por completar cursos y racha de estudio.


🎨 CERTIFICADOS
═══════════════════════════════════════════════════════════

Dos modos de generación:
1. PDF automático → ReportLab con bordes, QR, datos
2. Imagen personalizada → Subir imagen de fondo
   en PlantillaCertificado, se superpone nombre/curso

Admin → Plantillas de Certificados → Subir imagen_fondo


⚙️ TROUBLESHOOTING
═══════════════════════════════════════════════════════════

❌ Puerto 8000 ocupado:
   → Ejecuta: detener_eki.bat
   → Luego: iniciar_eki.bat

❌ Ngrok no funciona:
   → Verifica que ngrok.exe esté en la carpeta raíz

❌ Webhook no recibe mensajes:
   → Verifica URL en Twilio
   → Debe ser: https://xxxxx.ngrok-free.app/webhook/whatsapp/
   → NO olvides el "/webhook/whatsapp/" al final

❌ Error de Python:
   → Abre PowerShell en la carpeta
   → Ejecuta: .\.venv\Scripts\python.exe manage.py runserver

❌ Videos no se envían:
   → Verificar que el módulo tiene video_archivo o video_url
   → Verificar permisos públicos en S3


═══════════════════════════════════════════════════════════
  ¿DUDAS? Revisa la documentación en Admin → Primera vez
═══════════════════════════════════════════════════════════
