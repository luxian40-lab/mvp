from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='studio_inicio'),
    path('cursos/', views.catalogo, name='studio_catalogo'),
    path('cuenta/registro/', views.cuenta_registro, name='studio_cuenta_registro'),
    path('cuenta/login/', views.cuenta_login, name='studio_cuenta_login'),
    path('cuenta/logout/', views.cuenta_logout, name='studio_cuenta_logout'),
    path('estudiante/login/', views.estudiante_login, name='studio_estudiante_login'),
    path('estudiante/whatsapp/', views.estudiante_login_whatsapp, name='studio_estudiante_whatsapp'),
    path('inscribir/<int:curso_id>/', views.inscribir, name='studio_inscribir'),
    path('pagar/<str:referencia>/', views.pagar_curso, name='studio_pagar'),
    path('pagar/<str:referencia>/resultado/', views.pagar_curso_resultado, name='studio_pagar_resultado'),
    path('pagar/<str:referencia>/confirmar/', views.pagar_curso_confirmar, name='studio_pagar_confirmar'),
    path('webhook/wompi/', views.webhook_wompi, name='studio_webhook_wompi'),
    path('creador/', views.creador, name='studio_creador'),
    path('creador/registro/', views.creador_registro, name='studio_creador_registro'),
    path('creador/panel/', views.creador_panel, name='studio_creador_panel'),
]
