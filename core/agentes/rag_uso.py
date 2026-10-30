"""Packs RAG educativos: compartido + extra por agente.

Default `todos` = comportamiento histórico (Course Engine, portal, chat).
`companero` / `claudia` son aditivos: nunca ocultan chunks viejos sin metadata.
"""

USO_TODOS = 'todos'
USO_COMPANERO = 'companero'
USO_CLAUDIA = 'claudia'

USO_CHOICES = [
    (USO_TODOS, 'Todos los agentes (compartido)'),
    (USO_COMPANERO, 'Extra compañero (Darío / Carlos)'),
    (USO_CLAUDIA, 'Extra Claudia (facilitadora)'),
]

USOS_VALIDOS = {USO_TODOS, USO_COMPANERO, USO_CLAUDIA}


def normalizar_uso(uso) -> str:
    raw = (uso or '').strip().lower()
    if raw in ('dario', 'darío', 'asistente', 'companion'):
        return USO_COMPANERO
    if raw in ('facilitadora', 'tutor'):
        return USO_CLAUDIA
    if raw in USOS_VALIDOS:
        return raw
    return USO_TODOS


def chunk_visible_para_uso(metadata, uso) -> bool:
    """
    uso vacío/`todos` → no filtra (Course Engine y docs históricos).
    Pack agente → ve `todos`, chunks sin campo, y el pack pedido.
    """
    uso_req = normalizar_uso(uso)
    if not uso or uso_req == USO_TODOS:
        return True
    meta = metadata or {}
    if not isinstance(meta, dict):
        return True
    raw = str(meta.get('uso') or meta.get('uso_agente') or '').strip().lower()
    if not raw or raw == USO_TODOS:
        return True
    return raw == uso_req


def filtrar_chunks_por_uso(docs, uso, limite: int = 3) -> list:
    """Filtra en Python para no excluir chunks Chroma sin metadata `uso`."""
    if not docs:
        return []
    out = []
    for doc in docs:
        meta = doc if isinstance(doc, dict) else {}
        if chunk_visible_para_uso(meta, uso):
            out.append(doc)
        if limite and len(out) >= limite:
            break
    return out
