"""
Sistema de Base de Conocimientos para IAs
Permite a las IAs (agente_cursos, agente_apoyo) aprender del contenido de los cursos
"""
import json
import logging
from typing import List, Dict, Optional
from django.core.cache import cache
from .models import Curso, Modulo

logger = logging.getLogger(__name__)


class BaseConocimientos:
    """
    Base de conocimientos que indexa el contenido de los cursos
    para que las IAs puedan responder preguntas basadas en el material educativo
    """
    
    CACHE_KEY = "base_conocimientos_cursos"
    CACHE_TIMEOUT = 3600  # 1 hora
    
    @classmethod
    def actualizar(cls):
        """
        Actualiza la base de conocimientos con todo el contenido de los cursos
        Se debe llamar cuando se crea/actualiza un curso o módulo
        """
        logger.info("🔄 Actualizando base de conocimientos...")
        
        base_conocimientos = {
            'cursos': [],
            'modulos': [],
            'temas': {},  # palabra_clave: [modulo_ids]
        }
        
        # Indexar todos los cursos activos
        for curso in Curso.objects.filter(activo=True).prefetch_related('modulos'):
            curso_info = {
                'id': curso.id,
                'nombre': curso.nombre,
                'descripcion': curso.descripcion,
                'nivel': 'general',
                'categoria': getattr(curso, 'categoria', 'General') or 'General',
                'modulos': []
            }
            
            # Indexar módulos del curso
            for modulo in curso.modulos.all().order_by('numero'):
                modulo_info = {
                    'id': modulo.id,
                    'numero': float(modulo.numero),
                    'titulo': modulo.titulo,
                    'descripcion': modulo.descripcion,
                    'contenido': modulo.contenido,
                    'curso_id': curso.id,
                    'curso_nombre': curso.nombre,
                    'tiene_video': bool(modulo.video_url or modulo.video_archivo),
                    'duracion_dias': modulo.duracion_dias,
                }
                
                curso_info['modulos'].append(modulo_info['id'])
                base_conocimientos['modulos'].append(modulo_info)
                
                # Indexar por palabras clave
                palabras_clave = cls._extraer_palabras_clave(modulo)
                for palabra in palabras_clave:
                    if palabra not in base_conocimientos['temas']:
                        base_conocimientos['temas'][palabra] = []
                    base_conocimientos['temas'][palabra].append(modulo.id)
            
            base_conocimientos['cursos'].append(curso_info)
        
        # Guardar en cache
        cache.set(cls.CACHE_KEY, base_conocimientos, cls.CACHE_TIMEOUT)
        logger.info(f"✅ Base de conocimientos actualizada: {len(base_conocimientos['cursos'])} cursos, {len(base_conocimientos['modulos'])} módulos")
        
        return base_conocimientos
    
    @classmethod
    def obtener(cls) -> Dict:
        """
        Obtiene la base de conocimientos del cache
        Si no existe, la crea
        """
        base = cache.get(cls.CACHE_KEY)
        if not base:
            base = cls.actualizar()
        return base
    
    @classmethod
    def buscar_por_tema(cls, termino: str, limite: int = 5) -> List[Dict]:
        """
        Busca módulos relacionados con un término específico
        
        Args:
            termino: palabra clave a buscar
            limite: máximo de resultados
            
        Returns:
            Lista de módulos relevantes
        """
        base = cls.obtener()
        termino_lower = termino.lower()
        
        resultados = []
        
        # Buscar en palabras clave indexadas
        for palabra, modulo_ids in base['temas'].items():
            if termino_lower in palabra:
                for modulo in base['modulos']:
                    if modulo['id'] in modulo_ids and modulo not in resultados:
                        resultados.append(modulo)
                        if len(resultados) >= limite:
                            return resultados
        
        # Buscar en títulos y contenidos
        for modulo in base['modulos']:
            if len(resultados) >= limite:
                break
                
            if termino_lower in modulo['titulo'].lower() or \
               termino_lower in modulo['descripcion'].lower() or \
               termino_lower in modulo['contenido'].lower():
                if modulo not in resultados:
                    resultados.append(modulo)
        
        return resultados[:limite]
    
    @classmethod
    def obtener_modulo(cls, modulo_id: int) -> Optional[Dict]:
        """
        Obtiene la información completa de un módulo específico
        """
        base = cls.obtener()
        for modulo in base['modulos']:
            if modulo['id'] == modulo_id:
                return modulo
        return None
    
    @classmethod
    def obtener_curso(cls, curso_id: int) -> Optional[Dict]:
        """
        Obtiene la información completa de un curso
        """
        base = cls.obtener()
        for curso in base['cursos']:
            if curso['id'] == curso_id:
                # Agregar contenido de módulos
                curso_completo = curso.copy()
                curso_completo['modulos_detalle'] = []
                for modulo_id in curso['modulos']:
                    modulo = cls.obtener_modulo(modulo_id)
                    if modulo:
                        curso_completo['modulos_detalle'].append(modulo)
                return curso_completo
        return None
    
    @classmethod
    def generar_contexto_ia(cls, termino_busqueda: str, max_tokens: int = 2000) -> str:
        """
        Genera un contexto optimizado para la IA basado en una búsqueda
        
        Args:
            termino_busqueda: tema o pregunta del usuario
            max_tokens: límite aproximado de tokens para el contexto
            
        Returns:
            String con el contexto relevante
        """
        resultados = cls.buscar_por_tema(termino_busqueda, limite=3)
        
        if not resultados:
            return "No se encontró información específica sobre ese tema en los cursos."
        
        contexto = "📚 **Información de los cursos de eki:**\n\n"
        
        for modulo in resultados:
            contexto += f"**{modulo['curso_nombre']} - Módulo {modulo['numero']}: {modulo['titulo']}**\n"
            contexto += f"{modulo['descripcion']}\n\n"
            
            # Agregar contenido limitado
            contenido = modulo['contenido']
            if len(contenido) > 500:
                contenido = contenido[:500] + "..."
            contexto += f"{contenido}\n\n"
            contexto += "---\n\n"
            
            # Controlar tamaño aproximado
            if len(contexto) > max_tokens * 4:  # ~4 caracteres por token
                break
        
        return contexto
    
    @classmethod
    def _extraer_palabras_clave(cls, modulo: Modulo) -> List[str]:
        """
        Extrae palabras clave del módulo para indexación
        """
        texto = f"{modulo.titulo} {modulo.descripcion} {modulo.contenido}"
        texto_lower = texto.lower()
        
        # Palabras clave agrícolas relevantes
        palabras_agricultura = [
            'siembra', 'cosecha', 'fertilizante', 'abono', 'riego',
            'plaga', 'cultivo', 'tierra', 'suelo', 'semilla',
            'cacao', 'cafe', 'platano', 'maiz', 'frijol',
            'ganaderia', 'bovino', 'porcino', 'avicola', 'ovino',
            'produccion', 'comercializacion', 'mercado', 'precio',
            'clima', 'lluvia', 'sequia', 'temperatura',
            'organico', 'sostenible', 'ambiental', 'conservacion',
            'cooperativa', 'asociacion', 'credito', 'financiamiento',
            'maquinaria', 'herramienta', 'tecnologia', 'innovacion'
        ]
        
        palabras_encontradas = []
        for palabra in palabras_agricultura:
            if palabra in texto_lower:
                palabras_encontradas.append(palabra)
        
        return palabras_encontradas


# Función helper para actualizar la base de conocimientos
def actualizar_base_conocimientos():
    """
    Función auxiliar para actualizar la base de conocimientos
    Se puede llamar desde signals o admin actions
    """
    return BaseConocimientos.actualizar()


# Función para obtener contexto para la IA
def obtener_contexto_para_ia(pregunta_usuario: str) -> str:
    """
    Obtiene contexto relevante para que la IA responda una pregunta
    
    Args:
        pregunta_usuario: pregunta o tema del usuario
        
    Returns:
        Contexto relevante de los cursos
    """
    return BaseConocimientos.generar_contexto_ia(pregunta_usuario)
