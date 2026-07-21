"""
Vistas para Certificados
Verificación pública (página HTML + API JSON)
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404, FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models_certificados import Certificado
from .certificado_service import verificar_certificado_publico
import logging
import os

logger = logging.getLogger(__name__)


def _aplicar_cors_certificados(response, request):
    """CORS para clientes que aún llamen la API de verificación."""
    allowed_origin = getattr(
        settings,
        'CERT_VERIFICATION_ALLOWED_ORIGIN',
        '*',
    )
    origin = request.headers.get('Origin', '')
    if allowed_origin == '*':
        response['Access-Control-Allow-Origin'] = '*'
    elif origin and origin == allowed_origin:
        response['Access-Control-Allow-Origin'] = origin
    elif not origin:
        response['Access-Control-Allow-Origin'] = allowed_origin
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Vary'] = 'Origin'
    return response


def _ctx_verificacion(codigo: str, data: dict) -> dict:
    codigo = (codigo or '').upper()
    if not data.get('valido'):
        return {
            'valido': False,
            'codigo': codigo,
            'mensaje': data.get('error') or 'Certificado no encontrado o no válido',
        }
    fecha = data.get('fecha_emision')
    fecha_txt = ''
    if fecha:
        try:
            fecha_txt = fecha.strftime('%d/%m/%Y')
        except Exception:
            fecha_txt = str(fecha)[:10]
    return {
        'valido': True,
        'codigo': data.get('codigo') or codigo,
        'estudiante': data.get('estudiante') or '',
        'curso': data.get('curso') or '',
        'mencion': data.get('mencion') or '',
        'fecha_emision': fecha_txt,
        'calificacion': data.get('calificacion'),
        'pdf_url': data.get('pdf_url'),
    }


def verificar_certificado_view(request, codigo_verificacion):
    """
    Página pública: ¿este código es un certificado eki válido?
    Una URL única por certificado (la del QR).
    """
    codigo = (codigo_verificacion or '').strip().upper()
    data = verificar_certificado_publico(codigo)
    ctx = _ctx_verificacion(codigo, data)
    status = 200 if ctx['valido'] else 404
    return render(request, 'certificados/verificar.html', ctx, status=status)


def verificar_certificado_query_view(request):
    """
    Compatibilidad con el formato antiguo Netlify: /verificar/?code=EKI-...
    También permite pegar el código a mano.
    """
    code = (request.GET.get('code') or request.GET.get('c') or '').strip().upper()
    if code:
        return redirect('verificar_certificado', codigo_verificacion=code)
    return render(
        request,
        'certificados/verificar.html',
        {
            'valido': False,
            'codigo': '',
            'mensaje': 'Ingrese el código del certificado para verificarlo.',
        },
    )


def descargar_certificado_view(request, codigo_verificacion):
    """
    Vista para descargar el PDF del certificado
    Accesible sin autenticación (enlace público)
    """
    try:
        certificado = get_object_or_404(
            Certificado,
            codigo_verificacion__iexact=(codigo_verificacion or '').strip(),
            emitido=True,
        )

        if not certificado.archivo_pdf:
            from .certificado_service import generar_y_guardar_certificado
            generar_y_guardar_certificado(certificado)
            certificado.refresh_from_db()

        if not certificado.archivo_pdf:
            return render(
                request,
                'certificados/verificar.html',
                {
                    'valido': False,
                    'codigo': codigo_verificacion.upper(),
                    'mensaje': 'El certificado existe pero el PDF aún no está disponible.',
                },
                status=404,
            )

        try:
            path = certificado.archivo_pdf.path
            if os.path.exists(path):
                return FileResponse(
                    open(path, 'rb'),
                    as_attachment=True,
                    filename=f'certificado_{codigo_verificacion}.pdf',
                )
        except Exception:
            pass

        return redirect(certificado.archivo_pdf.url)

    except Http404:
        return render(
            request,
            'certificados/verificar.html',
            {
                'valido': False,
                'codigo': codigo_verificacion.upper(),
                'mensaje': 'Certificado no encontrado o no emitido',
            },
            status=404,
        )
    except Exception as e:
        logger.error(f"Error descargando certificado {codigo_verificacion}: {e}")
        return render(
            request,
            'certificados/verificar.html',
            {
                'valido': False,
                'codigo': codigo_verificacion.upper(),
                'mensaje': 'Error al acceder al certificado',
            },
            status=500,
        )


@csrf_exempt
def verificar_certificado_json_view(request):
    """
    Endpoint JSON (compatibilidad).
    Recibe: ?code=eki-XXXX-YYYY-ZZZZ
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
