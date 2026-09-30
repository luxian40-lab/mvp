from django.urls import path

from core.views_video import abrir_video, progreso_video

urlpatterns = [
    path('v/<str:token>/progreso/', progreso_video, name='video_progreso'),
    path('v/<str:token>/', abrir_video, name='video_abrir'),
]
