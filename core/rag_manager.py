"""
Manager de instancias RAG Multi-Tenant.
Cache en memoria de instancias RAGClienteCurso.
Punto de entrada único para todo el sistema.
"""
import logging
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)

# Flag global
_CHROMADB_OK = False
try:
    from .rag_eki_multitenant import RAGClienteCurso, CHROMADB_DISPONIBLE
    _CHROMADB_OK = CHROMADB_DISPONIBLE
except Exception:
    _CHROMADB_OK = False


class RAGManager:
    """
    Gestiona instancias RAG aisladas por Cliente + Curso.
    Cada combinación tiene su propia BD vectorial.

    Uso:
        from core.rag_manager import rag_manager
        ctx = rag_manager.obtener_contexto_para_ia(cliente_id=1, curso_id=2, pregunta="¿Cómo plantar?")
    """

    def __init__(self):
        self._instancias: dict = {}

    @property
    def disponible(self) -> bool:
        return _CHROMADB_OK

    def obtener_rag(self, cliente_id: int, curso_id: int) -> Optional['RAGClienteCurso']:
        """Obtener (o crear) instancia RAG para un cliente+curso."""
        if not self.disponible:
            return None

        key = f"cli_{cliente_id}_cur_{curso_id}"
        if key not in self._instancias:
            try:
                self._instancias[key] = RAGClienteCurso(cliente_id, curso_id)
            except Exception as e:
                logger.error(f"[RAGManager] Error creando instancia {key}: {e}")
                return None
        return self._instancias[key]

    # ====================================================
    # API PRINCIPAL — usada por los agentes IA
    # ====================================================

    def obtener_contexto_para_ia(
        self,
        cliente_id: int,
        curso_id: int,
        pregunta: str,
        max_chars: int = 2000
    ) -> str:
        """
        Obtiene contexto RAG para inyectar en prompts de agentes.
        Retorna string vacío si RAG no disponible o sin documentos.

        Se usa en ai_assistant.py y tutor_ia_modulo.py
        """
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return ""
        try:
            return rag.obtener_contexto_rag(pregunta, max_chars=max_chars)
        except Exception as e:
            logger.warning(f"[RAGManager] Error obteniendo contexto: {e}")
            return ""

    def responder_pregunta(
        self,
        cliente_id: int,
        curso_id: int,
        pregunta: str,
        personalidad: str = "geronimo"
    ) -> Tuple[str, List[Dict]]:
        """
        Responde usando SOLO documentos de este cliente+curso.
        """
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return "", []
        try:
            return rag.responder(pregunta, personalidad)
        except Exception as e:
            logger.error(f"[RAGManager] Error respondiendo: {e}")
            return "", []

    # ====================================================
    # API DE GESTIÓN — usada por admin
    # ====================================================

    def procesar_documento(
        self,
        cliente_id: int,
        curso_id: int,
        ruta_archivo: str,
        nombre_documento: str,
        tipo: str = "contenido"
    ) -> int:
        """Procesa un documento SOLO para este cliente+curso."""
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            logger.warning("[RAGManager] ChromaDB no disponible, documento no indexado")
            return 0
        return rag.procesar_documento(ruta_archivo, nombre_documento, tipo)

    def procesar_texto(
        self,
        cliente_id: int,
        curso_id: int,
        texto: str,
        nombre_documento: str,
        tipo: str = "contenido"
    ) -> int:
        """Indexa texto directo (contenido de módulo) para este cliente+curso."""
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return 0
        return rag.procesar_texto_directo(texto, nombre_documento, tipo)

    def indexar_modulos_curso(self, curso_id: int) -> int:
        """
        Indexa automáticamente el contenido de todos los módulos de un curso.
        Se puede llamar desde admin tras editar contenido.
        """
        try:
            from core.models import Curso
            curso = Curso.objects.select_related('cliente').prefetch_related('modulos').get(id=curso_id)
            cliente_id = curso.cliente_id if curso.cliente_id else 0

            rag = self.obtener_rag(cliente_id, curso_id)
            if not rag:
                return 0

            total = 0
            for modulo in curso.modulos.all():
                if modulo.contenido:
                    nombre = f"modulo_{modulo.numero}_{modulo.titulo[:40]}"
                    n = rag.procesar_texto_directo(modulo.contenido, nombre, tipo="modulo")
                    total += n

            logger.info(f"[RAGManager] Indexados {total} chunks de {curso.modulos.count()} módulos para Curso {curso.nombre}")
            return total
        except Exception as e:
            logger.error(f"[RAGManager] Error indexando módulos: {e}")
            return 0

    def eliminar_documento(self, cliente_id: int, curso_id: int, nombre: str) -> bool:
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return False
        return rag.eliminar_documento(nombre)

    def listar_documentos(self, cliente_id: int, curso_id: int) -> List[Dict]:
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return []
        return rag.listar_documentos()

    def contar_chunks(self, cliente_id: int, curso_id: int) -> int:
        rag = self.obtener_rag(cliente_id, curso_id)
        if not rag:
            return 0
        return rag.contar_chunks()

    def limpiar_cache(self):
        """Limpia todas las instancias en cache."""
        self._instancias.clear()


# Instancia global singleton
rag_manager = RAGManager()
