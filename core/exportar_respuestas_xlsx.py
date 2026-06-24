from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from openpyxl import Workbook
from .models import CampanaUnica, RespuestaCampanaUnica

def _hoja_respuestas(ws, respuestas):
    ws.append(['Teléfono', 'Respuesta', 'Nombre', 'Fecha'])
    for r in respuestas.select_related('estudiante'):
        nombre = r.estudiante.nombre if r.estudiante else 'No identificado'
        ws.append([
            r.numero_telefono,
            r.get_respuesta_display(),
            nombre,
            r.fecha_respuesta.strftime('%Y-%m-%d %H:%M:%S'),
        ])


@staff_member_required
def exportar_respuestas_xlsx(request, campana_id):
    """Descargar respuestas de campaña (hojas Sí y No)."""
    campana = CampanaUnica.objects.get(id=campana_id)
    todas = RespuestaCampanaUnica.objects.filter(campana=campana).order_by('-fecha_respuesta')

    wb = Workbook()
    ws_si = wb.active
    ws_si.title = 'Respondieron Sí'
    _hoja_respuestas(ws_si, todas.filter(respuesta='si'))

    ws_no = wb.create_sheet('Respondieron No')
    _hoja_respuestas(ws_no, todas.filter(respuesta='no'))

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="respuestas_campana_{campana.id}.xlsx"'
    )
    wb.save(response)
    return response
