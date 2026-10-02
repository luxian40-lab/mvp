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
from ..models_extras import ArchivoModulo, GrupoEstudiantes
from ..utils import enviar_whatsapp, enviar_whatsapp_twilio
from ..intent_detector import detect_intent, mensaje_indica_listo as _mensaje_indica_listo
from ..response_templates import (
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















































from .webhook_comercial import _encolar_bot_comercial_si_async, bot_comercial_webhook

from .twilio_transporte import (
    _encolar_twilio_edu_si_async,
    _enviar_mensaje_twilio_segmentado,
    _registrar_estado_twilio_callback,
    youtube_hace_solo_enlace_en_texto,
)

from .empleabilidad import (
    _procesar_ubicacion_empleabilidad,
    _radar_msg_si_aplica,
)
from .certificados_wa import _intentar_responder_envio_certificado
from .ventana_drip import _pregunta_abierta_final_pendiente

from .webhook_meta import (
    _aplicar_sandbox_menu,
    _encolar_sandbox_si_async,
    _procesar_meta_webhook,
    _sandbox_inbound_repetido,
)
from . import webhook_comercial as _webhook_comercial_mod
_webhook_comercial_mod._aplicar_sandbox_menu = _aplicar_sandbox_menu
from .webhook_twilio import _procesar_twilio_webhook
