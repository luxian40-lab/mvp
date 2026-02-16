"""
Sistema de aprendizaje continuo para la IA
- Guarda interacciones para mejorar respuestas
- Construye base de conocimiento personalizada por estudiante
- Detecta patrones de consultas frecuentes
"""

import logging
from django.utils import timezone
from .models import WhatsappLog, Estudiante

logger = logging.getLogger(__name__)


class SistemaAprendizaje:
    """Sistema que aprende de cada interacción"""
    
    @staticmethod
    def guardar_interaccion(estudiante, pregunta, respuesta, agente_usado=None, tema=None):
        """
        Guarda una interacción para aprendizaje futuro
        
        Args:
            estudiante: Instancia de Estudiante
            pregunta: Texto de la pregunta original
            respuesta: Texto de la respuesta generada
            agente_usado: Nombre del agente que respondió (opcional)
            tema: Tema de la consulta (opcional)
        """
        try:
            # Guardar contexto adicional en el log
            metadata = {
                'agente': agente_usado,
                'tema': tema,
                'longitud_pregunta': len(pregunta),
                'longitud_respuesta': len(respuesta),
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"💾 Interacción guardada - Estudiante: {estudiante.nombre}, Agente: {agente_usado}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando interacción: {e}")
    
    @staticmethod
    def obtener_historial_estudiante(estudiante, limite=10):
        """
        Obtiene el historial reciente de un estudiante
        
        Args:
            estudiante: Instancia de Estudiante
            limite: Número máximo de mensajes a retornar
        
        Returns:
            list: Lista de dict con mensajes ordenados por fecha
        """
        try:
            mensajes = WhatsappLog.objects.filter(
                telefono=estudiante.telefono
            ).order_by('-fecha')[:limite]
            
            historial = []
            for msg in reversed(mensajes):  # Invertir para tener orden cronológico
                historial.append({
                    'fecha': msg.fecha,
                    'tipo': msg.tipo,
                    'mensaje': msg.mensaje,
                    'es_usuario': msg.tipo == 'INCOMING'
                })
            
            return historial
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo historial: {e}")
            return []
    
    @staticmethod
    def construir_contexto_conversacion(estudiante, limite=5):
        """
        Construye contexto de conversación reciente para la IA
        
        Args:
            estudiante: Instancia de Estudiante
            limite: Número de intercambios a incluir
        
        Returns:
            str: Contexto formateado para la IA
        """
        try:
            historial = SistemaAprendizaje.obtener_historial_estudiante(
                estudiante, 
                limite=limite * 2  # x2 porque cada intercambio tiene 2 mensajes
            )
            
            if not historial:
                return ""
            
            contexto = "Historial de conversación reciente:\n\n"
            for msg in historial:
                emisor = "Estudiante" if msg['es_usuario'] else "Asistente"
                contexto += f"{emisor}: {msg['mensaje']}\n"
            
            contexto += "\n---\n"
            return contexto
            
        except Exception as e:
            logger.error(f"❌ Error construyendo contexto: {e}")
            return ""
    
    @staticmethod
    def detectar_preguntas_frecuentes(limite_dias=30, minimo_repeticiones=3):
        """
        Detecta patrones de preguntas frecuentes
        
        Args:
            limite_dias: Días hacia atrás para analizar
            minimo_repeticiones: Mínimo de veces que debe repetirse
        
        Returns:
            list: Lista de dict con preguntas frecuentes y su frecuencia
        """
        try:
            from datetime import timedelta
            from django.db.models import Count
            
            fecha_limite = timezone.now() - timedelta(days=limite_dias)
            
            # Obtener mensajes entrantes recientes
            mensajes = WhatsappLog.objects.filter(
                tipo='INCOMING',
                fecha__gte=fecha_limite
            ).values('mensaje').annotate(
                cantidad=Count('mensaje')
            ).filter(
                cantidad__gte=minimo_repeticiones
            ).order_by('-cantidad')[:20]
            
            preguntas_frecuentes = []
            for msg in mensajes:
                preguntas_frecuentes.append({
                    'pregunta': msg['mensaje'],
                    'frecuencia': msg['cantidad']
                })
            
            logger.info(f"📊 Detectadas {len(preguntas_frecuentes)} preguntas frecuentes")
            return preguntas_frecuentes
            
        except Exception as e:
            logger.error(f"❌ Error detectando preguntas frecuentes: {e}")
            return []
    
    @staticmethod
    def obtener_temas_populares(estudiante=None, limite_dias=30):
        """
        Identifica los temas más consultados
        
        Args:
            estudiante: Estudiante específico (opcional, None para todos)
            limite_dias: Días hacia atrás para analizar
        
        Returns:
            dict: Temas y su frecuencia
        """
        try:
            from datetime import timedelta
            import re
            
            fecha_limite = timezone.now() - timedelta(days=limite_dias)
            
            query = WhatsappLog.objects.filter(
                tipo='INCOMING',
                fecha__gte=fecha_limite
            )
            
            if estudiante:
                query = query.filter(telefono=estudiante.telefono)
            
            mensajes = query.values_list('mensaje', flat=True)
            
            # Palabras clave por tema
            temas_keywords = {
                'café': ['café', 'cafetal', 'arábigo', 'robusta', 'cosecha café'],
                'aguacate': ['aguacate', 'hass', 'palta', 'aguacatal'],
                'maíz': ['maíz', 'maizal', 'mazorca', 'elote'],
                'cacao': ['cacao', 'cacaotal', 'chocolate'],
                'ganadería': ['ganadería', 'ganado', 'vaca', 'vacuno', 'ternero'],
                'fertilización': ['fertilizar', 'fertilizante', 'abono', 'nutriente'],
                'plagas': ['plaga', 'enfermedad', 'hongo', 'insecto', 'control'],
                'riego': ['riego', 'irrigación', 'agua', 'humedad'],
                'cosecha': ['cosecha', 'recolección', 'recolectar', 'cosechar']
            }
            
            temas_conteo = {tema: 0 for tema in temas_keywords}
            
            for mensaje in mensajes:
                mensaje_lower = mensaje.lower()
                for tema, keywords in temas_keywords.items():
                    if any(keyword in mensaje_lower for keyword in keywords):
                        temas_conteo[tema] += 1
            
            # Filtrar temas con al menos 1 mención
            temas_populares = {
                tema: count 
                for tema, count in sorted(
                    temas_conteo.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                ) 
                if count > 0
            }
            
            logger.info(f"📊 Temas populares identificados: {len(temas_populares)}")
            return temas_populares
            
        except Exception as e:
            logger.error(f"❌ Error identificando temas populares: {e}")
            return {}
    
    @staticmethod
    def generar_resumen_aprendizaje():
        """
        Genera un resumen del aprendizaje acumulado
        
        Returns:
            dict: Resumen con estadísticas de aprendizaje
        """
        try:
            from datetime import timedelta
            
            # Última semana
            hace_7_dias = timezone.now() - timedelta(days=7)
            
            total_interacciones = WhatsappLog.objects.filter(
                fecha__gte=hace_7_dias
            ).count()
            
            estudiantes_activos = WhatsappLog.objects.filter(
                fecha__gte=hace_7_dias
            ).values('telefono').distinct().count()
            
            preguntas_frecuentes = SistemaAprendizaje.detectar_preguntas_frecuentes(
                limite_dias=7,
                minimo_repeticiones=2
            )
            
            temas_populares = SistemaAprendizaje.obtener_temas_populares(
                limite_dias=7
            )
            
            resumen = {
                'total_interacciones': total_interacciones,
                'estudiantes_activos': estudiantes_activos,
                'preguntas_frecuentes': preguntas_frecuentes[:5],
                'temas_populares': temas_populares,
                'periodo': 'Últimos 7 días',
                'fecha_generacion': timezone.now().isoformat()
            }
            
            logger.info(f"📊 Resumen de aprendizaje generado: {total_interacciones} interacciones")
            return resumen
            
        except Exception as e:
            logger.error(f"❌ Error generando resumen: {e}")
            return {}


# Funciones helper para uso rápido

def guardar_aprendizaje(estudiante, pregunta, respuesta, agente=None, tema=None):
    """Wrapper rápido para guardar interacción"""
    return SistemaAprendizaje.guardar_interaccion(
        estudiante, pregunta, respuesta, agente, tema
    )


def obtener_contexto_ia(estudiante, limite=5):
    """Wrapper rápido para obtener contexto de conversación"""
    return SistemaAprendizaje.construir_contexto_conversacion(estudiante, limite)
