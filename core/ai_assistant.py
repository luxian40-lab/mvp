"""
Asistente de IA HÍBRIDO: OpenAI (primero) → Cohere (fallback)
"""
import logging
from django.conf import settings
import cohere
from .models import WhatsappLog, Estudiante

logger = logging.getLogger(__name__)

# ===== OPENAI =====
def get_openai_client():
    """Obtiene el cliente de OpenAI con la API key configurada"""
    try:
        from openai import OpenAI
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY no está configurada")
        return OpenAI(api_key=api_key)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo inicializar OpenAI: {e}")
        return None

# ===== COHERE (FALLBACK) =====
def get_cohere_client():
    """Obtiene el cliente de Cohere con la API key configurada"""
    api_key = getattr(settings, 'COHERE_API_KEY', None)
    if not api_key:
        raise ValueError("COHERE_API_KEY no está configurada en settings.py")
    return cohere.Client(api_key)

SYSTEM_PROMPT = """Eres el Profesor Gerónimo, TUTOR EDUCATIVO y MENTOR experto de eki, una plataforma de educación para comunidades rurales colombianas.

🎓 TU ROL COMO TUTOR:
- Enseñar y explicar conceptos paso a paso
- Guiar al estudiante en su proceso de aprendizaje y crecimiento personal
- Hacer preguntas para evaluar comprensión
- Motivar y acompañar en su desarrollo integral
- Corregir errores con paciencia y claridad

📚 TEMAS QUE DOMINAS:

🌱 **AGRICULTURA & GANADERÍA:**
- Cultivos colombianos: café, cacao, plátano, yuca, aguacate
- Técnicas: siembra, riego, fertilización, control de plagas
- Ganadería: manejo animal, pastos, salud
- Sostenibilidad y buenas prácticas

💰 **FINANZAS PERSONALES & EMPRENDIMIENTO:**
- Ahorro y presupuesto familiar
- Créditos y bancarización rural
- Costos de producción y rentabilidad
- Ventas y comercialización
- Emprendimiento rural

💪 **DESARROLLO PERSONAL & LIDERAZGO:**
- Motivación y mentalidad de crecimiento
- Gestión del tiempo y productividad
- Liderazgo comunitario
- Trabajo en equipo y asociatividad
- Resiliencia y superación personal

⚠️ REGLA CRÍTICA SOBRE CURSOS:
- El estudiante tiene un CURSO ACTUAL que verás en el contexto
- SIEMPRE contextualiza tus respuestas al curso actual del estudiante
- NO menciones otros cursos a menos que el estudiante pregunte explícitamente
- Si pregunta sobre plátano y está en café, enfócate en CAFÉ
- Si pregunta algo general, relacionalo con su curso actual

📚 METODOLOGÍA DE ENSEÑANZA:
1. Explica conceptos de forma sencilla (nivel campesino)
2. Usa ejemplos prácticos del campo colombiano
3. Da consejos aplicables inmediatamente
4. Pregunta si entendió antes de avanzar
5. Relaciona con su experiencia previa
6. CONTEXTUALIZA todo al curso actual del estudiante

💬 ESTILO DE COMUNICACIÓN:
- Amigable y cercano (como un maestro de confianza)
- Respuestas claras de 3-5 oraciones
- Usa emojis educativos: 📚 🌱 ✅ 💡 🎯
- Lenguaje sencillo sin términos técnicos complejos
- Haz preguntas guía: "¿Ya conocías esto?", "¿Qué te gustaría aprender?"

🚫 RESTRICCIONES:
- Enfócate en temas EDUCATIVOS y de DESARROLLO RURAL
- Puedes hablar de: agricultura, ganadería, finanzas personales, emprendimiento, motivación, liderazgo, desarrollo personal
- NO respondas sobre: política partidista, religión, noticias sensacionalistas, entretenimiento, deportes, celebridades
- Si preguntan temas fuera de alcance responde: "Puedo ayudarte con temas de agricultura, finanzas personales, emprendimiento y desarrollo personal 🌱💪"
- Mantén siempre un enfoque educativo y constructivo

🎯 OBJETIVO: No solo responder, sino ENSEÑAR y GUIAR el desarrollo integral del estudiante en su curso actual

✨ **ENFOQUE HOLÍSTICO:**
- Un buen agricultor también necesita saber de finanzas, liderazgo y mentalidad
- Conecta los temas cuando sea relevante (ej: cosecha → comercialización → finanzas)
- Empodera al estudiante como emprendedor rural completo

Contexto: Los estudiantes te escriben por WhatsApp buscando ayuda educativa y orientación."""


def obtener_historial_conversacion(telefono: str, limite: int = 10):
    """
    Obtiene el historial reciente de conversación con un estudiante.
    Estilo Huku: memoria extendida + contexto del estudiante
    
    Args:
        telefono: Número del estudiante
        limite: Cantidad de mensajes a recuperar (por defecto 10 como Huaku)
    
    Returns:
        Lista de mensajes formateados para OpenAI con contexto
    """
    import re
    # Normalizar teléfono para búsqueda (solo dígitos)
    telefono_limpio = re.sub(r'\D', '', str(telefono))
    if len(telefono_limpio) == 10:
        telefono_limpio = f"57{telefono_limpio}"
    
    logs = WhatsappLog.objects.filter(
        telefono=telefono_limpio
    ).order_by('-fecha')[:limite * 2]  # Obtenemos más para asegurar conversación balanceada
    
    historial = []
    for log in reversed(logs):  # Orden cronológico
        if log.tipo == 'INCOMING':
            role = "user"
        elif log.tipo == 'SENT':
            role = "assistant"
        else:
            continue  # Skip si no es ninguno de los dos
        
        if log.mensaje:  # Solo agregar si hay mensaje
            historial.append({
                "role": role,
                "content": log.mensaje[:500]  # Limitar largo del mensaje
            })
    
    # Devolver solo los últimos 'limite' mensajes
    return historial[-limite:] if len(historial) > limite else historial


def responder_con_openai(mensaje: str, telefono: str, contexto_estudiante: str = "") -> str:
    """Intenta responder con OpenAI incluyendo historial de conversación
    
    Implementación estilo Huaku:
    - Memoria extendida (10 mensajes)
    - Contexto del progreso del estudiante
    - Personalización según nivel
    """
    try:
        client = get_openai_client()
        if not client:
            raise ValueError("Cliente OpenAI no disponible")
        
        logger.info(f"🤖 Intentando con OpenAI para: {telefono}")
        
        # Obtener historial de conversación (últimos 10 mensajes - estilo Huaku)
        historial = obtener_historial_conversacion(telefono, limite=10)
        
        # Construir mensajes para OpenAI
        mensajes = [
            {"role": "system", "content": SYSTEM_PROMPT + contexto_estudiante}
        ]
        
        # Agregar historial (excluyendo el mensaje actual que ya vendrá al final)
        if historial:
            # Solo tomar los primeros 8 del historial para dejar espacio al mensaje actual
            mensajes.extend(historial[-8:])
        
        # Agregar el mensaje actual
        mensajes.append({"role": "user", "content": mensaje})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=mensajes,
            temperature=0.7,
            max_tokens=200,
            timeout=10  # 10 seconds max to avoid blocking webhook
        )
        
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ OpenAI respondió con contexto: {respuesta[:50]}...")
        
        # Agregar opciones de navegación
        respuesta_con_opciones = f"{respuesta}\n\n---\n💬 *Opciones:*\n• Escribe *menú* para ver el menú principal\n• Escribe *continuar* para seguir con tu curso\n• Escribe *ayuda* para ver todos los comandos"
        
        return respuesta_con_opciones
        
    except Exception as e:
        logger.warning(f"⚠️ OpenAI falló: {str(e)}")
        raise


def responder_con_cohere(mensaje: str, telefono: str, contexto_estudiante: str = "") -> str:
    """Responde con Cohere (fallback) incluyendo historial de conversación
    
    Implementación estilo Huaku: memoria extendida
    """
    try:
        logger.info(f"🤖 Usando Cohere (fallback) para: {telefono}")
        
        co = get_cohere_client()
        
        # Obtener historial de conversación (10 mensajes)
        historial = obtener_historial_conversacion(telefono, limite=10)
        
        # Convertir historial a formato de Cohere (chat_history)
        chat_history = []
        for msg in historial[-8:]:  # Últimos 8 mensajes (estilo Huaku)
            if msg["role"] == "user":
                chat_history.append({"role": "USER", "message": msg["content"]})
            elif msg["role"] == "assistant":
                chat_history.append({"role": "CHATBOT", "message": msg["content"]})
        
        response = co.chat(
            model='command-r-plus-08-2024',
            message=mensaje,
            chat_history=chat_history if chat_history else None,
            preamble=SYSTEM_PROMPT + contexto_estudiante,
            temperature=0.7,
            max_tokens=200
        )
        
        respuesta = response.text.strip()
        logger.info(f"✅ Cohere respondió con contexto: {respuesta[:50]}...")
        
        # Agregar opciones de navegación
        respuesta_con_opciones = f"{respuesta}\n\n---\n💬 *Opciones:*\n• Escribe *menú* para ver el menú principal\n• Escribe *continuar* para seguir con tu curso\n• Escribe *ayuda* para ver todos los comandos"
        
        return respuesta_con_opciones
        
    except Exception as e:
        logger.error(f"❌ Error en Cohere: {str(e)}", exc_info=True)
        raise


def responder_con_ia(mensaje: str, telefono: str) -> str:
    """
    Genera una respuesta inteligente usando IA HÍBRIDA.
    Intenta OpenAI primero, si falla usa Cohere.
    
    NOTA: Esta función solo debe llamarse para preguntas sobre agricultura
    que no tienen un intent definido. El flujo de habeas data y menús
    debe manejarse en el webhook antes de llamar esta función.
    
    Args:
        mensaje: Mensaje del usuario
        telefono: Número de teléfono del usuario
    
    Returns:
        Respuesta generada por la IA
    """
    try:
        # Normalizar teléfono (quitar +, whatsapp:, espacios, guiones)
        import re
        telefono_limpio = re.sub(r'\D', '', str(telefono))
        if len(telefono_limpio) == 10:
            telefono_limpio = f"57{telefono_limpio}"
        
        # Obtener información del estudiante si existe
        estudiante = None
        try:
            estudiante = Estudiante.objects.get(telefono=telefono_limpio)
        except Estudiante.DoesNotExist:
            # Intentar con formato original por compatibilidad
            try:
                estudiante = Estudiante.objects.get(telefono=telefono)
            except Estudiante.DoesNotExist:
                pass
        
        # DETECTAR SI HAY UN SELECTOR DE CURSO ACTIVO
        if estudiante:
            try:
                # Buscar el último mensaje enviado al usuario
                ultimo_log = WhatsappLog.objects.filter(
                    telefono=telefono_limpio,
                    tipo='SENT'
                ).order_by('-fecha').first()
                
                # Si el último mensaje contenía el selector de curso
                if ultimo_log and '[SELECTOR_CURSO_ACTIVO]' in ultimo_log.mensaje:
                    # El usuario debe responder con un número
                    if mensaje.strip().isdigit():
                        indice_curso = int(mensaje.strip())
                        from .selector_curso import continuar_curso_seleccionado
                        return continuar_curso_seleccionado(estudiante.id, indice_curso, mensaje)
                    else:
                        # Si NO es un número, el usuario puede estar escribiendo otra cosa
                        # En este caso, NO procesar como si fuera selector
                        # Dejar que el flujo normal lo maneje (intent_detector)
                        pass
            except Exception as e:
                print(f"⚠️ Error en selector de curso: {e}")
                # Continuar con flujo normal si hay error
        
        # Construir contexto adicional con curso actual
        contexto_estudiante = ""
        if estudiante:
            contexto_estudiante = f"\nEstudiante: {estudiante.nombre}"
            
            # Obtener curso actual (más reciente)
            from .models import ProgresoEstudiante
            progreso = ProgresoEstudiante.objects.filter(
                estudiante=estudiante
            ).order_by('-fecha_inicio').first()
            
            if progreso:
                porcentaje = progreso.porcentaje_avance()
                contexto_estudiante += f"\nCurso actual: {progreso.curso.nombre}"
                contexto_estudiante += f"\nProgreso: {porcentaje}%"
                if progreso.modulo_actual:
                    contexto_estudiante += f"\nMódulo actual: {progreso.modulo_actual.titulo}"
                contexto_estudiante += f"\n\n⚠️ IMPORTANTE: El estudiante está aprendiendo sobre {progreso.curso.nombre}. Todas tus respuestas deben estar contextualizadas a este cultivo/tema específico. NO menciones otros cursos a menos que el estudiante pregunte explícitamente."

                # 🤖 RAG Multi-Tenant: Inyectar contexto de documentos del curso
                try:
                    from .rag_manager import rag_manager
                    cliente_id = progreso.curso.cliente_id if progreso.curso.cliente_id else 0
                    contexto_rag = rag_manager.obtener_contexto_para_ia(
                        cliente_id=cliente_id,
                        curso_id=progreso.curso.id,
                        pregunta=mensaje,
                        max_chars=1500
                    )
                    if contexto_rag:
                        contexto_estudiante += contexto_rag
                        logger.info(f"[RAG] Contexto inyectado para {estudiante.nombre} (Cliente {cliente_id}, Curso {progreso.curso.id})")
                except Exception as e:
                    logger.warning(f"[RAG] Error obteniendo contexto: {e}")
        
        # ESTRATEGIA HÍBRIDA: OpenAI → Cohere
        try:
            # 1. Intentar con OpenAI primero
            return responder_con_openai(mensaje, telefono, contexto_estudiante)
        except:
            # 2. Si OpenAI falla, usar Cohere
            logger.info("🔄 OpenAI no disponible, cambiando a Cohere...")
            return responder_con_cohere(mensaje, telefono, contexto_estudiante)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error en ambas IAs: {error_msg}", exc_info=True)
        print(f"❌ Error en IA: {error_msg}")
        
        # Fallback a respuestas básicas
        from .intent_detector import detect_intent
        from .response_templates import get_response_for_intent
        
        intent = detect_intent(mensaje)
        fallback_response = get_response_for_intent(intent)
        
        logger.info(f"⚠️ Usando fallback para intent: {intent}")
        return fallback_response or "Disculpa, tengo problemas técnicos. ¿Puedes intentar más tarde? 🔧"


# ==========================================
# EVALUACIÓN DE EXÁMENES CON IA
# ==========================================

def evaluar_respuesta_examen(pregunta_obj, respuesta_estudiante: str) -> dict:
    """
    Evalúa la respuesta de un estudiante a una pregunta de examen usando IA.
    
    Args:
        pregunta_obj: Objeto PreguntaExamen con la pregunta y respuesta correcta
        respuesta_estudiante: Texto de la respuesta del estudiante
    
    Returns:
        dict: {
            'puntaje': int (0-puntos_pregunta),
            'correcta': bool,
            'feedback': str
        }
    """
    try:
        # Intentar con OpenAI primero
        client = get_openai_client()
        if not client:
            raise ValueError("OpenAI no disponible")
        
        prompt_evaluacion = f"""Eres un tutor evaluando un examen agrícola. Evalúa la siguiente respuesta:

PREGUNTA: {pregunta_obj.pregunta}

CONCEPTOS CLAVE ESPERADOS: {pregunta_obj.respuesta_correcta}

RESPUESTA DEL ESTUDIANTE: {respuesta_estudiante}

Evalúa si la respuesta contiene los conceptos clave y es coherente.
Responde EXACTAMENTE en este formato JSON:

{{
  "puntaje": [número de 0 a {pregunta_obj.puntos}],
  "correcta": [true o false],
  "feedback": "[Breve retroalimentación de 1-2 líneas explicando por qué está bien o qué faltó]"
}}

NO agregues texto adicional, solo el JSON."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un evaluador experto de exámenes agrícolas colombianos. SOLO evalúas temas de agricultura. Respondes SOLO con JSON válido."},
                {"role": "user", "content": prompt_evaluacion}
            ],
            temperature=0.3,  # Baja temperatura para evaluación consistente
            max_tokens=150
        )
        
        respuesta_ia = response.choices[0].message.content.strip()
        
        # Parsear JSON
        import json
        # Limpiar posibles markdown
        respuesta_ia = respuesta_ia.replace('```json', '').replace('```', '').strip()
        evaluacion = json.loads(respuesta_ia)
        
        logger.info(f"✅ Evaluación IA: {evaluacion['puntaje']}/{pregunta_obj.puntos} - {evaluacion['correcta']}")
        
        return evaluacion
        
    except Exception as e:
        logger.warning(f"⚠️ Error en evaluación con OpenAI: {str(e)}, usando evaluación básica")
        
        # FALLBACK: Evaluación básica por palabras clave
        respuesta_lower = respuesta_estudiante.lower()
        palabras_clave = [k.strip().lower() for k in pregunta_obj.respuesta_correcta.split(',')]
        
        # Contar cuántas palabras clave están presentes
        coincidencias = sum(1 for palabra in palabras_clave if palabra in respuesta_lower)
        total_palabras = len(palabras_clave)
        
        # Calcular puntaje proporcional
        if coincidencias == 0:
            puntaje = 0
            correcta = False
            feedback = f"Tu respuesta no incluye los conceptos clave esperados. Repasa: {pregunta_obj.respuesta_correcta[:50]}..."
        elif coincidencias < total_palabras / 2:
            puntaje = int(pregunta_obj.puntos * 0.4)
            correcta = False
            feedback = f"Tu respuesta es parcial. Te faltó mencionar algunos conceptos importantes."
        elif coincidencias < total_palabras:
            puntaje = int(pregunta_obj.puntos * 0.7)
            correcta = True
            feedback = f"Buena respuesta, aunque podrías haber incluido más detalles."
        else:
            puntaje = pregunta_obj.puntos
            correcta = True
            feedback = f"¡Excelente! Tu respuesta incluye todos los conceptos clave."
        
        return {
            'puntaje': puntaje,
            'correcta': correcta,
            'feedback': feedback
        }


def procesar_examen_completo(estudiante, examen, respuestas_dict: dict) -> dict:
    """
    Procesa todas las respuestas de un examen y genera resultado final.
    
    Args:
        estudiante: Objeto Estudiante
        examen: Objeto Examen
        respuestas_dict: Dict con {numero_pregunta: respuesta_texto}
    
    Returns:
        dict: {
            'puntaje_total': int (0-100),
            'aprobado': bool,
            'feedback_general': str,
            'detalles_preguntas': list[dict]
        }
    """
    from .models import PreguntaExamen, ResultadoExamen
    
    preguntas = examen.preguntas.order_by('numero')
    puntaje_total = 0
    puntaje_maximo = sum(p.puntos for p in preguntas)
    detalles = []
    
    for pregunta in preguntas:
        numero = pregunta.numero
        respuesta_estudiante = respuestas_dict.get(numero, "")
        
        if not respuesta_estudiante:
            evaluacion = {
                'puntaje': 0,
                'correcta': False,
                'feedback': 'No respondiste esta pregunta.'
            }
        else:
            evaluacion = evaluar_respuesta_examen(pregunta, respuesta_estudiante)
        
        puntaje_total += evaluacion['puntaje']
        
        detalles.append({
            'numero': numero,
            'pregunta': pregunta.pregunta,
            'respuesta': respuesta_estudiante,
            'puntaje': evaluacion['puntaje'],
            'puntaje_maximo': pregunta.puntos,
            'correcta': evaluacion['correcta'],
            'feedback': evaluacion['feedback']
        })
    
    # Calcular puntaje en escala 0-100
    puntaje_porcentaje = int((puntaje_total / puntaje_maximo) * 100)
    aprobado = puntaje_porcentaje >= examen.puntaje_minimo
    
    # Generar feedback general
    if aprobado:
        if puntaje_porcentaje >= 90:
            feedback_general = f"🎉 ¡EXCELENTE! Obtuviste {puntaje_porcentaje}%. Dominas muy bien este tema."
        elif puntaje_porcentaje >= 80:
            feedback_general = f"✅ ¡MUY BIEN! Obtuviste {puntaje_porcentaje}%. Buen desempeño."
        else:
            feedback_general = f"✅ APROBADO con {puntaje_porcentaje}%. Sigue practicando para mejorar."
    else:
        feedback_general = f"❌ No aprobaste ({puntaje_porcentaje}%). Necesitas {examen.puntaje_minimo}% para aprobar. Repasa el curso y vuelve a intentarlo."
    
    # Guardar resultado en BD
    resultado, created = ResultadoExamen.objects.update_or_create(
        estudiante=estudiante,
        examen=examen,
        defaults={
            'puntaje': puntaje_porcentaje,
            'aprobado': aprobado,
            'respuestas': respuestas_dict,
            'feedback': feedback_general
        }
    )
    
    logger.info(f"📊 Examen procesado: {estudiante.nombre} - {puntaje_porcentaje}% - {'✅' if aprobado else '❌'}")
    
    return {
        'puntaje_total': puntaje_porcentaje,
        'aprobado': aprobado,
        'feedback_general': feedback_general,
        'detalles_preguntas': detalles
    }
