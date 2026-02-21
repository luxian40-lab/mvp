from django.urls import path
from core.exportar_respuestas_xlsx import exportar_respuestas_xlsx

urlpatterns_adicionales = [
    path('admin/exportar-respuestas-xlsx/<int:campana_id>/', exportar_respuestas_xlsx, name='exportar_respuestas_xlsx'),
]
