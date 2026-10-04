"""
Detector de intents para WhatsApp - Agro Colombiano.
Identifica la intención del usuario basado en palabras clave o patrones.
"""
import re


def contiene_palabra(texto: str, palabra: str) -> bool:
    """Coincidencia de palabra o frase completa. No usa subcadena."""
    if not texto or not palabra:
        return False
    return re.search(rf'(?<!\w){re.escape(palabra)}(?!\w)', texto) is not None


def _alguna(texto: str, palabras) -> bool:
    return any(contiene_palabra(texto, palabra) for palabra in palabras)


# Tokens de uno a tres caracteres que aparecen dentro de frases normales.
# Solo cuentan si el mensaje tiene como mucho 3 palabras. «no» no es avance.
_CONTINUAR_CORTAS = frozenset({'si', 'sí', 'ok', 'ya', 'va'})
_NEGACIONES_TOKEN = frozenset({'no', 'nunca', 'tampoco', 'ni', 'jamas', 'jamás'})
_OBJETIVOS_AVANCE = frozenset({
    'seguir', 'continuar', 'sigo', 'listo', 'sigue', 'sigamos', 'seguimos',
})
_DUDA = frozenset({'se', 'sé'})
_SI_DUDA = frozenset({'si', 'sí'})


def _tokens_con_clausula(texto: str) -> list[tuple[str, int]]:
    """Palabras y el número de cláusula. La coma, el punto y el punto y coma cortan."""
    piezas: list[tuple[str, int]] = []
    clausula = 0
    for match in re.finditer(r'\w+|[,;.]', texto, flags=re.UNICODE):
        tok = match.group()
        if tok in ',;.':
            clausula += 1
            continue
        piezas.append((tok, clausula))
    return piezas


def _prefijo_niega(piezas: list[tuple[str, int]], indice: int) -> bool:
    """Negación en las 2 palabras anteriores, en la misma cláusula.

    «no sé si» justo antes del verbo también niega: «no» queda en la tercera
    posición y el test de esa frase pide que no avance.
    """
    clausula = piezas[indice][1]
    mismos = [tok for tok, numero in piezas[:indice] if numero == clausula]
    if any(tok in _NEGACIONES_TOKEN for tok in mismos[-2:]):
        return True
    tres = mismos[-3:]
    return (
        len(tres) == 3
        and tres[0] == 'no'
        and tres[1] in _DUDA
        and tres[2] in _SI_DUDA
    )


def _ocurrencia_negada(texto: str, frase: str) -> bool:
    """True si cada aparición de la frase está negada, o es un token corto
    pegado a un verbo de avance negado en la misma cláusula.
    """
    objetivo = re.findall(r'\w+', frase, flags=re.UNICODE)
    piezas = _tokens_con_clausula(texto)
    if not objetivo or not piezas:
        return False
    n = len(objetivo)
    tokens = [tok for tok, _ in piezas]
    alguna = False
    for i in range(len(tokens) - n + 1):
        if tokens[i:i + n] != objetivo:
            continue
        if any(piezas[i + k][1] != piezas[i][1] for k in range(n)):
            continue
        alguna = True
        if _prefijo_niega(piezas, i):
            continue
        if objetivo[0] in _CONTINUAR_CORTAS and _corto_junto_a_verbo_negado(piezas, i):
            continue
        return False
    return alguna


def _corto_junto_a_verbo_negado(piezas: list[tuple[str, int]], indice: int) -> bool:
    clausula = piezas[indice][1]
    for j in range(indice + 1, min(indice + 3, len(piezas))):
        if piezas[j][1] != clausula:
            break
        if piezas[j][0] in _OBJETIVOS_AVANCE and _prefijo_niega(piezas, j):
            return True
    return False


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
    
    # ========== PRIORIDAD ABSOLUTA: NÚMEROS ==========
    # Cualquier número solo (1-9) siempre es una opción de menú
    # NO importa el contexto - esto evita ambigüedades en sandbox
    
    if re.match(r'^\s*1\s*$', texto_limpio):
        return 'opcion_1'  # Siempre: progreso o primera opción de lista
    
    if re.match(r'^\s*2\s*$', texto_limpio):
        return 'opcion_2'  # Siempre: ayuda o segunda opción
    
    if re.match(r'^\s*3\s*$', texto_limpio):
        return 'opcion_3'  # Siempre: menú o tercera opción
    
    # Números 4-9: opciones de listas (cursos, módulos, etc.)
    if re.match(r'^\s*[4-9]\s*$', texto_limpio):
        return 'opcion_numerica'  # Genérico: se interpreta según contexto
    
    # Números de 2+ dígitos o 0: inválidos
    if re.match(r'^\s*\d{2,}\s*$', texto_limpio) or texto_limpio == '0':
        return 'numero_invalido'
    
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
    
    # Ayuda / PQRS / Soporte (todo unificado)
    if texto_limpio in ['ayuda', 'help', 'ayudame', 'ayúdame', 'no sé', 'no se', 'apoyo',
                         'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud', 'petición', 'peticion',
                         'necesito ayuda', 'necesito soporte']:
        return 'opcion_3'
    if re.match(r'^ayuda\b', texto_limpio):
        return 'opcion_3'
    
    # NOTA: Removidos intents de café, cacao, aguacate individuales
    # Ahora solo se usan cursos a través de "ver cursos" e inscripción
    # Preguntas sobre cultivos van directo a IA
    
    # ========== SISTEMA DE CURSOS ==========
    
    # Ver cursos disponibles
    palabras_ver_cursos = ['ver cursos', 'cursos disponibles', 'que cursos hay', 'listar cursos', 'mostrar cursos']
    if _alguna(texto_limpio, palabras_ver_cursos):
        return 'ver_cursos'
    
    # Inscribirse en curso: "tomar 1", "inscribir 2", o números solos (ya detectado arriba)
    palabras_inscripcion = ['inscribir', 'inscribirme', 'tomar curso', 'empezar curso', 'iniciar curso', 'quiero curso']
    if _alguna(texto_limpio, palabras_inscripcion) or re.match(r'^(tomar|inscribir)\s*\d+$', texto_limpio):
        return 'inscribir_curso'
    
    # Continuar con lección actual
    # También incluye "listo", "si", "confirmar" y variantes para simplificar
    palabras_continuar = [
        'continuar', 'siguiente', 'proximo', 'próximo', 'seguir', 'listo', 'ok', 'dale', 'sigue', 'avanzar',
        'continuar curso', 'seguir curso', 'sigamos', 'seguimos', 'continuar con', 'seguir con',
        'volver al curso', 'retomar curso', 'retomar', 'donde quede', 'donde quedé', 'donde iba',
        'mi curso', 'al curso', 'con el curso', 'mi lección', 'mi leccion',
        'si', 'sí', 'confirmar', 'confirmo', 'ya', 'claro', 'bueno', 'adelante', 'vamos', 'va',
    ]
    # «si», «ok», «ya» y «va» son ambiguos: solo si el mensaje es corto.
    # Una negación solo anula el verbo si está en las 2 palabras anteriores
    # de la misma cláusula. «no, listo» avanza: la coma deja «listo» solo.
    n_palabras = len(re.findall(r'\w+', texto_limpio, flags=re.UNICODE))
    for palabra in palabras_continuar:
        if palabra in _CONTINUAR_CORTAS and n_palabras > 3:
            continue
        if not contiene_palabra(texto_limpio, palabra):
            continue
        primero = re.findall(r'\w+', palabra, flags=re.UNICODE)[:1]
        if primero and primero[0] in _OBJETIVOS_AVANCE | _CONTINUAR_CORTAS:
            if _ocurrencia_negada(texto_limpio, palabra):
                continue
        return 'continuar_leccion'
    
    # Módulos específicos (1-5)
    if re.match(r'^(modulo|módulo)\s*[1-5]$', texto_limpio):
        return 'modulo_especifico'
    
    # Tomar examen
    palabras_examen = ['examen', 'evaluación', 'evaluacion', 'prueba', 'test', 'tomar examen']
    if _alguna(texto_limpio, palabras_examen):
        return 'iniciar_examen'
    
    # Respuesta de examen (detecta cuando está en modo examen)
    # Esta lógica se manejará en el message_handler con contexto
    
    # Ver mi progreso en cursos
    palabras_mi_progreso = ['mi progreso', 'mis cursos', 'mi avance', 'que he completado']
    if _alguna(texto_limpio, palabras_mi_progreso):
        return 'mi_progreso_cursos'
    
    # Ver ranking de gamificación
    palabras_ranking = ['ranking', 'leaderboard', 'tabla', 'posiciones', 'top', 'mejores', 'lideres', 'líderes']
    if _alguna(texto_limpio, palabras_ranking):
        return 'ver_ranking'
    
    # Cambiar nombre
    palabras_cambiar_nombre = ['cambiar nombre', 'editar nombre', 'modificar nombre', 'actualizar nombre', 'mi nombre es', 'me llamo', 'cambiar mi nombre']
    if _alguna(texto_limpio, palabras_cambiar_nombre):
        return 'cambiar_nombre'
    
    # Corregir datos personales
    palabras_corregir_datos = [
        'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
        'actualizar datos', 'actualizar mis datos', 'editar datos', 'editar mis datos',
        'me equivoqué', 'me equivoque', 'datos incorrectos', 'datos mal',
        'error en mis datos', 'mis datos están mal', 'mis datos estan mal',
        'modificar datos', 'modificar mis datos', 'corregir información',
        'corregir informacion', 'dato equivocado', 'equivoqué',
    ]
    if _alguna(texto_limpio, palabras_corregir_datos):
        return 'corregir_datos'
    
    return 'desconocido'


_AVANCE_CURSO_TRIGGERS = frozenset({'listo', 'continuar'})
# Typos cortos vistos en campo (Yuli: «Listi»). Solo token único.
_AVANCE_CURSO_TYPOS = frozenset({'listi', 'listoo', 'lsito'})


def mensaje_indica_listo(mensaje: str) -> bool:
    """
    True si el usuario pide avanzar con *listo* o *continuar* (mensaje corto y explícito).
    Usado en el gate del curso y en handoffs Darío → facilitadora.
    No usa detect_intent para evitar falsos positivos en prosa larga.
    """
    if not mensaje or not str(mensaje).strip():
        return False
    t = str(mensaje).strip().lower()
    t = re.sub(r'[*_]+', '', t).strip()
    tokens = re.findall(r'\w+', t, flags=re.UNICODE)
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in (_AVANCE_CURSO_TRIGGERS | _AVANCE_CURSO_TYPOS):
        return True
    if len(tokens) <= 4 and any(tok in _AVANCE_CURSO_TRIGGERS for tok in tokens):
        return True
    return False
