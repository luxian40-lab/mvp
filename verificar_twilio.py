#!/usr/bin/env python
"""
Verificar conexión con Twilio
"""

import os
import logging
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from twilio.rest import Client
from twilio.base.exceptions import TwilioException

logger = logging.getLogger("verificar_twilio")

def verificar_twilio():
    logger.info('🔍 Verificando conexión con Twilio...')

    # Variables de entorno
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    phone_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    template_anuncio = os.environ.get('TWILIO_TEMPLATE_ANUNCIO_GRUPAL')
    template_invitacion = os.environ.get('TWILIO_TEMPLATE_INVITACION_GRUPO')

    logger.info(f'📱 Account SID: {"✅" if account_sid else "❌"} {account_sid[:10] + "..." if account_sid else "No configurado"}')
    logger.info(f'🔑 Auth Token: {"✅" if auth_token else "❌"} {"Configurado" if auth_token else "No configurado"}')
    logger.info(f'📞 WhatsApp Number: {phone_number or "❌ No configurado"}')
    logger.info(f'📢 Template Anuncio: {template_anuncio or "❌ No configurado"}')
    logger.info(f'👥 Template Invitación: {template_invitacion or "❌ No configurado"}')

    if account_sid and auth_token:
        try:
            client = Client(account_sid, auth_token)
            account = client.api.accounts(account_sid).fetch()
            logger.info(f'✅ Conexión exitosa - Account: {account.friendly_name}')

            # Verificar templates disponibles
            try:
                templates = client.content.v1.contents.list(limit=10)
                logger.info(f'📋 Content Templates encontrados: {len(templates)}')

                for i, template in enumerate(templates[:5], 1):
                    logger.info(f'  {i}. {template.sid} - {template.friendly_name}')

                # Verificar templates específicos del sistema
                system_templates = [template_anuncio, template_invitacion]
                for sid in system_templates:
                    if sid:
                        try:
                            template = client.content.v1.contents(sid).fetch()
                            logger.info(f'✅ Template {sid}: {template.friendly_name}')
                        except Exception as e:
                            logger.warning(f'❌ Template {sid}: No encontrado - {str(e)[:50]}...')

            except Exception as e:
                logger.warning(f'⚠️ Error al listar templates: {str(e)[:100]}...')

        except TwilioException as e:
            logger.error(f'❌ Error de autenticación Twilio: {e}')
        except Exception as e:
            logger.error(f'❌ Error general: {str(e)[:100]}...')
    else:
        logger.error('❌ Configuración incompleta - faltan credenciales')

if __name__ == '__main__':
    verificar_twilio()