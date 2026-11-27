"""Reexportes lazy para no enlazar el paquete views al SCC por imports estáticos."""
from __future__ import annotations

import importlib

_ATTRS: dict[str, tuple[str, str]] = {
    # legacy
    '_bot_comercial_respuesta_catalogo': ('core.views.legacy', '_bot_comercial_respuesta_catalogo'),
    '_bot_comercial_sin_contexto_natural': ('core.views.legacy', '_bot_comercial_sin_contexto_natural'),
    '_contexto_fallback_web_agro': ('core.views.legacy', '_contexto_fallback_web_agro'),
    '_procesar_bot_comercial_twilio_webhook': ('core.views.legacy', '_procesar_bot_comercial_twilio_webhook'),
    # entrada / webhooks
    'whatsapp_webhook': ('core.views.entrada', 'whatsapp_webhook'),
    '_procesar_twilio_webhook': ('core.views.webhook_twilio', '_procesar_twilio_webhook'),
    '_aplicar_sandbox_menu': ('core.views.webhook_meta', '_aplicar_sandbox_menu'),
    '_procesar_meta_webhook': ('core.views.webhook_meta', '_procesar_meta_webhook'),
    # empleabilidad
    '_activar_radar_empleabilidad_si_aplica': ('core.views.empleabilidad', '_activar_radar_empleabilidad_si_aplica'),
    '_haversine_metros': ('core.views.empleabilidad', '_haversine_metros'),
    '_procesar_ubicacion_empleabilidad': ('core.views.empleabilidad', '_procesar_ubicacion_empleabilidad'),
    # certificados
    '_es_ack_certificado': ('core.views.certificados_wa', '_es_ack_certificado'),
    '_intentar_responder_envio_certificado': ('core.views.certificados_wa', '_intentar_responder_envio_certificado'),
    # diploma
    'entregar_si_es_diploma': ('core.views.diploma_meta', 'entregar_si_es_diploma'),
    'es_entrega_diploma': ('core.views.diploma_meta', 'es_entrega_diploma'),
    # pqrs
    'enviar_respuesta_pqrs_meta': ('core.views.pqrs_meta', 'enviar_respuesta_pqrs_meta'),
    # twilio transporte
    '_encolar_twilio_edu_si_async': ('core.views.twilio_transporte', '_encolar_twilio_edu_si_async'),
    '_enviar_mensaje_twilio_segmentado': ('core.views.twilio_transporte', '_enviar_mensaje_twilio_segmentado'),
    '_es_status_callback_twilio': ('core.views.twilio_transporte', '_es_status_callback_twilio'),
    '_registrar_estado_twilio_callback': ('core.views.twilio_transporte', '_registrar_estado_twilio_callback'),
    # comercial
    '_encolar_bot_comercial_si_async': ('core.views.webhook_comercial', '_encolar_bot_comercial_si_async'),
    'bot_comercial_webhook': ('core.views.webhook_comercial', 'bot_comercial_webhook'),
    # audio
    '_audio_path_para_whisper': ('core.views.audio', '_audio_path_para_whisper'),
    '_transcribir_audio_twilio': ('core.views.audio', '_transcribir_audio_twilio'),
    '_transcribir_con_vosk': ('core.views.audio', '_transcribir_con_vosk'),
    # media
    'descargar_archivo_multimedia': ('core.views.media', 'descargar_archivo_multimedia'),
    'obtener_archivos_modulo_view': ('core.views.media', 'obtener_archivos_modulo_view'),
    'serve_media_proxy': ('core.views.media', 'serve_media_proxy'),
    'stream_media': ('core.views.media', 'stream_media'),
    # admin panel
    'api_estado_curso_ia': ('core.views.admin_panel', 'api_estado_curso_ia'),
    'bot_comercial_admin_view': ('core.views.admin_panel', 'bot_comercial_admin_view'),
    'calendario_campanas_view': ('core.views.admin_panel', 'calendario_campanas_view'),
    'conversaciones_view': ('core.views.admin_panel', 'conversaciones_view'),
    'dashboard_unificado': ('core.views.admin_panel', 'dashboard_unificado'),
    'dashboard_unificado_resumen_data': ('core.views.admin_panel', 'dashboard_unificado_resumen_data'),
    'descargar_reportes': ('core.views.admin_panel', 'descargar_reportes'),
    'generando_curso_ia': ('core.views.admin_panel', 'generando_curso_ia'),
    'importar_estudiantes': ('core.views.admin_panel', 'importar_estudiantes'),
    'importar_prospectos': ('core.views.admin_panel', 'importar_prospectos'),
    'instrucciones_view': ('core.views.admin_panel', 'instrucciones_view'),
    'subir_documento_curso': ('core.views.admin_panel', 'subir_documento_curso'),
    'test_email_gmail_view': ('core.views.admin_panel', 'test_email_gmail_view'),
    'vista_previa_curso_ia': ('core.views.admin_panel', 'vista_previa_curso_ia'),
    # bot comercial helper
    '_extraer_texto_archivo_simple': ('core.bot_comercial.webhook', '_extraer_texto_archivo_simple'),
}

_SUBMODULES = frozenset({'webhook_meta', 'webhook_twilio', 'entrada', 'admin_panel'})


def __getattr__(name: str):
    if name in _SUBMODULES:
        return importlib.import_module(f'core.views.{name}')
    spec = _ATTRS.get(name)
    if spec is not None:
        mod_path, attr = spec
        return getattr(importlib.import_module(mod_path), attr)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')