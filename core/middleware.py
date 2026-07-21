"""
Middleware para Rate Limiting
Previene spam y abuso de API
"""

import time
import uuid
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class RequestContextMiddleware(MiddlewareMixin):
    """
    Agrega request_id para trazabilidad básica en logs y respuestas.
    """

    def process_request(self, request):
        request.request_id = request.META.get('HTTP_X_REQUEST_ID') or str(uuid.uuid4())
        request._request_start_ts = time.time()
        return None

    def process_response(self, request, response):
        request_id = getattr(request, 'request_id', None)
        if request_id:
            response['X-Request-ID'] = request_id

        start_ts = getattr(request, '_request_start_ts', None)
        if start_ts is not None:
            duration_ms = int((time.time() - start_ts) * 1000)
            # Log de acceso mínimo para operar webhooks/APIs en producción.
            logger.info(
                "request_done",
                extra={
                    "request_id": request_id,
                    "method": getattr(request, "method", ""),
                    "path": getattr(request, "path", ""),
                    "status_code": getattr(response, "status_code", 0),
                    "duration_ms": duration_ms,
                },
            )
        return response

class RateLimitMiddleware(MiddlewareMixin):
    """
    Middleware para limitar el número de requests por IP/usuario
    
    Configuración en settings.py:
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = 100  # requests permitidos
    RATE_LIMIT_PERIOD = 60     # por periodo de X segundos (1 minuto)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def get_client_ip(self, request):
        """Obtiene la IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def process_request(self, request):
        """Verifica rate limit antes de procesar el request"""
        from django.conf import settings
        
        # Verificar si rate limiting está habilitado
        if not getattr(settings, 'RATE_LIMIT_ENABLED', False):
            return None
        
        # Rutas excluidas del rate limit
        excluded_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
        ]
        
        for path in excluded_paths:
            if request.path.startswith(path):
                return None
        
        # Obtener IP y parámetros
        ip = self.get_client_ip(request)
        limit_requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        limit_period = getattr(settings, 'RATE_LIMIT_PERIOD', 60)
        
        # Cache key
        cache_key = f"rate_limit:{ip}"
        
        # Obtener contador actual
        request_count = cache.get(cache_key, 0)
        
        if request_count >= limit_requests:
            logger.warning(f"Rate limit excedido para IP: {ip}")
            return HttpResponse(
                'Rate limit excedido. Intenta de nuevo más tarde.',
                status=429  # Too Many Requests
            )
        
        # Incrementar contador
        cache.set(cache_key, request_count + 1, limit_period)
        
        return None


class WhatsAppRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware específico para limitar envíos por WhatsApp
    Previene envío accidental de múltiples mensajes al mismo número
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Verifica rate limit para WhatsApp"""
        from django.conf import settings
        
        # Solo para endpoints de WhatsApp
        if not request.path.startswith('/api/whatsapp/') and not request.path.startswith('/webhook/whatsapp/'):
            return None
        
        # Obtener teléfono destino
        telefono = request.GET.get('to') or request.POST.get('to')
        
        if not telefono:
            return None
        
        # Límites por teléfono
        max_mensajes = getattr(settings, 'WHATSAPP_RATE_LIMIT', 5)  # 5 mensajes
        periodo = getattr(settings, 'WHATSAPP_RATE_PERIOD', 60)     # en 60 segundos
        
        cache_key = f"whatsapp_limit:{telefono}"
        mensajes_enviados = cache.get(cache_key, 0)
        
        if mensajes_enviados >= max_mensajes:
            logger.warning(f"Rate limit de WhatsApp excedido para: {telefono}")
            return HttpResponse(
                f'Demasiados mensajes al mismo número. Espera {periodo} segundos.',
                status=429
            )
        
        # Incrementar contador
        cache.set(cache_key, mensajes_enviados + 1, periodo)
        
        return None


class CertificadoAccessMiddleware(MiddlewareMixin):
    """
    Middleware para registrar accesos a certificados públicos
    Auditoría de quién accede a los certificados
    """
    
    def process_request(self, request):
        """Registra acceso a certificados públicos"""
        
        # Solo para URLs públicas de certificados
        if '/verificar-certificado/' not in request.path:
            return None
        
        # Extraer código del certificado
        import re
        match = re.search(r'/verificar-certificado/([A-Za-z0-9\-]+)/', request.path)
        
        if not match:
            return None
        
        codigo = match.group(1)
        ip = self._get_client_ip(request)
        
        # Registrar en audit log
        try:
            from core.models_audit import AuditLog
            AuditLog.registrar(
                accion='VERIFICAR',
                certificado=codigo,  # Pasar el código, el método lo procesa
                ip_address=ip,
                exitoso=True
            )
        except Exception as e:
            logger.error(f"Error registrando acceso a certificado: {str(e)}")
        
        return None
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
