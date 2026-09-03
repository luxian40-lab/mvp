from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing, name='mercado_gtm_inicio'),
    path('api/extraer/', views.api_extraer, name='mercado_gtm_extraer'),
    path('api/calcular/', views.api_calcular, name='mercado_gtm_calcular'),
    path('api/simular/', views.api_simular, name='mercado_gtm_simular'),
    path('api/gtm/', views.api_gtm, name='mercado_gtm_gtm'),
    path('api/preguntar/', views.api_preguntar, name='mercado_gtm_preguntar'),
    path('api/escenarios/', views.api_listar, name='mercado_gtm_listar'),
]
