"""
Handler mejorado para Onboarding con captura natural de municipio
y soporte completo para respuestas de audio en evaluaciones
"""


import re
import logging
from django.utils import timezone
from decimal import Decimal

from .models import Estudiante, InteraccionLog
from .audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

# ========================================
# ONBOARDING MEJORADO
# ========================================

# Lista de municipios colombianos más comunes (puedes expandir)
MUNICIPIOS_COLOMBIA = [
    'riosucio', 'supía', 'marmato', 'filadelfia', 'la merced',
    'manizales', 'chinchiná', 'palestina', 'neira', 'villamaría',
    'anserma', 'viterbo', 'risaralda', 'marsella', 'belalcázar',
    'medellín', 'bello', 'itagüí', 'envigado', 'sabaneta',
    'bogotá', 'soacha', 'fusagasugá', 'facatativá', 'zipaquirá',
    'cali', 'palmira', 'buenaventura', 'tuluá', 'jamundí',
    'barranquilla', 'soledad', 'malambo', 'puerto colombia',
    'cartagena', 'turbaco', 'magangué', 'arjona',
    'bucaramanga', 'floridablanca', 'girón', 'piedecuesta',
    'cúcuta', 'villa del rosario', 'los patios', 'el zulia',
    'pereira', 'dosquebradas', 'la virginia', 'santa rosa de cabal',
    'armenia', 'calarcá', 'montenegro', 'la tebaida', 'circasia',
    'ibagué', 'espinal', 'melgar', 'guamo', 'honda',
    'neiva', 'pitalito', 'garzón', 'la plata', 'campoalegre',
    'popayán', 'santander de quilichao', 'puerto tejada', 'piendamó',
    'villavicencio', 'acacías', 'granada', 'san martín', 'puerto lópez',
    'montería', 'cereté', 'lorica', 'sahagún', 'planeta rica',
    'valledupar', 'aguachica', 'bosconia', 'el copey', 'chimichagua',
    'sincelejo', 'corozal', 'sampués', 'tolú', 'san marcos',
    'santa marta', 'ciénaga', 'fundación', 'plato', 'zona bananera',
    'riohacha', 'maicao', 'uribia', 'manaure', 'villanueva',
    'pasto', 'tumaco', 'ipiales', 'tuquerres', 'samaniego',
]

# Departamentos de Colombia
DEPARTAMENTOS_COLOMBIA = {
    'caldas': ['riosucio', 'supía', 'marmato', 'manizales', 'chinchiná', 'palestina', 'neira', 'anserma', 'filadelfia', 'la merced'],
    'antioquia': ['medellín', 'bello', 'itagüí', 'envigado', 'sabaneta', 'rionegro', 'marinilla'],
    'cundinamarca': ['bogotá', 'soacha', 'fusagasugá', 'facatativá', 'zipaquirá', 'chía', 'mosquera'],
    'valle del cauca': ['cali', 'palmira', 'buenaventura', 'tuluá', 'jamundí', 'cartago', 'buga'],
    'atlántico': ['barranquilla', 'soledad', 'malambo', 'puerto colombia', 'sabanalarga'],
    'bolívar': ['cartagena', 'turbaco', 'magangué', 'arjona', 'el carmen de bolívar'],
    'santander': ['bucaramanga', 'floridablanca', 'girón', 'piedecuesta', 'barrancabermeja'],
    'norte de santander': ['cúcuta', 'villa del rosario', 'los patios', 'el zulia', 'ocaña'],
    'risaralda': ['pereira', 'dosquebradas', 'la virginia', 'santa rosa de cabal', 'marsella'],
    'quindío': ['armenia', 'calarcá', 'montenegro', 'la tebaida', 'circasia'],
    'tolima': ['ibagué', 'espinal', 'melgar', 'guamo', 'honda', 'líbano'],
    'huila': ['neiva', 'pitalito', 'garzón', 'la plata', 'campoalegre'],
    'cauca': ['popayán', 'santander de quilichao', 'puerto tejada', 'piendamó', 'patía'],
    'meta': ['villavicencio', 'acacías', 'granada', 'san martín', 'puerto lópez'],
    'córdoba': ['montería', 'cereté', 'lorica', 'sahagún', 'planeta rica'],
    'cesar': ['valledupar', 'aguachica', 'bosconia', 'el copey', 'chimichagua'],
    'sucre': ['sincelejo', 'corozal', 'sampués', 'tolú', 'san marcos'],
    'magdalena': ['santa marta', 'ciénaga', 'fundación', 'plato', 'zona bananera'],
    'la guajira': ['riohacha', 'maicao', 'uribia', 'manaure', 'villanueva'],
    'nariño': ['pasto', 'tumaco', 'ipiales', 'tuquerres', 'samaniego'],
}


def detectar_municipio_en_texto(texto: str) -> tuple:
    """
    Detecta si el texto menciona un municipio colombiano
    
    Returns:
        tuple: (municipio, departamento) o (None, None)
    """
    texto_lower = texto.lower().strip()
    
    # Normalizar texto (quitar tildes y caracteres especiales)
    texto_normalizado = texto_lower
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n'
    }
    for orig, repl in reemplazos.items():
        texto_normalizado = texto_normalizado.replace(orig, repl)
    
    # Buscar municipio
    for municipio in MUNICIPIOS_COLOMBIA:
        if municipio in texto_normalizado:
            # Buscar departamento
            for depto, municipios in DEPARTAMENTOS_COLOMBIA.items():
                if municipio in municipios:
                    return (municipio.title(), depto.title())
            
            # Si no se encuentra departamento, retornar solo municipio
            return (municipio.title(), None)
    
    return (None, None)



def manejar_onboarding_natural(estudiante: Estudiante, mensaje: str) -> tuple:
    """
    Onboarding: 1) habeas data, 2) nombre y tipo doc, 3) guardar, 4) ubicación municipio/ciudad, 5) detalle ubicación.
    Returns: (completado: bool, respuesta: str)
    """
    # Paso 1: Habeas Data (si aplica, puedes personalizar el mensaje legal aquí)
    if estudiante.estado_onboarding == 'inicio' or not estudiante.estado_onboarding:
        estudiante.estado_onboarding = 'habeas_data'
        estudiante.save()
        return (False, "Para continuar, debes aceptar el tratamiento de datos personales (habeas data). ¿Aceptas? Responde SÍ para continuar.")

    if estudiante.estado_onboarding == 'habeas_data':
        if mensaje.strip().lower() in ['si', 'sí', 'acepto', 'de acuerdo', 'ok']:
            estudiante.estado_onboarding = 'esperando_nombre'
            estudiante.save()
            return (False, "¿Cuál es tu nombre completo?")
        return (False, "Por favor, responde SÍ para aceptar el tratamiento de datos personales y continuar.")



    # Paso 2: Nombre, tipo de documento y número de documento (pueden venir juntos)
    if (not estudiante.nombre or not estudiante.tipo_documento or not estudiante.cedula or estudiante.estado_onboarding in ['esperando_nombre', 'esperando_tipo_doc', 'esperando_cedula']):
        tipos = dict(Estudiante.TIPO_DOCUMENTO_CHOICES)
        mensaje_l = mensaje.lower()
        tipo_detectado = None
        for key, val in tipos.items():
            if val.lower() in mensaje_l or key.lower() in mensaje_l:
                tipo_detectado = key
                break
        # Extraer número de documento
        cedula = ''.join(filter(str.isdigit, mensaje))
        # Extraer nombre (todo lo que no sea tipo de doc ni número)
        nombre = mensaje.strip()
        if tipo_detectado:
            nombre = re.sub(rf"\b({tipo_detectado}|{tipos[tipo_detectado]})\b", '', nombre, flags=re.IGNORECASE).strip()
        if cedula:
            nombre = re.sub(rf"\b{cedula}\b", '', nombre).strip()
        # Si los tres presentes
        if tipo_detectado and len(nombre.split()) >= 2 and len(cedula) >= 5:
            estudiante.nombre = nombre
            estudiante.tipo_documento = tipo_detectado
            estudiante.cedula = cedula
            estudiante.estado_onboarding = 'esperando_municipio'
            estudiante.save()
            return (False, "¿En qué municipio o ciudad te encuentras?")
        # Si falta alguno, pedir el que falta
        if not estudiante.nombre or len(nombre.split()) < 2:
            estudiante.estado_onboarding = 'esperando_nombre'
            estudiante.save()
            return (False, "Por favor, dime tu nombre completo (nombre y apellido). Puedes escribirlo junto con tu tipo de documento y número si lo prefieres.")
        if not estudiante.tipo_documento:
            estudiante.estado_onboarding = 'esperando_tipo_doc'
            estudiante.save()
            opciones = ', '.join([f"{v} ({k})" for k, v in tipos.items()])
            return (False, f"¿Cuál es tu tipo de documento? Opciones: {opciones}")
        if not estudiante.cedula or len(cedula) < 5:
            estudiante.estado_onboarding = 'esperando_cedula'
            estudiante.save()
            return (False, "Por favor, indícame tu número de documento (solo números, mínimo 5 dígitos). Puedes escribirlo junto con tu nombre y tipo de documento si lo prefieres.")

    # Paso 5: Municipio/ciudad
    if (not estudiante.municipio or estudiante.estado_onboarding == 'esperando_municipio'):
        municipio, _ = detectar_municipio_en_texto(mensaje)
        if municipio:
            estudiante.municipio = municipio
            estudiante.estado_onboarding = 'esperando_ubicacion_detalle'
            estudiante.save()
            return (False, "¿Puedes darme un detalle adicional de tu ubicación? (vereda, barrio, etc.)")
        estudiante.estado_onboarding = 'esperando_municipio'
        estudiante.save()
        return (False, "No logré identificar tu municipio o ciudad. Por favor, escríbelo nuevamente.")

    # Paso 6: Ubicación detalle
    if (not estudiante.ubicacion_detalle or estudiante.estado_onboarding == 'esperando_ubicacion_detalle'):
        ubicacion = mensaje.strip()
        if len(ubicacion) >= 3:
            estudiante.ubicacion_detalle = ubicacion
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            return (True, f"¡Registro completo! 🎉\n\nBienvenido/a, {estudiante.nombre}. Ya podemos empezar con los cursos. ¿Qué te gustaría aprender hoy?")
        estudiante.estado_onboarding = 'esperando_ubicacion_detalle'
        estudiante.save()
        return (False, "Por favor, indícame un detalle adicional de tu ubicación (vereda, barrio, etc.).")

    # Si ya está completo
    return (True, None)


# ========================================
# SOPORTE DE AUDIO PARA EVALUACIONES
# ========================================

def procesar_respuesta_audio_ejercicio(
    ejercicio,
    estudiante,
    media_info,
    proveedor='twilio',
    intento=1
):
    """
    Procesa una respuesta de audio a un ejercicio práctico
    
    Args:
        ejercicio: Instancia de EjercicioPractico
        estudiante: Instancia de Estudiante
        media_info: Información del audio (dict para Twilio, str para Meta)
        proveedor: 'twilio' o 'meta'
        intento: Número de intento
    
    Returns:
        dict: Resultado de la evaluación con audio_url
    """
    
    logger.info(f"🎤 Procesando respuesta de audio para ejercicio {ejercicio.id}")
    
    # 1. Procesar audio (descargar + transcribir)
    processor = AudioProcessor()
    resultado_audio = processor.procesar_audio_completo(media_info, proveedor)
    
    if not resultado_audio['success']:
        return {
            'success': False,
            'error': 'No se pudo procesar el audio',
            'feedback': '⚠️ Hubo un problema al procesar tu audio. Por favor intenta de nuevo o escribe tu respuesta.'
        }
    
    texto_transcrito = resultado_audio['texto']
    audio_path = resultado_audio['audio_path']
    
    logger.info(f"✅ Audio transcrito: {texto_transcrito}")
    
    # 2. Evaluar según tipo de ejercicio
    from .evaluacion_ia import evaluar_ejercicio_numerico, evaluar_respuesta_abierta
    from decimal import Decimal, InvalidOperation
    
    if ejercicio.tipo == 'numerico':
        # Extraer número del texto transcrito
        numeros = re.findall(r'\d+(?:\.\d+)?', texto_transcrito.replace(',', ''))
        
        if not numeros:
            return {
                'success': False,
                'error': 'No se detectó un número en tu audio',
                'feedback': f"""
🎤 Escuché: "{texto_transcrito}"

No pude identificar un número en tu respuesta. Por favor di claramente el número, por ejemplo:

"Setecientos mil" o "700000"
"""
            }
        
        # Tomar el número más grande (usualmente es la respuesta)
        try:
            respuesta_numerica = Decimal(max(numeros, key=lambda x: float(x)))
        except InvalidOperation:
            return {
                'success': False,
                'error': 'Número inválido',
                'feedback': '⚠️ El número detectado no es válido. Por favor intenta de nuevo.'
            }
        
        # Evaluar
        resultado = evaluar_ejercicio_numerico(
            ejercicio=ejercicio,
            respuesta_numerica=respuesta_numerica,
            estudiante=estudiante,
            intento=intento
        )
        
        # Actualizar con datos de audio
        resultado['respuesta'].audio_url = audio_path
        resultado['respuesta'].modalidad = 'audio'
        resultado['respuesta'].save()
        
        # Agregar transcripción al feedback
        resultado['feedback'] = f"""
🎤 **Escuché:** "{texto_transcrito}"
📊 **Tu respuesta:** ${respuesta_numerica:,.0f}

{resultado['feedback']}
"""
        
        return {
            'success': True,
            **resultado
        }
    
    elif ejercicio.tipo in ['abierto', 'hipotetico', 'comprension']:
        # Evaluar texto transcrito
        resultado = evaluar_respuesta_abierta(
            ejercicio=ejercicio,
            respuesta_texto=texto_transcrito,
            estudiante=estudiante,
            intento=intento,
            modalidad='audio'
        )
        
        # Actualizar con audio_url
        resultado['respuesta'].audio_url = audio_path
        resultado['respuesta'].save()
        
        # Agregar transcripción al feedback
        resultado['feedback'] = f"""
🎤 **Escuché:** "{texto_transcrito}"

{resultado['feedback']}
"""
        
        return {
            'success': True,
            **resultado
        }
    
    else:
        return {
            'success': False,
            'error': 'Tipo de ejercicio no soportado para audio',
            'feedback': '⚠️ Este tipo de ejercicio no acepta respuestas de audio.'
        }


def transcribir_audio_simple(media_info, proveedor='twilio') -> str:
    """
    Transcribe un audio y retorna solo el texto
    
    Args:
        media_info: Información del audio
        proveedor: 'twilio' o 'meta'
    
    Returns:
        str: Texto transcrito o mensaje de error
    """
    processor = AudioProcessor()
    resultado = processor.procesar_audio_completo(media_info, proveedor)
    
    if resultado['success']:
        return resultado['texto']
    else:
        logger.error(f"❌ Error transcribiendo audio: {resultado['error']}")
        return None


# ========================================
# HELPERS
# ========================================

def extraer_numero_de_texto(texto: str) -> Decimal:
    """
    Extrae un número de un texto (útil para respuestas de audio)
    
    Ejemplos:
        "setecientos mil" → 700000
        "es 450000" → 450000
        "creo que son como 320 mil" → 320000
    """
    import re
    
    # Patrón para números escritos o dígitos
    numeros = re.findall(r'\d+(?:[.,]\d+)?', texto.replace(',', ''))
    
    if numeros:
        # Tomar el número más grande
        try:
            return Decimal(max(numeros, key=lambda x: float(x)))
        except:
            return None
    
    # Palabras a números (básico)
    conversiones = {
        'cero': 0, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
        'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
        'diez': 10, 'veinte': 20, 'treinta': 30, 'cuarenta': 40,
        'cincuenta': 50, 'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90,
        'cien': 100, 'ciento': 100, 'doscientos': 200, 'trescientos': 300,
        'cuatrocientos': 400, 'quinientos': 500, 'seiscientos': 600,
        'setecientos': 700, 'ochocientos': 800, 'novecientos': 900,
        'mil': 1000, 'millón': 1000000
    }
    
    texto_lower = texto.lower()
    for palabra, valor in conversiones.items():
        if palabra in texto_lower:
            # Intento básico de conversión
            if 'mil' in texto_lower and palabra != 'mil':
                return Decimal(valor * 1000)
            return Decimal(valor)
    
    return None
