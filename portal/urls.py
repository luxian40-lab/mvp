from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.portal_login, name='portal_login'),
    path('logout/', views.portal_logout, name='portal_logout'),
    path('dashboard/', views.dashboard, name='portal_dashboard'),
    path('metricas/', views.metricas_empresa, name='portal_metricas'),
    path('gamificacion/', views.portal_gamificacion, name='portal_gamificacion'),
    path('cobertura/', views.portal_cobertura, name='portal_cobertura'),
    path('cobertura/datos.json', views.portal_cobertura_api, name='portal_cobertura_api'),
    path('cobertura/departamentos.geojson', views.portal_cobertura_geojson, name='portal_cobertura_geojson'),
    path('cobertura/municipios.geojson', views.portal_cobertura_municipios_geojson, name='portal_cobertura_municipios_geojson'),
    path('gei/', views.portal_gei, name='portal_gei'),
    path('gei/exportar/', views.portal_gei_exportar, name='portal_gei_exportar'),
    path('gei/<int:ficha_id>/', views.portal_gei_detalle, name='portal_gei_detalle'),
    path('nat/', views.portal_nat, name='portal_nat'),
    path('campanas/', views.campanas_lista, name='portal_campanas'),
    path('campanas/<int:campana_id>/', views.campana_detalle, name='portal_campana_detalle'),
    path('estudiantes/', views.estudiantes, name='portal_estudiantes'),
    path('estudiantes/exportar/', views.exportar_estudiantes_excel, name='portal_exportar_estudiantes'),
    path('estudiantes/<int:estudiante_id>/', views.estudiante_detalle, name='portal_estudiante_detalle'),
    path('cursos/', views.cursos_lista, name='portal_cursos'),
    path('pqrs/', views.pqrs_lista, name='portal_pqrs'),
    path('pqrs/<int:pqrs_id>/', views.pqrs_detalle, name='portal_pqrs_detalle'),
    path('perfil/', views.perfil_organizacion, name='portal_perfil'),
    path('suscripcion-vencida/', views.suscripcion_vencida, name='portal_vencida'),
]
