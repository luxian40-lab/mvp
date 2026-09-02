"""Formato clase tipo Platzi → mensajes WhatsApp legibles."""
from __future__ import annotations

from core.course_engine.interactive_sequence import BloqueInteractivo

_MAX_WA_CHARS = 900


def _recortar(texto: str, limite: int = _MAX_WA_CHARS) -> str:
    t = (texto or '').strip()
    if len(t) <= limite:
        return t
    return t[: limite - 1].rstrip() + '…'


def formatear_paso_whatsapp(
    bloque: BloqueInteractivo,
    *,
    titulo_leccion: str = '',
    prefijo_leccion: str = '',
) -> str:
    """
    Convierte un bloque en texto WA con jerarquía estilo Platzi:
    resumen → secciones (pregunta) → definición → listas → cierre.
    """
    tipo = (bloque.tipo or 'texto').strip().lower()
    titulo = (bloque.titulo or '').strip()
    guion = (bloque.guion or '').strip()
    pref = (prefijo_leccion or '').strip()

    if tipo == 'resumen':
        cab = f'📋 *Resumen*\n*{titulo_leccion}*\n\n' if titulo_leccion else '📋 *Resumen*\n\n'
        return _recortar(f'{pref}{cab}{guion}')

    if tipo == 'seccion':
        # Título = pregunta tipo Platzi ("¿Qué es la rentabilidad?")
        cuerpo = f'\n\n{guion}' if guion else ''
        return _recortar(f'{pref}*{titulo}*{cuerpo}')

    if tipo == 'definicion':
        # Cita / definición clave (blockquote visual en WA)
        label = titulo or 'Definición'
        return _recortar(f'{pref}💡 *{label}*\n_{guion}_')

    if tipo == 'lista':
        cab = f'*{titulo}*\n' if titulo else ''
        return _recortar(f'{pref}{cab}{guion}')

    if tipo in ('cierre', 'resumen_final'):
        cab = f'✅ *{titulo or "Para cerrar"}*\n\n'
        pie = '\n\n_Escribe *listo* cuando termines._'
        return _recortar(f'{pref}{cab}{guion}{pie}')

    if tipo == 'micro_video':
        # Caption corta bajo el video
        if titulo and guion:
            return _recortar(f'🎬 *{titulo}*\n{guion}')
        return _recortar(guion or titulo)

    # texto narrativo
    if titulo and guion:
        return _recortar(f'{pref}{guion}')
    return _recortar(pref + (guion or titulo))
