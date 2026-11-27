from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt


from django.http import HttpResponse, JsonResponse, FileResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
import mimetypes
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, Max, Count
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from django.utils import timezone
import math
import requests
import tempfile
import os
import logging

# Logger para debugging
logger = logging.getLogger(__name__)

from ..models import Campana, Estudiante, WhatsappLog, EnvioLog, Cliente, Curso, ProgresoEstudiante, ModuloCompletado
from core.analitica.models_extras import ArchivoModulo, GrupoEstudiantes
from ..canal.envios import enviar_whatsapp, enviar_whatsapp_twilio
from ..conversacion.intent_detector import detect_intent, mensaje_indica_listo as _mensaje_indica_listo
from ..conversacion.response_templates import (
    MENSAJE_CAPTION_SOLO_MEDIA as TWILIO_CAPTION_ADJUNTO,
    get_response_for_intent,
    parte_mensaje_con_media,
)

from django.views.decorators.csrf import csrf_exempt



from .audio import _transcribir_audio_twilio





















# ---------- Webhook para WhatsApp Cloud API ----------








# --- Nat / bot comercial: lógica en core.bot_comercial.webhook ---
from core.bot_comercial.webhook import (  # noqa: E402
    _actualizar_sesion_comercial,
    _bot_comercial_diagnosticar_imagen,
    _bot_comercial_historial_reciente,
    _bot_comercial_respuesta_catalogo,
    _bot_comercial_sin_contexto_natural,
    _contexto_fallback_desde_documentos,
    _contexto_fallback_web_agro,
    _obtener_o_crear_sesion_comercial,
    _procesar_bot_comercial_twilio_webhook,
)















































import importlib


def _encolar_bot_comercial_si_async(*args, **kwargs):
    return importlib.import_module('core.views.webhook_comercial')._encolar_bot_comercial_si_async(
        *args, **kwargs,
    )


def bot_comercial_webhook(*args, **kwargs):
    return importlib.import_module('core.views.webhook_comercial').bot_comercial_webhook(*args, **kwargs)


def _encolar_twilio_edu_si_async(*args, **kwargs):
    return importlib.import_module('core.views.twilio_transporte')._encolar_twilio_edu_si_async(*args, **kwargs)


def _enviar_mensaje_twilio_segmentado(*args, **kwargs):
    return importlib.import_module('core.views.twilio_transporte')._enviar_mensaje_twilio_segmentado(
        *args, **kwargs,
    )


def _registrar_estado_twilio_callback(*args, **kwargs):
    return importlib.import_module('core.views.twilio_transporte')._registrar_estado_twilio_callback(
        *args, **kwargs,
    )


def youtube_hace_solo_enlace_en_texto(*args, **kwargs):
    return importlib.import_module('core.views.twilio_transporte').youtube_hace_solo_enlace_en_texto(
        *args, **kwargs,
    )


def _procesar_ubicacion_empleabilidad(*args, **kwargs):
    return importlib.import_module('core.views.empleabilidad')._procesar_ubicacion_empleabilidad(
        *args, **kwargs,
    )


def _radar_msg_si_aplica(*args, **kwargs):
    return importlib.import_module('core.views.empleabilidad')._radar_msg_si_aplica(*args, **kwargs)


def _intentar_responder_envio_certificado(*args, **kwargs):
    return importlib.import_module('core.views.certificados_wa')._intentar_responder_envio_certificado(
        *args, **kwargs,
    )


def _pregunta_abierta_final_pendiente(*args, **kwargs):
    return importlib.import_module('core.views.ventana_drip')._pregunta_abierta_final_pendiente(*args, **kwargs)


def _aplicar_sandbox_menu(*args, **kwargs):
    return importlib.import_module('core.views.webhook_meta')._aplicar_sandbox_menu(*args, **kwargs)


def _encolar_sandbox_si_async(*args, **kwargs):
    return importlib.import_module('core.views.webhook_meta')._encolar_sandbox_si_async(*args, **kwargs)


def _procesar_meta_webhook(*args, **kwargs):
    return importlib.import_module('core.views.webhook_meta')._procesar_meta_webhook(*args, **kwargs)


def _sandbox_inbound_repetido(*args, **kwargs):
    return importlib.import_module('core.views.webhook_meta')._sandbox_inbound_repetido(*args, **kwargs)


def _procesar_twilio_webhook(*args, **kwargs):
    return importlib.import_module('core.views.webhook_twilio')._procesar_twilio_webhook(*args, **kwargs)


def _wire_webhook_comercial_sandbox_menu() -> None:
    comercial = importlib.import_module('core.views.webhook_comercial')
    comercial._aplicar_sandbox_menu = importlib.import_module(
        'core.views.webhook_meta',
    )._aplicar_sandbox_menu


_wire_webhook_comercial_sandbox_menu()
