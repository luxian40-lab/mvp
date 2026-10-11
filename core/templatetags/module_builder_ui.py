"""Etiquetas de pantalla del Module Builder. No persiste nada."""
from django import template

register = template.Library()

_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
_VIDEO = ('.mp4', '.m4v', '.mov', '.webm', '.3gp')
_AUDIO = ('.mp3', '.ogg', '.m4a', '.aac', '.amr', '.opus', '.wav')
_QUIZ = ('evaluacion_opciones', 'evaluacion_abierta', 'reto')


@register.simple_tag
def etiqueta_mensaje(paso):
    """Texto, Imagen, Video, Audio o Documento. No usa paso_builder_ui."""
    tipo = getattr(paso, 'tipo', '') or ''
    if tipo in _QUIZ:
        return 'Quiz'
    url = (getattr(paso, 'media_url', '') or '').split('?', 1)[0].lower()
    if url.endswith(_IMAGEN):
        return 'Imagen'
    if url.endswith(_VIDEO):
        return 'Video'
    if url.endswith(_AUDIO):
        return 'Audio'
    if url:
        return 'Documento'
    return 'Texto'
