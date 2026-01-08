"""
Detector de intents para WhatsApp - Agro Colombiano.
Identifica la intención del usuario basado en palabras clave o patrones.
"""
import re


def detect_intent(mensaje: str) -> str:
    """
    Detecta la intención del mensaje del usuario.
    
    Intents:
    - 'saludo': hola, buenos días, qué tal, etc.
    - 'progreso': progreso, avance, cómo voy, etc.
    - 'tareas': tareas, cursos, lecciones, qué hacer, etc.
    - 'ayuda': ayuda, help, no entiendo, etc.
    - 'cafe': preguntas sobre cultivo de café
    - 'cacao': preguntas sobre cultivo de cacao
    - 'aguacate': preguntas sobre cultivo de aguacate
    - 'ganaderia': preguntas sobre ganadería
    - 'opcion_1': "1" → progreso
    - 'opcion_2': "2" → cursos/tareas
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
    
    # Detectar números inválidos (dos dígitos, números > 9, o múltiples números)
    if re.match(r'^\s*\d{2,}\s*$', texto_limpio) or re.match(r'^\s*[0-9]+[0-9]+\s*$', texto_limpio):
        return 'numero_invalido'
    
    # Opciones numéricas del menú (prioritarias: 1, 2, 3)
    if re.match(r'^\s*1\s*$', texto_limpio):
        return 'opcion_1'
    if re.match(r'^\s*2\s*$', texto_limpio):
        return 'opcion_2'
    if re.match(r'^\s*3\s*$', texto_limpio):
        return 'opcion_3'
    
    # Números 4-9 para inscripción en cursos
    if re.match(r'^\s*[4-9]\s*$', texto_limpio):
        return 'inscribir_curso'
    
    # Saludos (SOLO si es EXACTAMENTE un saludo, no parte de una frase)
    palabras_saludo = ['hola', 'buenos días', 'buenas noches', 'buenas tardes', 'qué tal', 'hi', 'hey', 'buenas']
    # Verificar si el mensaje ES SOLO el saludo (no parte de una pregunta)
    if texto_limpio in palabras_saludo or texto_limpio.startswith('hola ') and len(texto_limpio.split()) <= 3:
        return 'saludo'
    
    # Menú / Inicio - volver al menú principal
    if texto_limpio in ['menu', 'menú', 'inicio', 'volver', 'regresar', 'principal', 'start']:
        return 'saludo'
    
    # Progreso (comandos específicos)
    if texto_limpio in ['progreso', 'avance', 'cómo voy', 'como voy', 'mi avance', 'mi progreso', 'cuánto he avanzado', 'cuanto he avanzado']:
        return 'progreso'
    
    # Tareas/Cursos/Lecciones (solo comandos directos)
    if texto_limpio in ['tareas', 'cursos', 'curso', 'lecciones', 'lección', 'actividades', 'qué hacer', 'que hacer', 'clases', 'clase', 'modulos', 'módulos', 'ver tareas', 'mis tareas']:
        return 'tareas'
    
    # Ayuda (solo comandos directos)
    if texto_limpio in ['ayuda', 'help', 'ayudame', 'ayúdame', 'no sé', 'no se', 'apoyo']:
        return 'ayuda'
    
    # NOTA: Removidos intents de café, cacao, aguacate individuales
    # Ahora solo se usan cursos a través de "ver cursos" e inscripción
    # Preguntas sobre cultivos van directo a IA
    
    # ========== SISTEMA DE CURSOS ==========
    
    # Ver cursos disponibles
    palabras_ver_cursos = ['ver cursos', 'cursos disponibles', 'que cursos hay', 'listar cursos', 'mostrar cursos']
    if any(p in texto_limpio for p in palabras_ver_cursos):
        return 'ver_cursos'
    
    # Inscribirse en curso: "tomar 1", "inscribir 2", o números solos (ya detectado arriba)
    palabras_inscripcion = ['inscribir', 'inscribirme', 'tomar curso', 'empezar curso', 'iniciar curso', 'quiero curso']
    if any(p in texto_limpio for p in palabras_inscripcion) or re.match(r'^(tomar|inscribir)\s*\d+$', texto_limpio):
        return 'inscribir_curso'
    
    # Continuar con lección actual
    # También incluye "listo" y "siguiente" para simplificar
    palabras_continuar = [
        'continuar', 'siguiente', 'proximo', 'próximo', 'seguir', 'listo', 'ok', 'dale', 'sigue', 'avanzar',
        'continuar curso', 'seguir curso', 'sigamos', 'seguimos', 'continuar con', 'seguir con',
        'volver al curso', 'retomar curso', 'retomar', 'donde quede', 'donde quedé', 'donde iba',
        'mi curso', 'al curso', 'con el curso', 'mi lección', 'mi leccion'
    ]
    if any(palabra in texto_limpio for palabra in palabras_continuar):
        return 'continuar_leccion'
    
    # Módulos específicos (1-5)
    if re.match(r'^(modulo|módulo)\s*[1-5]$', texto_limpio):
        return 'modulo_especifico'
    
    # Tomar examen
    palabras_examen = ['examen', 'evaluación', 'evaluacion', 'prueba', 'test', 'tomar examen']
    if any(p in texto_limpio for p in palabras_examen):
        return 'iniciar_examen'
    
    # Respuesta de examen (detecta cuando está en modo examen)
    # Esta lógica se manejará en el message_handler con contexto
    
    # Ver mi progreso en cursos
    palabras_mi_progreso = ['mi progreso', 'mis cursos', 'mi avance', 'que he completado']
    if any(p in texto_limpio for p in palabras_mi_progreso):
        return 'mi_progreso_cursos'
    
    # Ver ranking de gamificación
    palabras_ranking = ['ranking', 'leaderboard', 'tabla', 'posiciones', 'top', 'mejores', 'lideres', 'líderes']
    if any(p in texto_limpio for p in palabras_ranking):
        return 'ver_ranking'
    
    # Cambiar nombre
    palabras_cambiar_nombre = ['cambiar nombre', 'editar nombre', 'modificar nombre', 'actualizar nombre', 'mi nombre es', 'me llamo', 'cambiar mi nombre']
    if any(p in texto_limpio for p in palabras_cambiar_nombre):
        return 'cambiar_nombre'
    
    return 'desconocido'
