"""
Vistas para Certificados
Verificación pública (página HTML + API JSON)
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404, FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models_certificados import Certificado
from .certificado_service import (
    asegurar_pdf_certificado,
    generar_y_guardar_certificado,
    obtener_url_certificado_twilio,
    obtener_url_pdf_certificado,
    verificar_certificado_publico,
)
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
            'anulado': bool(data.get('anulado')),
            'motivo_anulacion': data.get('motivo_anulacion') or '',
        }
    fecha = data.get('fecha_emision')
    fecha_txt = ''
    if fecha:
        try:
            fecha_txt = fecha.strftime('%d/%m/%Y')
        except Exception:
            fecha_txt = str(fecha)[:10]
    fecha_comp = data.get('fecha_completado')
    fecha_comp_txt = ''
    if fecha_comp:
        try:
            fecha_comp_txt = fecha_comp.strftime('%d/%m/%Y')
        except Exception:
            fecha_comp_txt = str(fecha_comp)[:10]
    return {
        'valido': True,
        'codigo': data.get('codigo') or codigo,
        'estudiante': data.get('estudiante') or '',
        'cedula_enmascarada': data.get('cedula_enmascarada') or '',
        'curso': data.get('curso') or '',
        'organizacion': data.get('organizacion') or '',
        'mencion': data.get('mencion') or '',
        'fecha_emision': fecha_txt,
        'fecha_completado': fecha_comp_txt,
        'calificacion': data.get('calificacion'),
        'horas_estimadas': data.get('horas_estimadas'),
        'duracion_semanas': data.get('duracion_semanas'),
        'hash_sha256': data.get('hash_sha256') or '',
        'pdf_url': data.get('pdf_url') or data.get('descarga_url'),
        'imagen_url': data.get('imagen_url'),
        'descarga_url': data.get('descarga_url') or data.get('pdf_url'),
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
    Descarga el PDF del certificado (o PNG si aún no hay PDF).
    Accesible sin autenticación (enlace público del QR / verify).
    """
    try:
        certificado = get_object_or_404(
            Certificado,
            codigo_verificacion__iexact=(codigo_verificacion or '').strip(),
            emitido=True,
        )
        if certificado.anulado:
            return render(
                request,
                'certificados/verificar.html',
                {
                    'valido': False,
                    'codigo': (codigo_verificacion or '').upper(),
                    'mensaje': 'Este certificado fue anulado y no se puede descargar.',
                    'anulado': True,
                },
                status=410,
            )

        if not certificado.archivo_pdf:
            if not certificado.archivo_imagen:
                generar_y_guardar_certificado(certificado)
                certificado.refresh_from_db()
            else:
                asegurar_pdf_certificado(certificado)
                certificado.refresh_from_db()

        # Preferir PDF
        if certificado.archivo_pdf:
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
            pdf_url = obtener_url_pdf_certificado(certificado)
            if pdf_url:
                return redirect(pdf_url)

        # Fallback: imagen PNG (WhatsApp artifact)
        if certificado.archivo_imagen:
            try:
                path = certificado.archivo_imagen.path
                if os.path.exists(path):
                    return FileResponse(
                        open(path, 'rb'),
                        as_attachment=True,
                        filename=f'certificado_{codigo_verificacion}.png',
                    )
            except Exception:
                pass
            img_url = obtener_url_certificado_twilio(certificado)
            if img_url:
                return redirect(img_url)

        return render(
            request,
            'certificados/verificar.html',
            {
                'valido': False,
                'codigo': (codigo_verificacion or '').upper(),
                'mensaje': 'El certificado existe pero el archivo aún no está disponible.',
            },
            status=404,
        )

    except Http404:
        return render(
            request,
            'certificados/verificar.html',
            {
                'valido': False,
                'codigo': (codigo_verificacion or '').upper(),
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
                'codigo': (codigo_verificacion or '').upper(),
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
            'anulado': bool(data.get('anulado')),
        }, status=404)
        return _aplicar_cors_certificados(resp, request)

    fecha_emision = data.get('fecha_emision')
    fecha_emision_iso = fecha_emision.isoformat() if fecha_emision else None

    resp = JsonResponse({
        'valido': True,
        'codigo': data.get('codigo', code),
        'nombre_estudiante': data.get('estudiante', ''),
        'cedula_enmascarada': data.get('cedula_enmascarada', ''),
        'curso': data.get('curso', ''),
        'organizacion': data.get('organizacion', ''),
        'mencion': data.get('mencion') or '',
        'calificacion': data.get('calificacion'),
        'horas_estimadas': data.get('horas_estimadas'),
        'hash_sha256': data.get('hash_sha256') or '',
        'pdf_url': data.get('pdf_url'),
        'imagen_url': data.get('imagen_url'),
        'descarga_url': data.get('descarga_url'),
        'fecha_emision': fecha_emision_iso,
        'mensaje_error': '',
    })
    return _aplicar_cors_certificados(resp, request)
