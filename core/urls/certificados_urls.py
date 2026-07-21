from django.urls import path

from core.views_certificados import (
    descargar_certificado_view,
    verificar_certificado_json_view,
    verificar_certificado_query_view,
    verificar_certificado_view,
)

urlpatterns = [
    # Página pública por código (QR nuevo)
    path(
        'verificar-certificado/<str:codigo_verificacion>/',
        verificar_certificado_view,
        name='verificar_certificado',
    ),
    # Compatibilidad Netlify: /verificar/?code=EKI-...
    path('verificar/', verificar_certificado_query_view, name='verificar_certificado_query'),
    path(
        'descargar-certificado/<str:codigo_verificacion>/',
        descargar_certificado_view,
        name='descargar_certificado',
    ),
    path('api/certificados/verificar/', verificar_certificado_json_view, name='verificar_certificado_json'),
]
