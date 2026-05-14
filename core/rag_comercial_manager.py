"""
Manager para RAG comercial.
Aísla el conocimiento de ventas/catálogo del RAG educativo de cursos.
"""
import logging
import re
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_CHROMADB_OK = False
try:
    from .rag_eki_multitenant import RAGClienteCurso, CHROMADB_DISPONIBLE
    _CHROMADB_OK = CHROMADB_DISPONIBLE
except Exception:
    _CHROMADB_OK = False


def _consulta_catalogo_comercial(pregunta: str) -> bool:
    """Detecta intención de precios / listas / catálogo para activar refuerzos de recuperación."""
    return bool(
        re.search(
            r"precio|precios|cotiz|lista|tarifa|valor|cu[aá]nto|cuesta|insumo|producto|"
            r"cat[aá]logo|bulto|arroba|\bkg\b|kilo|dosis|paquete|mezcla|fertil|herbic|fungic",
            (pregunta or "").lower(),
        )
    )


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
        """Un solo scope (compatibilidad). Preferir `obtener_contexto_varios_clientes` en el webhook."""
        return self.obtener_contexto_varios_clientes(
            [int(cliente_id or 0)],
            canal,
            pregunta,
            max_chars=max_chars,
        )

    def obtener_contexto_varios_clientes(
        self,
        cliente_ids: Sequence[int],
        canal: str,
        pregunta: str,
        max_chars: int = 2200,
        top_k_por_scope: int = 8,
    ) -> str:
        """
        Une búsquedas semánticas en varios scopes (ej. cliente configurado + catálogo general id=0).

        Antes el webhook paraba en el primer cliente con *algún* hit en Chroma, aunque fuera
        irrelevante, y nunca llegaba al Excel indexado en otro scope (típico: General vs cliente).
        """
        if not self.disponible or not (pregunta or "").strip():
            return ""

        try:
            top_k_por_scope = int(top_k_por_scope)
        except (TypeError, ValueError):
            top_k_por_scope = 8
        top_k_por_scope = max(3, min(top_k_por_scope, 20))

        orden_ids: List[int] = []
        for raw in cliente_ids or []:
            try:
                cid = int(raw)
            except (TypeError, ValueError):
                continue
            if cid not in orden_ids:
                orden_ids.append(cid)

        if not orden_ids:
            return ""

        por_cliente: Dict[int, List[dict]] = {}
        for cid in orden_ids:
            rag = self.obtener_rag(cid, canal)
            if not rag:
                continue
            try:
                por_cliente[cid] = rag.buscar(pregunta, top_k=top_k_por_scope)
            except Exception as e:
                logger.warning("[RAGComercial] buscar falló cliente_id=%s canal=%s: %s", cid, canal, e)
                por_cliente[cid] = []

        vistos: set[str] = set()
        fragmentos: List[str] = []
        chars = 0
        ronda = 0
        salir = False
        while chars < max_chars and ronda < top_k_por_scope + 5 and not salir:
            avance = False
            for cid in orden_ids:
                hits = por_cliente.get(cid) or []
                if ronda >= len(hits):
                    continue
                d = hits[ronda]
                contenido = (d.get("contenido") or "").strip()
                if len(contenido) < 12:
                    continue
                firma = contenido[:400]
                if firma in vistos:
                    continue
                vistos.add(firma)
                fuente = (d.get("fuente") or "documento").strip()
                alcance = "catálogo general eki" if cid == 0 else f"material cliente {cid}"
                frag = f"[Fuente: {fuente} — {alcance}]\n{contenido}"
                if chars + len(frag) + 20 > max_chars:
                    salir = True
                    break
                fragmentos.append(frag)
                chars += len(frag)
                avance = True
            if salir:
                break
            if not avance:
                break
            ronda += 1
            if chars >= int(max_chars * 0.98):
                break

        cat_q = _consulta_catalogo_comercial(pregunta)
        if (not fragmentos) or (cat_q and chars < max(280, int(max_chars * 0.72))):
            logger.info("[RAGComercial] refuerzo muestreo Chroma (catálogo o poco contexto vectorial)")
            for cid in sorted(orden_ids, key=lambda x: (0 if x == 0 else 1, x)):
                rag = self.obtener_rag(cid, canal)
                if not rag:
                    continue
                for d in rag.muestreo_documentos(6):
                    contenido = (d.get("contenido") or "").strip()
                    if len(contenido) < 12:
                        continue
                    firma = contenido[:400]
                    if firma in vistos:
                        continue
                    vistos.add(firma)
                    fuente = (d.get("fuente") or "documento").strip()
                    alcance = "catálogo general eki" if cid == 0 else f"material cliente {cid}"
                    frag = f"[Fuente: {fuente} — {alcance} — extracto listado]\n{contenido}"
                    if chars + len(frag) + 20 > max_chars:
                        break
                    fragmentos.append(frag)
                    chars += len(frag)
                if chars >= int(max_chars * 0.98):
                    break

        if not fragmentos:
            amplia = f"{pregunta}\n\nPalabras clave: lista de precios productos insumos catálogo comercial venta."
            for cid in sorted(orden_ids, key=lambda x: (0 if x == 0 else 1, x)):
                rag = self.obtener_rag(cid, canal)
                if not rag:
                    continue
                try:
                    hits_amp = rag.buscar(amplia, top_k=top_k_por_scope)
                except Exception as e:
                    logger.warning("[RAGComercial] búsqueda ampliada falló cliente_id=%s: %s", cid, e)
                    hits_amp = []
                for d in hits_amp:
                    contenido = (d.get("contenido") or "").strip()
                    if len(contenido) < 12:
                        continue
                    firma = contenido[:400]
                    if firma in vistos:
                        continue
                    vistos.add(firma)
                    fuente = (d.get("fuente") or "documento").strip()
                    alcance = "catálogo general eki" if cid == 0 else f"material cliente {cid}"
                    frag = f"[Fuente: {fuente} — {alcance}]\n{contenido}"
                    if chars + len(frag) + 20 > max_chars:
                        break
                    fragmentos.append(frag)
                    chars += len(frag)
                if fragmentos:
                    break

        if not fragmentos:
            return ""

        return (
            "\n\n📚 INFORMACIÓN COMERCIAL INDEXADA (prioridad para precios, catálogo, condiciones):\n"
            + "\n---\n".join(fragmentos)
            + "\n\n⚠️ REGLA: Priorizá estos datos sobre conocimiento general; no inventes cifras, productos ni precios.\n"
        )

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
