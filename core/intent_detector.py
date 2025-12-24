"""
Detector de intents simple para WhatsApp.
Identifica la intención del usuario basado en palabras clave o patrones.
"""
import re


def detect_intent(mensaje: str) -> str:
    """
    Detecta la intención del mensaje del usuario.
    
    Intents:
    - 'saludo': hola, buenos días, qué tal, etc.
    - 'progreso': progreso, avance, cómo voy, etc.
    - 'tareas': tareas, actividades, qué hacer, siguiente, etc.
    - 'ayuda': ayuda, help, no entiendo, etc.
    - 'opcion_1': "1" → progreso
    - 'opcion_2': "2" → tareas
    - 'opcion_3': "3" → ayuda
    - 'desconocido': no coincide con nada
    
    Args:
        mensaje: texto del usuario
    
    Returns:
        intent (str): categoría detectada
    """
    
    if not mensaje:
        return 'desconocido'
    
    texto_limpio = mensaje.lower().strip()
    
    # Opciones numéricas (prioritarias)
    if re.match(r'^\s*1\s*$', texto_limpio):
        return 'opcion_1'
    if re.match(r'^\s*2\s*$', texto_limpio):
        return 'opcion_2'
    if re.match(r'^\s*3\s*$', texto_limpio):
        return 'opcion_3'
    
    # Saludos
    palabras_saludo = ['hola', 'buenos días', 'buenas noches', 'buenas tardes', 'qué tal', 'holap', 'hi', 'hey', 'hey!']
    if any(p in texto_limpio for p in palabras_saludo):
        return 'saludo'
    
    # Progreso
    palabras_progreso = ['progreso', 'avance', 'cómo voy', 'como voy', 'mi avance', 'mi progreso', 'cuánto he avanzado', 'cuanto he avanzado']
    if any(p in texto_limpio for p in palabras_progreso):
        return 'progreso'
    
    # Tareas
    palabras_tareas = ['tareas', 'actividades', 'qué hacer', 'que hacer', 'siguiente', 'siguiente tarea', 'próximo', 'proximo', 'cosas', 'debo hacer', 'trabajo']
    if any(p in texto_limpio for p in palabras_tareas):
        return 'tareas'
    
    # Ayuda
    palabras_ayuda = ['ayuda', 'help', 'no entiendo', 'explica', 'no comprendo', 'ayudame', 'ayúdame', 'no sé', 'no se']
    if any(p in texto_limpio for p in palabras_ayuda):
        return 'ayuda'
    
    return 'desconocido'
