"""
Agente de IA Empática para Soporte Emocional
Responde con empatía antes de escalar a soporte humano
"""
from openai import OpenAI
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


PROMPT_SISTEMA_EMPATICO = """Eres un asistente empático y comprensivo para estudiantes de agricultura que están experimentando dificultades o frustración.

Tu rol es:
1. Escuchar con empatía
2. Validar sus emociones
3. Ofrecer apoyo emocional
4. Intentar ayudar con su problema específico
5. Si no puedes resolver, ofrecer conectar con soporte humano

Directrices:
- Usa un tono cálido y comprensivo
- Valida sus sentimientos ("Entiendo que esto puede ser frustrante...")
- Sé breve pero efectivo (máximo 150 palabras)
- Usa emojis apropiados: 💚 🤗 🌱 ✨
- Si es algo técnico que no puedes resolver, di: "Te conectaré con nuestro equipo de soporte"
- Si es emocional/motivacional, da ánimo y consejos prácticos

Contexto: Plataforma educativa WhatsApp para caficultores colombianos.

NO inventes información técnica. Si no sabes, admítelo y ofrece soporte humano.
"""


def responder_con_empatia(mensaje_usuario, nombre_estudiante=""):
    """
    Genera respuesta empática usando IA antes de escalar a soporte
    
    Args:
        mensaje_usuario: El mensaje del estudiante
        nombre_estudiante: Nombre del estudiante (opcional)
    
    Returns:
        str: Respuesta empática generada por IA
    """
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            logger.warning("⚠️ No hay API key de OpenAI para IA empática")
            return None
        
        client = OpenAI(api_key=api_key)
        
        # Preparar contexto con nombre si está disponible
        contexto_nombre = f"El estudiante se llama {nombre_estudiante}. " if nombre_estudiante else ""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA_EMPATICO},
                {"role": "user", "content": f"{contexto_nombre}Mensaje del estudiante: {mensaje_usuario}"}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ IA empática generó respuesta")
        return respuesta
        
    except Exception as e:
        logger.error(f"❌ Error en IA empática: {e}")
        return None


def generar_respuesta_empatica_fallback(mensaje_usuario, nombre_estudiante=""):
    """
    Respuesta empática sin IA (fallback)
    """
    nombre = nombre_estudiante if nombre_estudiante else "amigo/a"
    
    # Detectar tipo de problema
    mensaje_lower = mensaje_usuario.lower()
    
    if any(palabra in mensaje_lower for palabra in ['no entiendo', 'difícil', 'complicado', 'confundido']):
        return f"""💚 {nombre}, entiendo que esto puede ser confuso.

🌱 Aprender cosas nuevas siempre tiene su reto, pero estás en el camino correcto solo por intentarlo.

✨ *¿Qué tal si probamos esto?*
• Lee el módulo de nuevo con calma
• Escríbeme la parte específica que no entiendes
• O dime: *"Quiero hablar con soporte"* y te conecto con alguien del equipo

Estás haciendo un gran trabajo. 🤗"""
    
    elif any(palabra in mensaje_lower for palabra in ['error', 'no funciona', 'problema', 'falla']):
        return f"""🤗 {nombre}, lamento que estés teniendo problemas técnicos.

💚 Entiendo lo frustrante que puede ser cuando algo no funciona como debería.

✨ *Vamos a solucionarlo:*
• ¿Puedes contarme exactamente qué pasó?
• ¿Qué mensaje de error viste?
• O dime: *"Conectar con soporte"* y te paso directo con el equipo técnico

Estamos aquí para ayudarte. 🌱"""
    
    elif any(palabra in mensaje_lower for palabra in ['frustrado', 'molesto', 'enojado', 'cansado']):
        return f"""💚 {nombre}, siento mucho que te sientas así.

Tus emociones son completamente válidas. Aprender algo nuevo mientras trabajas duro en el campo no es fácil.

🌱 *Recuerda:*
• Cada pequeño paso cuenta
• No tienes que hacerlo todo perfecto
• Estamos aquí para apoyarte

🤗 Si necesitas hablar con alguien de nuestro equipo, solo dime: *"Quiero soporte humano"*

Respira profundo. Vamos juntos en esto. ✨"""
    
    else:
        return f"""💚 Hola {nombre}, veo que necesitas ayuda.

Estoy aquí para escucharte y apoyarte en lo que necesites.

✨ *¿Cómo puedo ayudarte?*
• Cuéntame más sobre tu situación
• Pregúntame sobre algún tema específico del curso
• O dime: *"Necesito soporte"* y te conecto con nuestro equipo

🌱 Juntos encontraremos la solución. 🤗"""


def debe_escalar_a_soporte(mensaje_usuario):
    """
    Detecta si el mensaje explícitamente pide soporte humano
    
    Returns:
        bool: True si debe escalar, False si IA puede manejar
    """
    mensaje_lower = mensaje_usuario.lower()
    
    keywords_escalacion = [
        'quiero soporte',
        'necesito soporte',
        'hablar con soporte',
        'conectar con soporte',
        'quiero hablar con alguien',
        'necesito hablar con alguien',
        'soporte humano',
        'persona real',
        'alguien del equipo'
    ]
    
    return any(keyword in mensaje_lower for keyword in keywords_escalacion)
