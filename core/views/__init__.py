from core.views.legacy import (
    _bot_comercial_respuesta_catalogo,
    _bot_comercial_sin_contexto_natural,
    _contexto_fallback_web_agro,
    _procesar_bot_comercial_twilio_webhook,
    _procesar_twilio_webhook,
    whatsapp_webhook,
)

from core.views.webhook_meta import (
    _aplicar_sandbox_menu,
    _procesar_meta_webhook,
)

from core.views.empleabilidad import (
    _activar_radar_empleabilidad_si_aplica,
    _haversine_metros,
    _procesar_ubicacion_empleabilidad,
)

from core.views.certificados_wa import (
    _es_ack_certificado,
    _intentar_responder_envio_certificado,
)

from core.views.twilio_transporte import (
    _encolar_twilio_edu_si_async,
    _enviar_mensaje_twilio_segmentado,
    _es_status_callback_twilio,
    _registrar_estado_twilio_callback,
)

from core.views.webhook_comercial import (
    _encolar_bot_comercial_si_async,
    bot_comercial_webhook,
)

from core.views.audio import (
    _audio_path_para_whisper,
    _transcribir_audio_twilio,
    _transcribir_con_vosk,
)

from core.views.media import (
    descargar_archivo_multimedia,
    obtener_archivos_modulo_view,
    serve_media_proxy,
    stream_media,
)

from core.views.admin_panel import (
    api_estado_curso_ia,
    bot_comercial_admin_view,
    calendario_campanas_view,
    conversaciones_view,
    dashboard_unificado,
    dashboard_unificado_resumen_data,
    descargar_reportes,
    generando_curso_ia,
    importar_estudiantes,
    importar_prospectos,
    instrucciones_view,
    subir_documento_curso,
    test_email_gmail_view,
    vista_previa_curso_ia,
)

from core.bot_comercial.webhook import _extraer_texto_archivo_simple
