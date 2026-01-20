"""
Vistas para Certificados
Verificación pública y descarga
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404, FileResponse
from django.views.decorators.csrf import csrf_exempt
from .models_certificados import Certificado
from .certificado_service import verificar_certificado_publico
import logging
import os

logger = logging.getLogger(__name__)


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
