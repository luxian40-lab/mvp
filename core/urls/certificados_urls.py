from django.urls import path

from core.views_certificados import (
    descargar_certificado_view,
    verificar_certificado_json_view,
    verificar_certificado_view,
)

urlpatterns = [
    path('verificar-certificado/<str:codigo_verificacion>/', verificar_certificado_view, name='verificar_certificado'),
    path('descargar-certificado/<str:codigo_verificacion>/', descargar_certificado_view, name='descargar_certificado'),
    path('api/certificados/verificar/', verificar_certificado_json_view, name='verificar_certificado_json'),
]
