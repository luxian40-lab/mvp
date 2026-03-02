"""
Utilidades para probar la configuración de email
"""

from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def test_gmail_connection():
    """
    Prueba la conexión con Gmail
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not settings.EMAIL_HOST_USER:
        return False, "❌ EMAIL_HOST_USER no está configurado"
    
    if not settings.EMAIL_HOST_PASSWORD:
        return False, "❌ EMAIL_HOST_PASSWORD no está configurado"
    
    try:
        # Intentar enviar email de prueba
        send_mail(
            subject='🧪 Prueba de Conexión - eki',
            message='Este es un email de prueba para verificar que la configuración de Gmail está funcionando correctamente.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],  # Se envía a sí mismo
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de prueba enviado exitosamente a {settings.EMAIL_HOST_USER}")
        return True, f"✅ Conexión exitosa! Email de prueba enviado a {settings.EMAIL_HOST_USER}"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error probando Gmail: {error_msg}")
        
        # Mensajes de error comunes y sus soluciones
        if "authentication failed" in error_msg.lower():
            return False, """❌ Error de autenticación. Soluciones:
            
1. Verifica que usas una CONTRASEÑA DE APLICACIÓN (no tu contraseña normal)
2. Pasos para crear contraseña de aplicación:
   - Ve a https://myaccount.google.com/security
   - Activa "Verificación en 2 pasos" si no está activa
   - Busca "Contraseñas de aplicaciones"
   - Genera una nueva para "Correo" > "Otro (Django)"
   - Usa esa contraseña de 16 caracteres en EMAIL_HOST_PASSWORD
3. Reinicia el servidor después de cambiar las variables de entorno"""
        
        elif "timed out" in error_msg.lower():
            return False, "❌ Timeout de conexión. Verifica tu conexión a internet."
        
        else:
            return False, f"❌ Error: {error_msg}"


def get_email_status():
    """
    Obtiene el estado de la configuración de email
    
    Returns:
        dict: Estado de la configuración
    """
    status = {
        'configurado': False,
        'backend': settings.EMAIL_BACKEND,
        'host': settings.EMAIL_HOST,
        'port': settings.EMAIL_PORT,
        'use_tls': settings.EMAIL_USE_TLS,
        'usuario': settings.EMAIL_HOST_USER or 'No configurado',
        'password_set': bool(settings.EMAIL_HOST_PASSWORD),
        'from_email': settings.DEFAULT_FROM_EMAIL,
    }
    
    status['configurado'] = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    
    return status


def format_email_status_html():
    """
    Formatea el estado de email como HTML para el admin
    
    Returns:
        str: HTML con el estado
    """
    status = get_email_status()
    
    if status['configurado']:
        badge = '<span style="background:#4caf50;color:white;padding:8px 16px;border-radius:20px;font-weight:bold;">✅ CONFIGURADO</span>'
    else:
        badge = '<span style="background:#f44336;color:white;padding:8px 16px;border-radius:20px;font-weight:bold;">❌ NO CONFIGURADO</span>'
    
    html = f"""
    <div style="background:#f5f5f5;padding:20px;border-radius:8px;margin:10px 0;">
        <h3 style="margin-top:0;">📧 Estado de Configuración de Email</h3>
        {badge}
        <br><br>
        <table style="width:100%;border-collapse:collapse;">
            <tr style="border-bottom:1px solid #ddd;">
                <td style="padding:8px;font-weight:bold;">Backend:</td>
                <td style="padding:8px;"><code>{status['backend']}</code></td>
            </tr>
            <tr style="border-bottom:1px solid #ddd;">
                <td style="padding:8px;font-weight:bold;">Servidor:</td>
                <td style="padding:8px;"><code>{status['host']}:{status['port']}</code></td>
            </tr>
            <tr style="border-bottom:1px solid #ddd;">
                <td style="padding:8px;font-weight:bold;">Usuario (Gmail):</td>
                <td style="padding:8px;"><code>{status['usuario']}</code></td>
            </tr>
            <tr style="border-bottom:1px solid #ddd;">
                <td style="padding:8px;font-weight:bold;">Contraseña configurada:</td>
                <td style="padding:8px;">{'✅ Sí' if status['password_set'] else '❌ No'}</td>
            </tr>
            <tr style="border-bottom:1px solid #ddd;">
                <td style="padding:8px;font-weight:bold;">Email remitente:</td>
                <td style="padding:8px;"><code>{status['from_email']}</code></td>
            </tr>
            <tr>
                <td style="padding:8px;font-weight:bold;">TLS:</td>
                <td style="padding:8px;">{'✅ Activado' if status['use_tls'] else '❌ Desactivado'}</td>
            </tr>
        </table>
    </div>
    """
    
    if not status['configurado']:
        html += """
        <div style="background:#fff3e0;padding:15px;border-left:4px solid #ff9800;margin:10px 0;">
            <strong>⚠️ Configuración Pendiente</strong>
            <ol style="margin:10px 0;">
                <li>Ve a <a href="https://myaccount.google.com/security" target="_blank">Seguridad de Google</a></li>
                <li>Activa "Verificación en 2 pasos" si no está activa</li>
                <li>Busca "Contraseñas de aplicaciones"</li>
                <li>Genera una para "Correo" > "Otro (Django)"</li>
                <li>Agrega estas variables de entorno:
                    <pre style="background:#f5f5f5;padding:10px;border-radius:4px;margin:10px 0;">
EMAIL_HOST_USER=tu_email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=tu_email@gmail.com</pre>
                </li>
                <li>Reinicia el servidor Django</li>
            </ol>
        </div>
        """
    
    return html
