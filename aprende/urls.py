from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='aprende_inicio'),
    path('estudiante/login/', views.estudiante_login, name='aprende_estudiante_login'),
    path('estudiante/logout/', views.estudiante_logout, name='aprende_estudiante_logout'),
    path('estudiante/', views.estudiante_cursos, name='aprende_estudiante_cursos'),
    path('estudiante/inscribir/<int:curso_id>/', views.estudiante_inscribir, name='aprende_estudiante_inscribir'),
    path('estudiante/curso/<int:curso_id>/', views.estudiante_curso, name='aprende_estudiante_curso'),
    path('estudiante/modulo/<int:modulo_id>/', views.estudiante_modulo, name='aprende_estudiante_modulo'),
    path('profesor/login/', views.profesor_login, name='aprende_profesor_login'),
    path('profesor/logout/', views.profesor_logout, name='aprende_profesor_logout'),
    path('profesor/', views.profesor_cursos, name='aprende_profesor_cursos'),
    path('profesor/curso/<int:curso_id>/', views.profesor_curso, name='aprende_profesor_curso'),
    path('profesor/curso/<int:curso_id>/modulo/nuevo/', views.profesor_modulo_nuevo, name='aprende_profesor_modulo_nuevo'),
    path('profesor/modulo/<int:modulo_id>/', views.profesor_modulo_editar, name='aprende_profesor_modulo_editar'),
]
