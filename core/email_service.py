"""
Servicio de Email con soporte para APIs
Soporta: SendGrid, Resend, Mailgun, y SMTP fallback
"""

import logging
import requests
from django.conf import settings
from typing import List, Optional, Dict
import os

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio unificado de email con soporte multi-proveedor"""
    
    def __init__(self):
        self.provider = self._detect_provider()
        logger.info(f"📧 EmailService inicializado con proveedor: {self.provider}")
    
    def _detect_provider(self) -> str:
        """Detecta qué proveedor usar basado en variables de entorno"""
        if os.environ.get('RESEND_API_KEY'):
            return 'resend'
        elif os.environ.get('SENDGRID_API_KEY'):
            return 'sendgrid'
        elif os.environ.get('MAILGUN_API_KEY'):
            return 'mailgun'
        elif os.environ.get('EMAIL_HOST_USER'):
            return 'smtp'
        else:
            return 'console'  # Para desarrollo
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Envía un email usando el proveedor configurado
        
        Args:
            to_emails: Lista de emails destino
            subject: Asunto del email
            body: Cuerpo del email (texto plano)
            from_email: Email remitente (opcional)
            attachments: Lista de adjuntos [{filename, content, content_type}]
            html_body: Cuerpo HTML (opcional)
        
        Returns:
            bool: True si se envió exitosamente
        """
        if not to_emails:
            logger.error("❌ No hay destinatarios especificados")
            return False
        
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        
        try:
            if self.provider == 'resend':
                return self._send_resend(to_emails, subject, body, from_email, attachments, html_body)
            elif self.provider == 'sendgrid':
                return self._send_sendgrid(to_emails, subject, body, from_email, attachments, html_body)
            elif self.provider == 'mailgun':
                return self._send_mailgun(to_emails, subject, body, from_email, attachments, html_body)
            elif self.provider == 'smtp':
                return self._send_smtp(to_emails, subject, body, from_email, attachments, html_body)
            else:
                # Desarrollo: solo log
                logger.info(f"📧 [CONSOLE] Email a {to_emails}: {subject}")
                return True
        
        except Exception as e:
            logger.error(f"❌ Error enviando email: {e}", exc_info=True)
            return False
    
    def _send_resend(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        from_email: str,
        attachments: Optional[List[Dict]],
        html_body: Optional[str]
    ) -> bool:
        """
        Resend API - Moderna y simple
        https://resend.com/docs/api-reference/emails/send-email
        """
        api_key = os.environ.get('RESEND_API_KEY')
        
        payload = {
            'from': from_email,
            'to': to_emails,
            'subject': subject,
            'text': body,
        }
        
        if html_body:
            payload['html'] = html_body
        
        # Adjuntos en Resend
        if attachments:
            payload['attachments'] = []
            for att in attachments:
                import base64
                content_b64 = base64.b64encode(att['content']).decode('utf-8')
                payload['attachments'].append({
                    'filename': att['filename'],
                    'content': content_b64,
                })
        
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=payload
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Email enviado vía Resend a {to_emails}")
            return True
        else:
            logger.error(f"❌ Error Resend: {response.status_code} - {response.text}")
            return False
    
    def _send_sendgrid(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        from_email: str,
        attachments: Optional[List[Dict]],
        html_body: Optional[str]
    ) -> bool:
        """
        SendGrid API v3
        https://docs.sendgrid.com/api-reference/mail-send/mail-send
        """
        api_key = os.environ.get('SENDGRID_API_KEY')
        
        payload = {
            'personalizations': [{
                'to': [{'email': email} for email in to_emails],
                'subject': subject
            }],
            'from': {'email': from_email},
            'content': [
                {'type': 'text/plain', 'value': body}
            ]
        }
        
        if html_body:
            payload['content'].append({'type': 'text/html', 'value': html_body})
        
        # Adjuntos en SendGrid
        if attachments:
            payload['attachments'] = []
            for att in attachments:
                import base64
                content_b64 = base64.b64encode(att['content']).decode('utf-8')
                payload['attachments'].append({
                    'content': content_b64,
                    'filename': att['filename'],
                    'type': att.get('content_type', 'application/pdf'),
                    'disposition': 'attachment'
                })
        
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=payload
        )
        
        if response.status_code == 202:
            logger.info(f"✅ Email enviado vía SendGrid a {to_emails}")
            return True
        else:
            logger.error(f"❌ Error SendGrid: {response.status_code} - {response.text}")
            return False
    
    def _send_mailgun(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        from_email: str,
        attachments: Optional[List[Dict]],
        html_body: Optional[str]
    ) -> bool:
        """
        Mailgun API
        https://documentation.mailgun.com/en/latest/api-sending.html
        """
        api_key = os.environ.get('MAILGUN_API_KEY')
        domain = os.environ.get('MAILGUN_DOMAIN', 'mg.eki.com')
        
        data = {
            'from': from_email,
            'to': to_emails,
            'subject': subject,
            'text': body,
        }
        
        if html_body:
            data['html'] = html_body
        
        files = []
        if attachments:
            for att in attachments:
                files.append(('attachment', (att['filename'], att['content'])))
        
        response = requests.post(
            f'https://api.mailgun.net/v3/{domain}/messages',
            auth=('api', api_key),
            data=data,
            files=files if files else None
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Email enviado vía Mailgun a {to_emails}")
            return True
        else:
            logger.error(f"❌ Error Mailgun: {response.status_code} - {response.text}")
            return False
    
    def _send_smtp(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        from_email: str,
        attachments: Optional[List[Dict]],
        html_body: Optional[str]
    ) -> bool:
        """Fallback a SMTP tradicional usando Django"""
        from django.core.mail import EmailMessage
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to_emails,
        )
        
        if html_body:
            email.content_subtype = 'html'
            email.body = html_body
        
        if attachments:
            for att in attachments:
                email.attach(
                    att['filename'],
                    att['content'],
                    att.get('content_type', 'application/pdf')
                )
        
        email.send()
        logger.info(f"✅ Email enviado vía SMTP a {to_emails}")
        return True


def enviar_certificados_a_cliente(cliente, certificados_list):
    """
    Envía certificados por email al cliente usando EmailService
    
    Args:
        cliente: Instancia de Cliente
        certificados_list: Lista de instancias de Certificado
    
    Returns:
        bool: True si se envió exitosamente
    """
    if not cliente.enviar_certificados_email:
        logger.info(f"ℹ️ Cliente {cliente.nombre} no tiene habilitado envío de certificados")
        return False
    
    if not certificados_list:
        logger.warning(f"⚠️ No hay certificados para enviar a {cliente.nombre}")
        return False
    
    email_service = EmailService()
    
    # Construir cuerpo del email
    subject = f'Certificados de {len(certificados_list)} estudiante(s) - eki'
    
    body = f"""Estimado/a {cliente.contacto_principal},

Adjuntamos los certificados de {len(certificados_list)} estudiante(s) de su organización "{cliente.nombre}":

"""
    for cert in certificados_list:
        body += f"• {cert.estudiante.nombre} - {cert.curso.nombre} ({cert.calificacion_final}%)\n"
    
    body += f"""

Códigos de verificación:
"""
    for cert in certificados_list:
        url_verificacion = cert.obtener_url_verificacion()
        body += f"• {cert.estudiante.nombre}: {cert.codigo_verificacion}\n  {url_verificacion}\n\n"
    
    body += """
Estos certificados pueden ser verificados en cualquier momento usando los códigos de verificación.

Saludos cordiales,
Equipo eki
"""
    
    # Preparar adjuntos
    attachments = []
    for cert in certificados_list:
        try:
            pdf_file = cert.archivo_pdf.open('rb')
            pdf_content = pdf_file.read()
            pdf_file.close()
            
            filename = f"{cert.estudiante.nombre.replace(' ', '_')}_{cert.codigo_verificacion}.pdf"
            attachments.append({
                'filename': filename,
                'content': pdf_content,
                'content_type': 'application/pdf'
            })
        except Exception as e:
            logger.error(f"Error leyendo PDF {cert.codigo_verificacion}: {e}")
    
    # Enviar
    try:
        success = email_service.send_email(
            to_emails=[cliente.email],
            subject=subject,
            body=body,
            attachments=attachments
        )
        
        if success:
            logger.info(f"✅ Certificados enviados a {cliente.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error enviando certificados a {cliente.email}: {e}", exc_info=True)
        return False


# Singleton global
_email_service = None

def get_email_service() -> EmailService:
    """Obtiene instancia singleton del servicio de email"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
