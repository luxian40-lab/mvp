from django.http import FileResponse, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import mimetypes
import requests

from ..models_extras import ArchivoModulo

# Endpoint proxy para servir archivos de S3 desde el dominio propio
@csrf_exempt
def serve_media_proxy(request, filename):
    s3_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{filename}"
    r = requests.get(s3_url, stream=True, timeout=(5, 30))
    if r.status_code == 200:
        content_type = r.headers.get('Content-Type', 'application/octet-stream')
        content_length = r.headers.get('Content-Length')
        # Forzar Content-Disposition inline para WhatsApp
        content_disposition = f'inline; filename="{filename}"'
        response = FileResponse(r.raw, content_type=content_type)
        if content_length:
            response['Content-Length'] = content_length
        response['Content-Disposition'] = content_disposition
        # WhatsApp/Twilio requieren CORS headers a veces
        response['Access-Control-Allow-Origin'] = '*'
        return response
    else:
        return HttpResponseBadRequest("Archivo no encontrado o error en S3")

def obtener_archivos_modulo_view(request, modulo_id):
    """
    API para obtener archivos multimedia de un módulo específico
    Usado por estudiantes para ver contenido disponible
    """
    from ..models import Modulo
    
    try:
        modulo = get_object_or_404(Modulo, id=modulo_id)
        archivos = modulo.archivos_multimedia.filter(activo=True).order_by('orden', 'id')
        
        archivos_data = []
        for archivo in archivos:
            archivos_data.append({
                'id': archivo.id,
                'tipo': archivo.get_tipo_display(),
                'titulo': archivo.titulo,
                'descripcion': archivo.descripcion,
                'url_descarga': f'/media/descargar-archivo/{archivo.id}/' if archivo.archivo else None,
                'url_externa': archivo.url_externa,
                'url_proxy': archivo.get_url_para_envio(),
                'disponible_offline': archivo.disponible_offline,
                'tamano_mb': archivo.tamano_mb(),
                'duracion_segundos': archivo.duracion_segundos,
            })
        
        return JsonResponse({
            'success': True,
            'modulo': {
                'id': modulo.id,
                'titulo': modulo.titulo,
                'numero': modulo.numero,
            },
            'archivos': archivos_data,
            'total': len(archivos_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def descargar_archivo_multimedia(request, archivo_id):
    """
    Descarga un archivo multimedia específico
    Permite descarga offline si está habilitada
    """
    try:
        archivo = get_object_or_404(ArchivoModulo, id=archivo_id)
        
        if not archivo.archivo:
            return JsonResponse({
                'error': 'Este archivo no tiene descarga disponible. Usa la URL externa.'
            }, status=400)
        
        # Verificar si la descarga offline está permitida
        if not archivo.disponible_offline:
            return JsonResponse({
                'error': 'La descarga offline no está habilitada para este archivo.'
            }, status=403)
        
        # Retornar el archivo para descarga
        response = FileResponse(archivo.archivo.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{archivo.titulo}.{archivo.archivo.name.split(".")[-1]}"'
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'Error al descargar archivo: {str(e)}'
        }, status=500)


def stream_media(request):
    """Proxy simple para servir archivos multimedia almacenados (oculta la URL S3).

    Parámetros: ?path=<ruta_relativa_en_storage>
    Ej: /media/stream/?path=modulos/2026/02/video.mp4
    """
    path = request.GET.get('path')
    if not path:
        return HttpResponseBadRequest('Falta parámetro path')

    # Normalizar y evitar traversal
    path = path.lstrip('/')
    if '..' in path:
        return HttpResponseBadRequest('Ruta inválida')

    try:
        f = default_storage.open(path, 'rb')
        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        return FileResponse(f, content_type=content_type)
    except Exception:
        return HttpResponse(status=404)
