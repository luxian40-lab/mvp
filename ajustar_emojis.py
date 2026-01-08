"""
Ajuste final de emojis - solo los esenciales
"""

with open('core/response_templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Mantener SOLO emojis de cursos (🍌 🥑 ☕) y algunos clave
# Quitar el resto de decorativos

replacements = [
    # Quitar emojis decorativos que quedaron
    ('━━━━━━━━━━━━━━━━━━━━', '---'),
    ('═══════', '---'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open('core/response_templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Emojis ajustados - solo los esenciales")
