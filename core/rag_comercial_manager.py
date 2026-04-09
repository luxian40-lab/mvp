"""
Manager para RAG comercial.
Aísla el conocimiento de ventas/catálogo del RAG educativo de cursos.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CHROMADB_OK = False
try:
    from .rag_eki_multitenant import RAGClienteCurso, CHROMADB_DISPONIBLE
    _CHROMADB_OK = CHROMADB_DISPONIBLE
except Exception:
    _CHROMADB_OK = False


class RAGComercialManager:
    """Gestiona RAG comercial por cliente + canal."""

    def __init__(self):
        self._instancias: dict = {}

    @property
    def disponible(self) -> bool:
        return _CHROMADB_OK

    @staticmethod
    def _normalizar_canal(canal: str) -> str:
        canal = (canal or 'bot_comercial').strip().lower()
        normalizado = ''.join(ch if ch.isalnum() or ch in ['_', '-'] else '_' for ch in canal)
        return normalizado or 'bot_comercial'

    def _virtual_scope(self, canal: str) -> str:
        # Scope virtual para separar almacenamiento comercial de cursos.
        return f"comercial_{self._normalizar_canal(canal)}"

    def obtener_rag(self, cliente_id: int, canal: str = 'bot_comercial') -> Optional['RAGClienteCurso']:
        if not self.disponible:
            return None

        scope = self._virtual_scope(canal)
        key = f"cli_{cliente_id}_{scope}"
        if key not in self._instancias:
            try:
                # Reuso del backend Chroma existente con scope virtual (no curso real).
                self._instancias[key] = RAGClienteCurso(cliente_id, scope)
            except Exception as e:
                logger.error(f"[RAGComercial] Error creando instancia {key}: {e}")
                return None
        return self._instancias[key]

    def obtener_contexto_para_bot(
        self,
        cliente_id: int,
        canal: str,
        pregunta: str,
        max_chars: int = 2200,
    ) -> str:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            return ""
        try:
            return rag.obtener_contexto_rag(pregunta, max_chars=max_chars)
        except Exception as e:
            logger.warning(f"[RAGComercial] Error obteniendo contexto: {e}")
            return ""

    def procesar_documento(
        self,
        cliente_id: int,
        canal: str,
        ruta_archivo: str,
        nombre_documento: str,
        tipo: str = 'producto',
    ) -> int:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            logger.warning("[RAGComercial] ChromaDB no disponible, documento no indexado")
            return 0
        return rag.procesar_documento(ruta_archivo, nombre_documento, tipo)

    def procesar_texto(
        self,
        cliente_id: int,
        canal: str,
        texto: str,
        nombre_documento: str,
        tipo: str = 'general',
    ) -> int:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            return 0
        return rag.procesar_texto_directo(texto, nombre_documento, tipo)

    def eliminar_documento(self, cliente_id: int, canal: str, nombre: str) -> bool:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            return False
        return rag.eliminar_documento(nombre)

    def listar_documentos(self, cliente_id: int, canal: str) -> List[Dict]:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            return []
        return rag.listar_documentos()

    def contar_chunks(self, cliente_id: int, canal: str) -> int:
        rag = self.obtener_rag(cliente_id, canal)
        if not rag:
            return 0
        return rag.contar_chunks()

    def limpiar_cache(self):
        self._instancias.clear()


rag_comercial_manager = RAGComercialManager()
