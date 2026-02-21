from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from openpyxl import Workbook
from .models import CampanaUnica, RespuestaCampanaUnica

@staff_member_required
def exportar_respuestas_xlsx(request, campana_id):
    """Descargar los números que respondieron SÍ en XLSX"""
    campana = CampanaUnica.objects.get(id=campana_id)
    respuestas_si = RespuestaCampanaUnica.objects.filter(
        campana=campana,
        respuesta='si'
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Respuestas SI"
    ws.append(['Número de Teléfono', 'Fecha de Respuesta', 'Nombre Estudiante'])

    for respuesta in respuestas_si:
        nombre = respuesta.estudiante.nombre if respuesta.estudiante else "No identificado"
        ws.append([
            respuesta.numero_telefono,
            respuesta.fecha_respuesta.strftime('%Y-%m-%d %H:%M:%S'),
            nombre
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="respuestas_si_{campana.id}.xlsx"'
    wb.save(response)
    return response
