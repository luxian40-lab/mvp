"""
Script para simplificar mensajes - quitar emojis excesivos
"""
import re

# Leer archivo
with open('core/response_templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazos para hacer mensajes más naturales
replacements = [
    # Saludo
    ('¡Hola {nombre_usuario}! 🌱 Soy tu tutor agrícola de Eki', 
     'Hola {nombre_usuario}, soy tu tutor agrícola de Eki.'),
    
    ('Estoy aquí para ENSEÑARTE con cursos estructurados de agricultura colombiana.',
     'Estoy aquí para enseñarte agricultura colombiana.'),
    
    ('📚 ¿Qué quieres hacer hoy?', '¿Qué quieres hacer?'),
    
    ('1️⃣  Ver mi progreso en cursos', '1. Ver mi progreso'),
    ('2️⃣  Ver cursos disponibles', '2. Ver cursos disponibles'),
    ('3️⃣  Continuar con mi curso actual', '3. Continuar con mi curso'),
    
    ('Responde con el número o pregúntame directamente 💬', 
     'Responde con el número o escribe tu pregunta.'),
    
    ('💡 También puedes escribir:', 'También puedes escribir:'),
    ('   • "ver cursos" - Lista todos los cursos', '   - "ver cursos" para listar cursos'),
    ('   • "mi progreso" - Ver tu avance', '   - "mi progreso" para ver tu avance'),
    ('   • "continuar" - Seguir con tu lección', '   - "continuar" para seguir'),
    
    # Cambiar nombre
    ('✏️ **Cambiar tu nombre**', 'Para cambiar tu nombre:'),
    ('Para actualizar tu nombre, simplemente escribe:', 'Escribe:'),
    ('`Mi nombre es [Tu Nuevo Nombre]`', 'Mi nombre es [Tu Nombre]'),
    ('💬 Escribe tu nuevo nombre ahora:', ''),
    
    # Confirmación
    ('✅ **Nombre actualizado exitosamente**', 'Nombre actualizado.'),
    ('¡Listo! Ahora te llamaré **{nuevo_nombre}**', 'Ahora te llamaré {nuevo_nombre}.'),
    ('¿Quieres continuar con tus cursos? Escribe:', '¿Quieres continuar?'),
    ('• "continuar" - Seguir con tu lección', 'Escribe "continuar", "ver cursos" o "mi progreso".'),
    ('• "ver cursos" - Ver cursos disponibles', ''),
    ('• "mi progreso" - Ver tu avance', ''),
    
    # Otros emojis comunes
    ('📖 **', ''), 
    ('**', ''),
    ('✅ ', ''),
    ('❌ ', ''),
    ('🎓 ', ''),
    ('📚 ', ''),
    ('🌱 ', ''),
    ('💡 ', ''),
    ('🔹 ', '- '),
    ('📊 ', ''),
    ('🎥 **Video educativo:**', 'Video:'),
]

for old, new in replacements:
    content = content.replace(old, new)

# Guardar
with open('core/response_templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Mensajes simplificados - menos emojis, más lenguaje natural")
