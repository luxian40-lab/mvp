"""
Admin completo: Estudiantes, Plantillas, Campañas, EnvioLog, Sistema Educativo
CON función de envío directo desde Plantillas Y gestión de cursos/módulos/exámenes
"""
from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.admin import TabularInline as UnfoldTabularInline

# Unfold debe envolver ModelAdmin/Inlines para que add/change forms y el botón
# «Añadir» funcionen bien (Jazzmin ya no está).
admin.ModelAdmin = UnfoldModelAdmin
admin.TabularInline = UnfoldTabularInline
admin.StackedInline = UnfoldStackedInline
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin import helpers
from django.urls import path, reverse
from django.db import models, transaction  # Q(), atomic/on_commit
from django.db.models import Count  # ✅ Para agregaciones
from django.conf import settings  # ✅ Para acceder a settings
import openpyxl
from django.http import HttpResponse
from ..models import (
    Estudiante, WhatsappLog, Plantilla, Campana, EnvioLog, Linea,
    MediaPaqueteEntrega,
    Curso, ConfiguracionDripCliente, HabilitacionModuloDripCliente, HabilitacionModuloEstudiante,
    Modulo, SeccionModulo, PasoModulo, ProgresoEstudiante, ModuloCompletado,
    Examen, PreguntaExamen, ResultadoExamen, Cliente,
    PerfilGamificacion, Badge, BadgeEstudiante, TransaccionPuntos,
    SolicitudSoporte, PreguntaModulo,  # 🆘 NUEVO + 📝 PREGUNTA MODULO
    Certificado, PlantillaCertificado, # 📜 CERTIFICADOS
    CampanaUnica, RespuestaCampanaUnica,
    ProspectoB2B, CampanaB2B,  # 🤝 LEADS B2B
    AliadoEmpleabilidad, MisionEmpleabilidad, PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal,
    DocumentoRAG,  # 📚 RAG Multi-Tenant
    DocumentoRAGComercial,  # 🛒 RAG Comercial
    ProductoComercial,  # 💰 Precios Nat (Postgres)
    ProductoCatalogo,  # 📦 Catálogo recomendación Nat
    MetaMetricaEmpresa, MetaMetricaNati,
    EventoIA,
    ContextoAgroSession,
    ConversacionRAGCandidata,
)
from ..admin_campana_actualizado import CampanaUnicaAdmin, RespuestaCampanaUnicaAdmin
from ..models_extras import (
    GrupoEstudiantes, EnvioProgramado, PQRS, ArchivoModulo,
    MensajePush, EnvioMensajePush,
    EnlaceFormularioExterno, RegistroFormularioExterno,
    GrupoWhatsApp, InvitacionGrupo  # 📦 NUEVOS MODELOS
)
from ..models_audit import AuditLog  # 🔐 Auditoría
from ..recompensas import Recompensa, CanjeRecompensa
from ..utils import enviar_whatsapp_twilio, enviar_whatsapp  # Asegurar que tenemos la función
from ..widgets import ColorPickerWidget  # 🎨 Color picker para certificados
from portal.models import PortalUsuario
from django.utils import timezone  # Para timestamps
import logging
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)


def guardar_upload_admin_media(uploaded_file, *, carpeta='admin_media', prefix='media'):
    """Guarda un upload del admin en el storage activo y devuelve su URL pública.

    MP4: comprime/optimiza para WhatsApp; si tras eso supera ~16MB, rechaza (sin Twilio).
    Devuelve ``(url, meta)`` no — mantiene str URL. Meta de aptitud en form vía
    ``guardar_upload_admin_media_resultado``.
    """
    return guardar_upload_admin_media_resultado(uploaded_file, carpeta=carpeta, prefix=prefix)['url']


def guardar_upload_admin_media_resultado(
    uploaded_file, *, carpeta='admin_media', prefix='media'
) -> dict:
    """Como ``guardar_upload_admin_media`` pero con ``{url, media_wa_apto, bytes, razon}``."""
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename

    now = timezone.now()
    filename = get_valid_filename(uploaded_file.name)
    raw = uploaded_file.read()
    name_l = (filename or '').lower()
    media_wa_apto = None
    razon = ''
    # MP4: validar + optimizar para WhatsApp (63021: moov al final / High profile).
    if name_l.endswith(('.mp4', '.m4v', '.mov')):
        # Rechazar siempre basura corta / sin ftyp (EB a menudo no tiene ffprobe).
        if len(raw) < 12 or b'ftyp' not in raw[:64]:
            raise ValidationError(
                f'El video "{filename}" no es un MP4 válido (cabecera incorrecta). '
                'Exporte de nuevo como H.264 + AAC (.mp4) e intente otra vez.'
            )
        _validar_video_decodificable(raw, filename)
        try:
            from core.twilio_media import (
                WHATSAPP_VIDEO_MAX_BYTES,
                evaluar_mp4_listo_whatsapp,
                optimizar_mp4_bytes_whatsapp,
            )

            raw = optimizar_mp4_bytes_whatsapp(raw) or raw
            gate = evaluar_mp4_listo_whatsapp(raw)
            media_wa_apto = bool(gate.get('apto'))
            razon = gate.get('razon') or ''
            if not gate.get('apto'):
                mb = (gate.get('bytes') or len(raw)) / (1024 * 1024)
                raise ValidationError(
                    f'El video "{filename}" no queda apto para WhatsApp tras comprimir '
                    f'({mb:.1f} MB, {razon}). Meta/Twilio suelen fallar sobre '
                    f'{WHATSAPP_VIDEO_MAX_BYTES // (1024 * 1024)} MB o con codec inválido. '
                    'Acórtelo o baje calidad e intente de nuevo.'
                )
            # Path estable wa_safe para uploads nuevos aptos
            stem = filename.rsplit('.', 1)[0]
            filename = f'{stem}_h264_main_faststart.mp4'
            carpeta = f'{carpeta.rstrip("/")}/wa_safe'
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning('Optimización WhatsApp omitida | %s | %s', filename, exc)
            media_wa_apto = None
            razon = f'opt_omitida:{exc}'
    path = f'{carpeta}/{now:%Y/%m}/{prefix}_{now:%Y%m%d%H%M%S}_{filename}'
    saved_path = default_storage.save(path, ContentFile(raw))
    url = default_storage.url(saved_path)
    return {
        'url': url,
        'media_wa_apto': media_wa_apto,
        'bytes': len(raw),
        'razon': razon,
    }


def _validar_video_decodificable(raw: bytes, filename: str) -> None:
    """ffprobe: exige pista de video; evita subir MP4 corruptos que WhatsApp rechaza (63021)."""
    import shutil
    import subprocess
    import tempfile

    if not shutil.which('ffprobe'):
        logger.warning('ffprobe no disponible; se omite validación profunda de %s', filename)
        return
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        probe = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'csv=p=0',
                path,
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        line = (probe.stdout or '').strip()
        if probe.returncode != 0 or not line or line.startswith(','):
            err = (probe.stderr or '').strip()[:200]
            raise ValidationError(
                f'El video "{filename}" está dañado o no es reproducible '
                f'(WhatsApp lo rechazaría). Reexporte como H.264 + AAC. {err}'.strip()
            )
        # Intento corto de decode: 1 frame; si falla, el bitstream está roto.
        if shutil.which('ffmpeg'):
            dec = subprocess.run(
                [
                    'ffmpeg', '-v', 'error', '-xerror', '-i', path,
                    '-frames:v', '1', '-f', 'null', '-',
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if dec.returncode != 0:
                raise ValidationError(
                    f'El video "{filename}" no se puede decodificar (archivo corrupto). '
                    'Exporte de nuevo como MP4 H.264 + AAC e intente otra vez.'
                )
    except ValidationError:
        raise
    except Exception as exc:
        logger.warning('Validación video omitida por error: %s | %s', filename, exc)
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


# ================================================
# 🔍 FILTRO PERSONALIZADO PARA CURSOS
# ================================================

class CursosEstudianteFilter(admin.SimpleListFilter):
    """Filtro para ver estudiantes por curso inscrito"""
    title = 'Curso inscrito'
    parameter_name = 'curso'

    def lookups(self, request, model_admin):
        """Obtiene todos los cursos disponibles"""
        cursos = Curso.objects.all().order_by('nombre')
        return [(curso.id, curso.nombre) for curso in cursos] + [('sin_curso', '❌ Sin curso')]

    def queryset(self, request, queryset):
        """Filtra los estudiantes según el curso seleccionado"""
        if self.value() == 'sin_curso':
            # Estudiantes sin ningún curso
            return queryset.exclude(progresos__isnull=False)
        elif self.value():
            # Estudiantes inscritos en el curso específico
            return queryset.filter(progresos__curso_id=self.value()).distinct()
        return queryset


class GruposEstudianteFilter(admin.SimpleListFilter):
    """Filtro para ver estudiantes por grupo"""
    title = '👥 Grupo asignado'
    parameter_name = 'grupo'

    def lookups(self, request, model_admin):
        """Obtiene todos los grupos disponibles"""
        grupos = GrupoEstudiantes.objects.all().order_by('nombre')
        return [(grupo.id, f"{grupo.emoji} {grupo.nombre}") for grupo in grupos] + [('sin_grupo', '❌ Sin grupo')]

    def queryset(self, request, queryset):
        """Filtra los estudiantes según el grupo seleccionado"""
        if self.value() == 'sin_grupo':
            # Estudiantes sin ningún grupo
            return queryset.filter(grupos__isnull=True)
        elif self.value():
            # Estudiantes en el grupo específico
            return queryset.filter(grupos__id=self.value()).distinct()
        return queryset
