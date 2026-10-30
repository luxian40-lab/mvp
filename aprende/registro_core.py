"""Registra en core lo que antes core importaba de esta app. Fase H3."""
from core.puentes import registrar

from aprende.acceso_whatsapp import client_ip_from_request as _client_ip_from_request
registrar('client_ip_from_request', _client_ip_from_request)
from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp as _emitir_acceso_desde_whatsapp
registrar('emitir_acceso_desde_whatsapp', _emitir_acceso_desde_whatsapp)
from aprende.acceso_whatsapp import mensaje_pide_acceso_aula as _mensaje_pide_acceso_aula
registrar('mensaje_pide_acceso_aula', _mensaje_pide_acceso_aula)
from aprende.views_admin import aula_web_admin_view as _aula_web_admin_view
registrar('aula_web_admin_view', _aula_web_admin_view)
