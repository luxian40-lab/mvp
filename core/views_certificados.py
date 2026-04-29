"""
Vistas para Certificados
Verificación pública y descarga
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404, FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models_certificados import Certificado
from .certificado_service import verificar_certificado_publico
import logging
import os

logger = logging.getLogger(__name__)


def _aplicar_cors_certificados(response, request):
    """Aplica CORS para la landing de verificación de certificados."""
    allowed_origin = getattr(
        settings,
        'CERT_VERIFICATION_ALLOWED_ORIGIN',
        'https://certificadosseki.netlify.app',
    )
    origin = request.headers.get('Origin', '')
    if origin and origin == allowed_origin:
        response['Access-Control-Allow-Origin'] = origin
    elif not origin:
        # Peticiones sin Origin (curl/postman/navegador directo)
        response['Access-Control-Allow-Origin'] = allowed_origin
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Vary'] = 'Origin'
    return response


def verificar_certificado_view(request, codigo_verificacion):
    """
    Vista pública para verificar un certificado
    Accesible sin autenticación
    Muestra PDF embebido en navegador
    """
    try:
        # Buscar certificado emitido
        try:
            certificado = Certificado.objects.get(
                codigo_verificacion=codigo_verificacion.upper(), 
                emitido=True
            )
        except Certificado.DoesNotExist:
            return render(request, 'certificados/error.html', {
                'mensaje': f'Certificado {codigo_verificacion.upper()} no encontrado o no emitido',
                'codigo': codigo_verificacion.upper()
            }, status=404)
        
        # Generar PDF si no existe
        if not certificado.archivo_pdf or not os.path.exists(certificado.archivo_pdf.path):
            from .certificado_service import generar_y_guardar_certificado
            generar_y_guardar_certificado(certificado)
        
        # Servir PDF embebido en navegador
        response = FileResponse(
            open(certificado.archivo_pdf.path, 'rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'inline; filename="certificado_{codigo_verificacion}.pdf"'
        return response
        
    except Exception as e:
        logger.error(f"Error verificando certificado {codigo_verificacion}: {e}")
        return render(request, 'certificados/error.html', {
            'mensaje': 'Error al generar o acceder al certificado',
            'codigo': codigo_verificacion.upper()
        }, status=500)
        return render(request, 'certificados/error.html', {
            'mensaje': 'Error al generar o acceder al certificado',
            'codigo': codigo_verificacion.upper(),
            'error': str(e)
        }, status=500)


def descargar_certificado_view(request, codigo_verificacion):
    """
    Vista para descargar el PDF del certificado
    Accesible sin autenticación (enlace público)
    """
    try:
        certificado = get_object_or_404(
            Certificado,
            codigo_verificacion=codigo_verificacion.upper(),
            emitido=True
        )
        
        # Generar PDF si no existe
        if not certificado.archivo_pdf or not os.path.exists(certificado.archivo_pdf.path):
            from .certificado_service import generar_y_guardar_certificado
            generar_y_guardar_certificado(certificado)
        
        if not certificado.archivo_pdf:
            return render(request, 'certificados/error.html', {
                'mensaje': 'No fue posible generar el certificado',
                'codigo': codigo_verificacion.upper()
            }, status=500)
        
        # Abrir y servir el PDF
        pdf_file = open(certificado.archivo_pdf.path, 'rb')
        response = FileResponse(
            pdf_file,
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="certificado_{codigo_verificacion.upper()}.pdf"'
        
        return response
        
    except Certificado.DoesNotExist:
        return render(request, 'certificados/error.html', {
            'mensaje': f'Certificado {codigo_verificacion.upper()} no encontrado',
            'codigo': codigo_verificacion.upper()
        }, status=404)
    except Exception as e:
        logger.error(f"Error descargando certificado {codigo_verificacion}: {e}")
        return render(request, 'certificados/error.html', {
            'mensaje': 'Error al descargar el certificado',
            'codigo': codigo_verificacion.upper()
        }, status=500)


@csrf_exempt
def verificar_certificado_json_view(request):
    """
    Endpoint JSON para landing externa (Netlify).
    Recibe: ?code=eki-XXXX-YYYY-ZZZZ
    Devuelve:
      - valido
      - nombre_estudiante
      - curso
      - fecha_emision
      - codigo
      - mensaje_error (si no existe)
    """
    if request.method == 'OPTIONS':
        return _aplicar_cors_certificados(HttpResponse(status=204), request)

    if request.method != 'GET':
        resp = JsonResponse({'valido': False, 'mensaje_error': 'Método no permitido'}, status=405)
        return _aplicar_cors_certificados(resp, request)

    code = (request.GET.get('code', '') or '').strip().upper()
    if not code:
        resp = JsonResponse({
            'valido': False,
            'codigo': '',
            'nombre_estudiante': '',
            'curso': '',
            'fecha_emision': None,
            'mensaje_error': 'Parámetro code es obligatorio',
        }, status=400)
        return _aplicar_cors_certificados(resp, request)

    data = verificar_certificado_publico(code)
    if not data.get('valido'):
        resp = JsonResponse({
            'valido': False,
            'codigo': code,
            'nombre_estudiante': '',
            'curso': '',
            'fecha_emision': None,
            'mensaje_error': data.get('error', 'Certificado no encontrado'),
        }, status=404)
        return _aplicar_cors_certificados(resp, request)

    fecha_emision = data.get('fecha_emision')
    fecha_emision_iso = fecha_emision.isoformat() if fecha_emision else None

    resp = JsonResponse({
        'valido': True,
        'codigo': data.get('codigo', code),
        'nombre_estudiante': data.get('estudiante', ''),
        'curso': data.get('curso', ''),
        'fecha_emision': fecha_emision_iso,
        'mensaje_error': '',
    })
    return _aplicar_cors_certificados(resp, request)
