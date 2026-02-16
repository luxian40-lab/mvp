"""
Sistema de Agentes Especializados - Estilo Huaku
Múltiples IAs con roles específicos para educación por WhatsApp
"""

import logging
from .models import Estudiante, ProgresoEstudiante
from .ai_assistant import get_openai_client, obtener_historial_conversacion
from .base_conocimientos import obtener_contexto_para_ia

logger = logging.getLogger(__name__)


class AgenteBase:
    """Clase base para todos los agentes de IA"""
    
    def __init__(self, estudiante: Estudiante):
        self.estudiante = estudiante
        self.client = get_openai_client()
    
    def obtener_contexto_estudiante(self):
        """Obtiene información contextual del estudiante"""
        # Obtener el progreso más reciente (curso actual) - ordenado por fecha_inicio
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=self.estudiante
        ).order_by('-fecha_inicio').first()
        
        contexto = f"\n\nEstudiante: {self.estudiante.nombre}"
        
        if progreso:
            porcentaje = progreso.porcentaje_avance()
            contexto += f"\nCurso actual: {progreso.curso.nombre}"
            contexto += f"\nProgreso: {porcentaje}%"
            if progreso.modulo_actual:
                contexto += f"\nMódulo actual: {progreso.modulo_actual.titulo}"
                contexto += f"\n\n⚠️ IMPORTANTE: El estudiante está aprendiendo sobre {progreso.curso.nombre}. Todas tus respuestas deben estar contextualizadas a este cultivo específico."
        
        return contexto


class AgenteTutor(AgenteBase):
    """
    Agente especializado en ENSEÑANZA
    - Explica conceptos agrícolas
    - Responde preguntas educativas
    - Guía el aprendizaje paso a paso
    """
    
    PROMPT = """
Eres un TUTOR EXPERTO de Eki, especializado en adaptar la enseñanza a cualquier curso (agricultura, finanzas, emprendimiento, etc.) según el contexto del estudiante.

🎓 TU ESPECIALIDAD:
- Enseñar de forma PRÁCTICA y SENCILLA, adaptando explicaciones al nivel y realidad del estudiante.
- Usar ejemplos concretos y situaciones reales del curso actual.
- Hacer preguntas guía para verificar comprensión y motivar la reflexión.
- Motivar y acompañar el aprendizaje continuo.

⚠️ INSTRUCCIÓN CLAVE:
Al finalizar cada módulo, pide al estudiante un ejemplo práctico de cómo aplicaría lo aprendido en su contexto real (agricultura, finanzas, emprendimiento, etc.). Si el estudiante tiene dudas o su respuesta es vaga, haz preguntas guía para ayudarle a reflexionar y concretar su ejemplo.

📚 METODOLOGÍA PEDAGÓGICA:
1. SIMPLIFICA: Usa palabras sencillas, evita tecnicismos.
2. EJEMPLIFICA: Da ejemplos concretos del CURSO ACTUAL que puedan aplicar HOY.
3. CONTEXTUALIZA: Relaciona con su curso y experiencia previa.
4. VERIFICA: Pregunta si entendió antes de avanzar.
5. CELEBRA: Reconoce cuando responden bien o mejoran.

💬 ESTILO DE COMUNICACIÓN:
- Tono: Cercano y motivador (como un maestro de confianza).
- Longitud: 3-5 oraciones máximo (WhatsApp, lectura fácil).
- Emojis: Usa educativos: 📚 🌱 ✅ 💡 🎯 (máx 2 por mensaje).
- Preguntas: Haz preguntas guía cuando sea apropiado.
- Estructura: Párrafos cortos, fáciles de leer en móvil.

🎯 REGLAS CRÍTICAS:
- NO uses términos técnicos sin explicarlos primero.
- SÍ relaciona cada concepto con beneficios prácticos del CURSO ACTUAL.
- NO des respuestas genéricas, SÍ personaliza al contexto del estudiante.
- SÍ pregunta sobre su situación específica cuando sea relevante.
- NO menciones cursos diferentes al actual.

🚫 RESTRICCIONES ABSOLUTAS:
- SOLO hablas de los temas del curso actual y plataforma Eki.
- NO respondas preguntas sobre: política, religión, economía general, noticias, entretenimiento, deportes, celebridades.
- Si preguntan temas prohibidos responde: "Solo puedo ayudarte con temas de tu curso en Eki 📚"
- Tu único rol es EDUCACIÓN y acompañamiento para el curso actual del estudiante.

🌱 OBJETIVO: No solo responder, sino ENSEÑAR y ayudar a aplicar lo aprendido en el contexto real del estudiante para que aprenda de verdad y pueda aplicarlo."""

    def responder(self, mensaje: str) -> str:
        """Genera respuesta educativa personalizada"""
        import time
        inicio = time.time()
        
        try:
            if not self.client:
                raise ValueError("OpenAI no disponible")
            
            # Obtener contexto del estudiante
            contexto = self.obtener_contexto_estudiante()
            
            # Obtener contexto relevante de la base de conocimientos
            contexto_cursos = obtener_contexto_para_ia(mensaje)
            if contexto_cursos and "No se encontró información" not in contexto_cursos:
                contexto += f"\n\n📚 Información relevante de los cursos:\n{contexto_cursos}"
            
            # Obtener historial
            historial = obtener_historial_conversacion(self.estudiante.telefono, limite=10)
            
            # Construir mensajes
            mensajes = [
                {"role": "system", "content": self.PROMPT + contexto}
            ]
            mensajes.extend(historial[-8:])
            mensajes.append({"role": "user", "content": mensaje})
            
            # Generar respuesta
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=mensajes,
                temperature=0.7,
                max_tokens=200
            )
            
            respuesta = response.choices[0].message.content.strip()
            tiempo_respuesta = time.time() - inicio
            
            # Registrar uso para monitoreo
            from .monitoreo_agentes import registrar_uso_agente
            registrar_uso_agente(
                telefono=self.estudiante.telefono,
                mensaje=mensaje,
                agente_usado='AgenteTutor',
                respuesta=respuesta,
                tiempo_respuesta=tiempo_respuesta
            )
            
            logger.info(f"✅ AgenteTutor respondió con conocimiento: {respuesta[:50]}... ({tiempo_respuesta:.2f}s)")
            
            return respuesta
            
        except Exception as e:
            logger.error(f"❌ Error en AgenteTutor: {e}")
            raise


class AgenteFrustracion(AgenteBase):
    """
    Agente especializado en MANEJO DE FRUSTRACIÓN Y EMOCIONES
    - Detecta y valida emociones negativas (frustración, enojo, confusión)
    - Ofrece empatía y comprensión genuina
    - Transforma frustración en motivación constructiva
    - Sugiere pasos concretos para superar dificultades
    """
    
    PROMPT = """Eres un COACH EMOCIONAL ESPECIALIZADO en manejar frustración de estudiantes campesinos.

😤 TU ESPECIALIDAD: MANEJO DE FRUSTRACIÓN
Detectas cuando el estudiante está:
- Frustrado ("no entiendo", "esto es difícil")
- Enojado ("no sirve", "no me ayuda", "esto no funciona")
- Desanimado ("no puedo", "me rindo", "ya no quiero")
- Confundido ("estoy perdido", "no sé qué hacer")

💙 TU ENFOQUE:
1. VALIDA su emoción (no la minimices):
   - "Entiendo tu frustración, es normal sentirse así"
   - "Sé que esto puede ser confuso al principio"
   - "Es válido que te sientas así, muchos pasan por lo mismo"

2. IDENTIFICA la causa específica:
   - ¿Qué parte exactamente no entiende?
   - ¿Qué esperaba vs qué está pasando?
   - ¿Cuál es el obstáculo real?

3. OFRECE solución paso a paso:
   - Desglosa en pasos MÁS pequeños
   - Da ejemplo CONCRETO del campo
   - Ofrece alternativa más simple

4. MOTIVA constructivamente:
   - "Vamos a intentarlo de otra forma"
   - "Te voy a explicar más despacio"
   - "Juntos vamos a resolverlo"

💬 ESTILO DE COMUNICACIÓN:
- Tono: EMPÁTICO y PACIENTE (como un amigo que entiende)
- NO uses frases genéricas tipo "tú puedes"
- SÍ reconoce la dificultad específica
- Emojis calmantes: 💙 🤝 🌟 ✨ (máx 2 por mensaje)
- Pregunta: "¿Qué parte específica te genera confusión?"

🚫 RESTRICCIONES ABSOLUTAS:
- SOLO ayudas con FRUSTRACIÓN RELACIONADA A APRENDIZAJE AGRÍCOLA en Eki
- NO respondas preguntas sobre: política, religión, problemas personales no relacionados con agricultura
- Si preguntan temas prohibidos responde: "Solo puedo ayudarte con tu aprendizaje agrícola en Eki 🌱"

🎯 OBJETIVO CRÍTICO:
- NO frustrar más al estudiante
- SÍ validar su emoción primero
- SÍ ofrecer solución CONCRETA
- SÍ transformar frustración en progreso

Ejemplo de respuesta ideal:
"Entiendo que esto puede ser confuso 💙 Es completamente normal. 
Vamos a resolverlo juntos paso a paso. 
¿Qué parte específica te genera más dificultad? Así te explico de forma más clara."
"""

    def responder(self, mensaje: str) -> str:
        """Genera respuesta empática para manejar frustración"""
        import time
        inicio = time.time()
        
        try:
            if not self.client:
                return "Entiendo tu frustración 💙 Vamos a resolverlo juntos paso a paso. ¿Qué parte específica te confunde?"
            
            # Obtener contexto e historial
            contexto = self.obtener_contexto_estudiante()
            historial = obtener_historial_conversacion(self.estudiante.telefono, limite=10)
            
            # Construir mensajes
            mensajes = [
                {"role": "system", "content": self.PROMPT + contexto}
            ]
            mensajes.extend(historial[-8:])
            mensajes.append({"role": "user", "content": mensaje})
            
            # Generar respuesta con temperatura más baja para ser más empático y preciso
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=mensajes,
                temperature=0.6,  # Más bajo para respuestas más consistentes y empáticas
                max_tokens=200
            )
            
            respuesta = response.choices[0].message.content.strip()
            tiempo_respuesta = time.time() - inicio
            
            # Registrar uso
            from .monitoreo_agentes import registrar_uso_agente
            registrar_uso_agente(
                telefono=self.estudiante.telefono,
                mensaje=mensaje,
                agente_usado='AgenteFrustracion',
                respuesta=respuesta,
                tiempo_respuesta=tiempo_respuesta
            )
            
            logger.info(f"✅ AgenteFrustracion respondió: {respuesta[:50]}... ({tiempo_respuesta:.2f}s)")
            
            return respuesta
            
        except Exception as e:
            logger.error(f"❌ Error en AgenteFrustracion: {e}")
            return "Entiendo que esto puede ser difícil 💙 Vamos paso a paso. ¿Qué parte específica te confunde más?"


class AgenteMotivador(AgenteBase):
    def responder(self, mensaje: str) -> str:
        """Responde con un mensaje motivacional contextualizado"""
        return self.generar_mensaje_motivacional(contexto_especifico=mensaje)
    """
    Agente especializado en MOTIVACIÓN y SEGUIMIENTO
    - Motiva a continuar estudiando
    - Celebra logros
    - Da ánimos cuando hay dificultades
    - Recuerda la importancia del aprendizaje
    """
    
    PROMPT = """Eres un MENTOR MOTIVACIONAL para campesinos colombianos en Eki.

🎯 TU MISIÓN:
- INSPIRAR a seguir aprendiendo agricultura
- CELEBRAR cada logro (pequeño o grande)
- DAR ÁNIMO en momentos de dificultad o frustración
- RECORDAR el valor práctico de lo que aprenden

💪 MENSAJES CLAVE:
- "Tu esfuerzo mejorará tus cosechas"
- "Cada día aprendes algo que puedes usar en tu finca"
- "Miles de campesinos ya lo lograron, tú también puedes"
- "El conocimiento es la mejor inversión para tu campo"

💬 ESTILO MOTIVACIONAL:
- POSITIVO y ENERGÉTICO (pero auténtico, no exagerado)
- Usa emojis motivadores: 💪 🌟 🎉 🚀 ⭐ 🏆 (máx 3 por mensaje)
- Frases cortas e impactantes
- Reconoce el ESFUERZO, no solo los resultados
- Conecta con beneficios reales: mejores cultivos, más ingresos, familia

🚫 RESTRICCIONES ABSOLUTAS:
- SOLO motivas sobre APRENDIZAJE AGRÍCOLA y progreso en Eki
- NO hables de: política, religión, motivación general de vida, temas no agrícolas
- Si preguntan temas prohibidos: "Solo puedo motivarte en tu aprendizaje agrícola 🌱💪"

🎯 REGLAS:
- NO uses frases genéricas como "tú puedes" sin contexto
- SÍ menciona beneficios concretos de seguir aprendiendo
- NO minimices sus dificultades, SÍ valida su esfuerzo
- SÍ usa historias breves de éxito de otros campesinos

Contexto: El estudiante necesita MOTIVACIÓN REAL para seguir adelante en su aprendizaje."""

    def generar_mensaje_motivacional(self, contexto_especifico: str = "") -> str:
        """Genera mensaje de motivación personalizado"""
        import time
        inicio = time.time()
        
        try:
            if not self.client:
                return "¡Sigue adelante! Tu esfuerzo dará frutos. 🌱💪"
            
            contexto = self.obtener_contexto_estudiante()
            if contexto_especifico:
                contexto += f"\n{contexto_especifico}"
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.PROMPT + contexto},
                    {"role": "user", "content": "Dame un mensaje motivacional corto"}
                ],
                temperature=0.9,
                max_tokens=100
            )
            
            respuesta = response.choices[0].message.content.strip()
            tiempo_respuesta = time.time() - inicio
            
            # Registrar uso
            from .monitoreo_agentes import registrar_uso_agente
            registrar_uso_agente(
                telefono=self.estudiante.telefono,
                mensaje="[Mensaje motivacional]",
                agente_usado='AgenteMotivador',
                respuesta=respuesta,
                tiempo_respuesta=tiempo_respuesta
            )
            
            return respuesta
            
        except Exception as e:
            logger.error(f"❌ Error en AgenteMotivador: {e}")
            return "¡Excelente trabajo! Sigue así, cada día aprendes más. 🌟"


class AgenteEvaluador(AgenteBase):
    def responder(self, mensaje: str) -> str:
        """Evalúa una respuesta de examen a partir de un mensaje simple"""
        # Para compatibilidad con el test, asumimos que el mensaje es la respuesta del estudiante
        pregunta = "Pregunta de ejemplo para prueba automática"
        respuesta_correcta = "Respuesta correcta de ejemplo"
        resultado = self.evaluar_respuesta(pregunta, respuesta_correcta, mensaje)
        feedback = resultado.get('feedback', '')
        puntaje = resultado.get('puntaje', 0)
        correcta = resultado.get('correcta', False)
        return f"Puntaje: {puntaje}/100\nCorrecta: {'Sí' if correcta else 'No'}\nFeedback: {feedback}"
    """
    Agente especializado en EVALUACIÓN
    - Evalúa respuestas de exámenes
    - Da feedback constructivo
    - Identifica áreas de mejora
    - Sugiere temas a repasar
    """
    
    PROMPT = """Eres un EVALUADOR EDUCATIVO experto en agricultura para Eki.

📝 TU FUNCIÓN:
- Evaluar respuestas de exámenes de forma JUSTA
- Dar FEEDBACK CONSTRUCTIVO
- Identificar qué entendió bien y qué no
- Sugerir qué debe repasar

✅ CRITERIOS:
- Corrección técnica (¿es correcto el concepto?)
- Comprensión profunda (¿realmente entendió?)
- Aplicabilidad práctica (¿puede aplicarlo?)

💬 FEEDBACK DEBE SER:
- Específico y claro
- Constructivo (qué hacer para mejorar)
- Equilibrado (reconoce lo bueno y lo mejorable)
- Motivador (anima a seguir aprendiendo)

🚫 RESTRICCIÓN CRÍTICA:
- SOLO evalúas conocimientos de AGRICULTURA COLOMBIANA
- NO evalúes temas de: política, religión, economía general, o temas no agrícolas
- Si detectas pregunta no agrícola responde: "Solo evalúo conocimientos agrícolas 🌱"

🎯 FORMATO:
1. ¿Qué estuvo bien?
2. ¿Qué faltó o está incorrecto?
3. ¿Qué debe repasar?"""

    def evaluar_respuesta(self, pregunta: str, respuesta_correcta: str, 
                         respuesta_estudiante: str) -> dict:
        """
        Evalúa una respuesta de examen
        
        Returns:
            dict con {
                'puntaje': int (0-100),
                'correcta': bool,
                'feedback': str
            }
        """
        try:
            if not self.client:
                return {
                    'puntaje': 50,
                    'correcta': False,
                    'feedback': 'No se pudo evaluar automáticamente.'
                }
            
            prompt_evaluacion = f"""Evalúa esta respuesta de un campesino:

PREGUNTA: {pregunta}

RESPUESTA ESPERADA: {respuesta_correcta}

RESPUESTA DEL ESTUDIANTE: {respuesta_estudiante}

Dame:
1. Puntaje (0-100)
2. Si es correcta (sí/no)
3. Feedback constructivo (2-3 oraciones)

Formato: PUNTAJE: X | CORRECTA: sí/no | FEEDBACK: ..."""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.PROMPT},
                    {"role": "user", "content": prompt_evaluacion}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            evaluacion_texto = response.choices[0].message.content.strip()
            
            # Parsear respuesta
            import re
            puntaje_match = re.search(r'PUNTAJE:\s*(\d+)', evaluacion_texto)
            correcta_match = re.search(r'CORRECTA:\s*(sí|si|no)', evaluacion_texto, re.IGNORECASE)
            feedback_match = re.search(r'FEEDBACK:\s*(.+)', evaluacion_texto, re.DOTALL)
            
            puntaje = int(puntaje_match.group(1)) if puntaje_match else 50
            correcta = correcta_match.group(1).lower() in ['sí', 'si'] if correcta_match else puntaje >= 70
            feedback = feedback_match.group(1).strip() if feedback_match else evaluacion_texto
            
            logger.info(f"✅ AgenteEvaluador: {puntaje}pts - {'✓' if correcta else '✗'}")
            
            return {
                'puntaje': puntaje,
                'correcta': correcta,
                'feedback': feedback
            }
            
        except Exception as e:
            logger.error(f"❌ Error en AgenteEvaluador: {e}")
            return {
                'puntaje': 50,
                'correcta': False,
                'feedback': 'Hubo un error al evaluar. Revisa tu respuesta.'
            }


# ==========================================
# COORDINADOR DE AGENTES (Selector inteligente)
# ==========================================

def seleccionar_agente(estudiante: Estudiante, mensaje: str, contexto: str = ""):
    """
    Selecciona el agente apropiado según el contexto
    Estilo Huaku: router inteligente de agentes
    
    Args:
        estudiante: Objeto Estudiante
        mensaje: Mensaje del usuario
        contexto: Contexto adicional (ej: "examen", "motivacion")
    
    Returns:
        Instancia del agente apropiado
    """
    mensaje_lower = mensaje.lower()
    
    # Si está en examen, usar Evaluador
    if contexto == "examen" or "evalua" in mensaje_lower:
        return AgenteEvaluador(estudiante)
    
    # ========== DETECTOR DE FRUSTRACIÓN (PRIORIDAD ALTA) ==========
    # Palabras clave de FRUSTRACIÓN directa (negación, queja, enojo)
    palabras_frustracion = [
        'no entiendo', 'no comprendo', 'no sé', 'no se', 
        'no me sirve', 'no sirve', 'no funciona', 'no ayuda',
        'no me ayuda', 'no está ayudando', 'no estas ayudando',
        'esto no', 'nada', 'perdido', 'confundido', 'confuso',
        'difícil', 'complicado', 'imposible', 'no puedo',
        'rendirme', 'me rindo', 'frustrado', 'frustrante',
        'enojado', 'molesto', 'hartado', 'cansado de',
        'no funciona', 'mal', 'error', 'problema',
        'ya intenté', 'sigo sin', 'todavía no'
    ]
    
    # Verificar si hay frustración evidente
    tiene_frustracion = any(palabra in mensaje_lower for palabra in palabras_frustracion)
    
    # Detectar tono negativo (palabras negativas sin solución constructiva)
    palabras_negativas = ['no', 'nada', 'nunca', 'nadie', 'ningún', 'mal', 'peor']
    cuenta_negativas = sum(1 for palabra in palabras_negativas if palabra in mensaje_lower.split())
    
    # Si hay 2 o más palabras negativas O frustración explícita → AgenteFrustracion
    if tiene_frustracion or cuenta_negativas >= 2:
        logger.info(f"🔴 Frustración detectada: '{mensaje[:50]}...' → AgenteFrustracion")
        return AgenteFrustracion(estudiante)
    
    # ========== DETECTOR DE NECESIDAD DE MOTIVACIÓN ==========
    # Palabras que indican necesidad de ánimo (pero no frustración directa)
    palabras_motivacion = ['cansado', 'difícil', 'duro', 'largo', 'mucho tiempo']
    if any(palabra in mensaje_lower for palabra in palabras_motivacion) and not tiene_frustracion:
        logger.info(f"💪 Motivación necesaria: '{mensaje[:50]}...' → AgenteMotivador")
        return AgenteMotivador(estudiante)
    
    # Por defecto, usar Tutor (educativo)
    logger.info(f"📚 Consulta educativa: '{mensaje[:50]}...' → AgenteTutor")
    return AgenteTutor(estudiante)
