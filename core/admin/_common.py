"""
Admin completo: Estudiantes, Plantillas, Campañas, EnvioLog, Sistema Educativo
CON función de envío directo desde Plantillas Y gestión de cursos/módulos/exámenes
"""
from django.contrib import admin
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
    """Guarda un upload del admin en el storage activo y devuelve su URL pública."""
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename

    now = timezone.now()
    filename = get_valid_filename(uploaded_file.name)
    path = f'{carpeta}/{now:%Y/%m}/{prefix}_{now:%Y%m%d%H%M%S}_{filename}'
    saved_path = default_storage.save(path, uploaded_file)
    return default_storage.url(saved_path)


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
