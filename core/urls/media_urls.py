from django.urls import path

from core.views import (
    descargar_archivo_multimedia,
    obtener_archivos_modulo_view,
    serve_media_proxy,
    stream_media,
)

urlpatterns = [
    path('media/modulo/<int:modulo_id>/archivos/', obtener_archivos_modulo_view, name='obtener_archivos_modulo'),
    path('media/stream/', stream_media, name='stream_media'),
    path('media/descargar-archivo/<int:archivo_id>/', descargar_archivo_multimedia, name='descargar_archivo_multimedia'),
    path('media-proxy/<str:filename>', serve_media_proxy, name='media_proxy'),
]
