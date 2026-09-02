from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing, name='calculadora_margen_inicio'),
    path('api/evento/', views.api_evento, name='calculadora_margen_evento'),
    path('api/calcular/', views.api_calcular, name='calculadora_margen_calcular'),
    path('api/recomendaciones/', views.api_recomendaciones, name='calculadora_margen_recomendaciones'),
    path('api/simular-precio/', views.api_simular_precio, name='calculadora_margen_simular'),
]
