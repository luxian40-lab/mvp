from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='studio_inicio'),
    path('cursos/', views.catalogo, name='studio_catalogo'),
    path('estudiante/login/', views.estudiante_login, name='studio_estudiante_login'),
    path('inscribir/<int:curso_id>/', views.inscribir, name='studio_inscribir'),
    path('creador/', views.creador, name='studio_creador'),
]
