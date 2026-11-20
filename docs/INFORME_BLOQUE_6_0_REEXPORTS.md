# Informe bloque 6.0 — inventario reexports H4

Fecha: 2026-11-20. Worktree: `eki_deploy_main`, rama `main`.
Alcance: solo **documentación**; no se retiraron stubs.

## Resumen

- **Total stubs H2 en raíz `core/`:** 222
- **Criterio:** `_sys.modules[__name__] = _impl` (fase H2) u homólogo documentado.
- **Conteo de usos:** archivos distintos con `from core.<módulo>` o `import core.<módulo>` (excluye el propio stub); producto vs test por ruta/nombre.

### Top 10 por usos de producto

| # | archivo | destino | usos_producto | usos_test |
|---|---------|---------|---------------|-----------|
| 1 | `core/sandbox_canal.py` | `core.canal.sandbox_canal` | 46 | 22 |
| 2 | `core/models_extras.py` | `core.analitica.models_extras` | 43 | 20 |
| 3 | `core/utils_telefono.py` | `core.canal.utils_telefono` | 42 | 5 |
| 4 | `core/models_certificados.py` | `core.certificados.models_certificados` | 39 | 27 |
| 5 | `core/utils.py` | `core.canal.envios` | 39 | 2 |
| 6 | `core/nati.py` | `core.agentes.nati` | 29 | 7 |
| 7 | `core/module_steps.py` | `core.curso.module_steps` | 27 | 8 |
| 8 | `core/twilio_media.py` | `core.canal.twilio_media` | 27 | 3 |
| 9 | `core/models_campana_meta.py` | `core.campanas.models_campana_meta` | 26 | 12 |
| 10 | `core/modulo_publicacion.py` | `core.curso.modulo_publicacion` | 25 | 10 |

### Totales por paquete destino (primer segmento tras `core.`)

| paquete | stubs | usos_producto (suma archivos) | usos_test (suma archivos) |
|---------|-------|-------------------------------|---------------------------|
| `canal` | 22 | 278 | 72 |
| `agentes` | 45 | 201 | 76 |
| `curso` | 32 | 177 | 78 |
| `analitica` | 37 | 145 | 51 |
| `conversacion` | 18 | 115 | 62 |
| `campanas` | 16 | 75 | 28 |
| `certificados` | 10 | 64 | 44 |
| `admin_vistas` | 36 | 40 | 5 |
| `gamificacion` | 6 | 27 | 7 |

### Recomendación primer retiro (sin ejecutar)

- **Paquete candidato:** `canal`
- **Motivo:** Primer paquete en orden planificado con 22 stubs; s suma 278 archivos de producto y 72 de test con import directo `core.<stub>`.
- Orden planificado: canal → certificados → gamificacion → campanas → curso → agentes → conversacion.

## Tabla completa

| archivo | destino | usos_producto | usos_test | nota |
|---------|---------|---------------|-----------|------|
| `core/admin_command_search.py` | `core.admin_vistas.admin_command_search` | 0 | 1 | solo tests |
| `core/admin_dashboard.py` | `core.admin_vistas.admin_dashboard` | 1 | 0 |  |
| `core/admin_mixins.py` | `core.admin_vistas.admin_mixins` | 4 | 0 |  |
| `core/admin_ranking.py` | `core.admin_vistas.admin_ranking` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/api.py` | `core.admin_vistas.api` | 1 | 0 |  |
| `core/views_admin_analytics.py` | `core.admin_vistas.views_admin_analytics` | 1 | 0 |  |
| `core/views_admin_home.py` | `core.admin_vistas.views_admin_home` | 1 | 0 |  |
| `core/views_admin_panel.py` | `core.admin_vistas.views_admin_panel` | 2 | 4 |  |
| `core/views_analytics.py` | `core.admin_vistas.views_analytics` | 2 | 0 |  |
| `core/views_avance_reset.py` | `core.admin_vistas.views_avance_reset` | 1 | 0 |  |
| `core/views_campana_meta_dia.py` | `core.admin_vistas.views_campana_meta_dia` | 1 | 0 |  |
| `core/views_certificados.py` | `core.admin_vistas.views_certificados` | 1 | 0 |  |
| `core/views_certificados_presenciales.py` | `core.admin_vistas.views_certificados_presenciales` | 1 | 0 |  |
| `core/views_cobertura_admin.py` | `core.admin_vistas.views_cobertura_admin` | 2 | 0 |  |
| `core/views_copiar_curso.py` | `core.admin_vistas.views_copiar_curso` | 1 | 0 |  |
| `core/views_copiloto_admin.py` | `core.admin_vistas.views_copiloto_admin` | 2 | 0 |  |
| `core/views_course_engine_studio.py` | `core.admin_vistas.views_course_engine_studio` | 1 | 0 |  |
| `core/views_curso_nuevo.py` | `core.admin_vistas.views_curso_nuevo` | 1 | 0 |  |
| `core/views_drip_estudiantes.py` | `core.admin_vistas.views_drip_estudiantes` | 1 | 0 |  |
| `core/views_envio_certificados.py` | `core.admin_vistas.views_envio_certificados` | 1 | 0 |  |
| `core/views_eventos_ia.py` | `core.admin_vistas.views_eventos_ia` | 1 | 0 |  |
| `core/views_form_externo.py` | `core.admin_vistas.views_form_externo` | 1 | 0 |  |
| `core/views_gamificacion_ajuste.py` | `core.admin_vistas.views_gamificacion_ajuste` | 1 | 0 |  |
| `core/views_infra_admin.py` | `core.admin_vistas.views_infra_admin` | 1 | 0 |  |
| `core/views_knowledge_studio.py` | `core.admin_vistas.views_knowledge_studio` | 1 | 0 |  |
| `core/views_laboratorio.py` | `core.admin_vistas.views_laboratorio` | 1 | 0 |  |
| `core/views_lineas_admin.py` | `core.admin_vistas.views_lineas_admin` | 1 | 0 |  |
| `core/views_module_builder.py` | `core.admin_vistas.views_module_builder` | 1 | 0 |  |
| `core/views_publicar_confirmar.py` | `core.admin_vistas.views_publicar_confirmar` | 1 | 0 |  |
| `core/views_push_estudiantes.py` | `core.admin_vistas.views_push_estudiantes` | 1 | 0 |  |
| `core/views_reportes.py` | `core.admin_vistas.views_reportes` | 1 | 0 |  |
| `core/views_retencion_admin.py` | `core.admin_vistas.views_retencion_admin` | 1 | 0 |  |
| `core/views_territorio_alertas.py` | `core.admin_vistas.views_territorio_alertas` | 1 | 0 |  |
| `core/views_video.py` | `core.admin_vistas.views_video` | 1 | 0 |  |
| `core/views_webhooks.py` | `core.admin_vistas.views_webhooks` | 1 | 0 |  |
| `core/widgets.py` | `core.admin_vistas.widgets` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/agente_cursos.py` | `core.agentes.agente_cursos` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/agentes_ia.py` | `core.agentes.agentes_ia` | 1 | 0 |  |
| `core/agentes_whatsapp.py` | `core.agentes.agentes_whatsapp` | 10 | 1 |  |
| `core/ai_assistant.py` | `core.agentes.ai_assistant` | 2 | 0 |  |
| `core/ai_capabilities.py` | `core.agentes.ai_capabilities` | 9 | 1 |  |
| `core/audio_processor.py` | `core.agentes.audio_processor` | 2 | 1 |  |
| `core/base_conocimientos.py` | `core.agentes.base_conocimientos` | 3 | 0 |  |
| `core/biblioteca_nat_service.py` | `core.agentes.biblioteca_nat_service` | 4 | 1 |  |
| `core/bot_comercial_routing.py` | `core.agentes.bot_comercial_routing` | 6 | 1 |  |
| `core/cafe_fuentes.py` | `core.agentes.cafe_fuentes` | 1 | 1 |  |
| `core/conocimiento_agentes.py` | `core.agentes.conocimiento_agentes` | 8 | 2 |  |
| `core/contexto_agro.py` | `core.agentes.contexto_agro` | 3 | 3 |  |
| `core/copiar_conocimiento_nati.py` | `core.agentes.copiar_conocimiento_nati` | 1 | 1 |  |
| `core/eki_ia_kill_switch.py` | `core.agentes.eki_ia_kill_switch` | 3 | 1 |  |
| `core/evaluacion_ia.py` | `core.agentes.evaluacion_ia` | 1 | 1 |  |
| `core/event_engine.py` | `core.agentes.event_engine` | 3 | 4 |  |
| `core/eventos_ia.py` | `core.agentes.eventos_ia` | 16 | 1 |  |
| `core/faq_organizacion.py` | `core.agentes.faq_organizacion` | 2 | 1 |  |
| `core/generador_ejercicios_ia.py` | `core.agentes.generador_ejercicios_ia` | 1 | 0 |  |
| `core/generador_preguntas_ia.py` | `core.agentes.generador_preguntas_ia` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/ia_empatica.py` | `core.agentes.ia_empatica` | 1 | 0 |  |
| `core/knowledge_studio.py` | `core.agentes.knowledge_studio` | 3 | 1 |  |
| `core/learning_system.py` | `core.agentes.learning_system` | 1 | 0 |  |
| `core/models_agentes.py` | `core.agentes.models_agentes` | 5 | 3 |  |
| `core/models_uso_llm.py` | `core.agentes.models_uso_llm` | 4 | 1 |  |
| `core/monitoreo_agentes.py` | `core.agentes.monitoreo_agentes` | 2 | 0 |  |
| `core/nat_cuota.py` | `core.agentes.nat_cuota` | 1 | 1 |  |
| `core/nat_diagnostico.py` | `core.agentes.nat_diagnostico` | 2 | 2 |  |
| `core/nat_router.py` | `core.agentes.nat_router` | 2 | 2 |  |
| `core/nati.py` | `core.agentes.nati` | 29 | 7 |  |
| `core/openai_compat.py` | `core.agentes.openai_compat` | 8 | 4 |  |
| `core/pqrs_acciones.py` | `core.agentes.pqrs_acciones` | 3 | 1 |  |
| `core/pqrs_respuesta.py` | `core.agentes.pqrs_respuesta` | 2 | 2 |  |
| `core/presupuesto_llm.py` | `core.agentes.presupuesto_llm` | 8 | 1 |  |
| `core/prompts_tecnicoagro.py` | `core.agentes.prompts_tecnicoagro` | 1 | 3 |  |
| `core/rag_comercial_manager.py` | `core.agentes.rag_comercial_manager` | 6 | 0 |  |
| `core/rag_eki_multitenant.py` | `core.agentes.rag_eki_multitenant` | 4 | 0 |  |
| `core/rag_manager.py` | `core.agentes.rag_manager` | 10 | 1 |  |
| `core/rag_uso.py` | `core.agentes.rag_uso` | 2 | 1 |  |
| `core/sandbox_agentes.py` | `core.agentes.sandbox_agentes` | 10 | 9 |  |
| `core/signals_conocimientos.py` | `core.agentes.signals_conocimientos` | 3 | 3 |  |
| `core/signals_eventos_ia.py` | `core.agentes.signals_eventos_ia` | 1 | 0 |  |
| `core/tutor_ia_modulo.py` | `core.agentes.tutor_ia_modulo` | 16 | 12 |  |
| `core/tutor_interactivo.py` | `core.agentes.tutor_interactivo` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/utils_ia.py` | `core.agentes.utils_ia` | 1 | 2 |  |
| `core/agrosavia_connector.py` | `core.analitica.agrosavia_connector` | 3 | 1 |  |
| `core/alerta_territorial_ops.py` | `core.analitica.alerta_territorial_ops` | 2 | 1 |  |
| `core/clasificador_senales.py` | `core.analitica.clasificador_senales` | 1 | 1 |  |
| `core/client_logos.py` | `core.analitica.client_logos` | 3 | 1 |  |
| `core/clima_open_meteo.py` | `core.analitica.clima_open_meteo` | 2 | 1 |  |
| `core/conversaciones_service.py` | `core.analitica.conversaciones_service` | 2 | 1 |  |
| `core/copiloto_ops.py` | `core.analitica.copiloto_ops` | 1 | 1 |  |
| `core/dashboard_avanzado.py` | `core.analitica.dashboard_avanzado` | 1 | 0 |  |
| `core/dashboard_redirects.py` | `core.analitica.dashboard_redirects` | 1 | 0 |  |
| `core/documento_identidad.py` | `core.analitica.documento_identidad` | 7 | 1 |  |
| `core/email_service.py` | `core.analitica.email_service` | 3 | 0 |  |
| `core/empleabilidad_pausa.py` | `core.analitica.empleabilidad_pausa` | 10 | 1 |  |
| `core/empleabilidad_prueba.py` | `core.analitica.empleabilidad_prueba` | 3 | 1 |  |
| `core/excel_celdas.py` | `core.analitica.excel_celdas` | 3 | 1 |  |
| `core/export_estudiantes.py` | `core.analitica.export_estudiantes` | 3 | 1 |  |
| `core/exportar_respuestas_xlsx.py` | `core.analitica.exportar_respuestas_xlsx` | 1 | 0 |  |
| `core/extractores_documento.py` | `core.analitica.extractores_documento` | 4 | 1 |  |
| `core/fao_connector.py` | `core.analitica.fao_connector` | 2 | 1 |  |
| `core/form_externo_service.py` | `core.analitica.form_externo_service` | 1 | 2 |  |
| `core/health_deep.py` | `core.analitica.health_deep` | 3 | 0 |  |
| `core/host_isolation.py` | `core.analitica.host_isolation` | 4 | 0 |  |
| `core/impacto_captura.py` | `core.analitica.impacto_captura` | 0 | 1 | solo tests |
| `core/import_estudiantes_excel.py` | `core.analitica.import_estudiantes_excel` | 2 | 1 |  |
| `core/infra_monitor.py` | `core.analitica.infra_monitor` | 6 | 1 |  |
| `core/metricas_empresa.py` | `core.analitica.metricas_empresa` | 4 | 3 |  |
| `core/models_audit.py` | `core.analitica.models_audit` | 3 | 0 |  |
| `core/models_extras.py` | `core.analitica.models_extras` | 43 | 20 |  |
| `core/models_notas.py` | `core.analitica.models_notas` | 1 | 0 |  |
| `core/ops_slack.py` | `core.analitica.ops_slack` | 2 | 0 |  |
| `core/senal_shadow.py` | `core.analitica.senal_shadow` | 1 | 1 |  |
| `core/sentry_eki.py` | `core.analitica.sentry_eki` | 1 | 1 |  |
| `core/services.py` | `core.analitica.services` | 2 | 3 |  |
| `core/services_estudiante.py` | `core.analitica.services_estudiante` | 1 | 0 |  |
| `core/signals_telemetria.py` | `core.analitica.signals_telemetria` | 1 | 0 |  |
| `core/taxonomia_senales.py` | `core.analitica.taxonomia_senales` | 1 | 1 |  |
| `core/telemetria.py` | `core.analitica.telemetria` | 15 | 2 |  |
| `core/territorio.py` | `core.analitica.territorio` | 2 | 1 |  |
| `core/admin_campana_actualizado.py` | `core.campanas.admin_campana_actualizado` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/campana_audiencia.py` | `core.campanas.campana_audiencia` | 6 | 4 |  |
| `core/campana_meta_ritmo.py` | `core.campanas.campana_meta_ritmo` | 5 | 1 |  |
| `core/campana_meta_v2.py` | `core.campanas.campana_meta_v2` | 2 | 1 |  |
| `core/campana_respuestas.py` | `core.campanas.campana_respuestas` | 3 | 1 |  |
| `core/campana_resultados.py` | `core.campanas.campana_resultados` | 1 | 1 |  |
| `core/catalogo_precios.py` | `core.campanas.catalogo_precios` | 1 | 1 |  |
| `core/enviar_plantillas.py` | `core.campanas.enviar_plantillas` | 9 | 0 |  |
| `core/mensajes_push.py` | `core.campanas.mensajes_push` | 2 | 0 |  |
| `core/models_campana_meta.py` | `core.campanas.models_campana_meta` | 26 | 12 |  |
| `core/plantilla_builder.py` | `core.campanas.plantilla_builder` | 2 | 1 |  |
| `core/plantilla_meta_editor.py` | `core.campanas.plantilla_meta_editor` | 6 | 1 |  |
| `core/plantilla_meta_reglas.py` | `core.campanas.plantilla_meta_reglas` | 3 | 1 |  |
| `core/precios_excel.py` | `core.campanas.precios_excel` | 2 | 1 |  |
| `core/precios_import.py` | `core.campanas.precios_import` | 2 | 1 |  |
| `core/reenganche_meta.py` | `core.campanas.reenganche_meta` | 5 | 2 |  |
| `core/linea_registrados.py` | `core.canal.linea_registrados` | 1 | 1 |  |
| `core/meta_estados.py` | `core.canal.meta_estados` | 5 | 2 |  |
| `core/meta_inbound.py` | `core.canal.meta_inbound` | 2 | 1 |  |
| `core/meta_templates.py` | `core.canal.meta_templates` | 1 | 0 |  |
| `core/meta_token.py` | `core.canal.meta_token` | 13 | 1 |  |
| `core/meta_waba.py` | `core.canal.meta_waba` | 20 | 6 |  |
| `core/models_meta_webhook.py` | `core.canal.models_meta_webhook` | 7 | 4 |  |
| `core/planes_linea.py` | `core.canal.planes_linea` | 16 | 12 |  |
| `core/sandbox_canal.py` | `core.canal.sandbox_canal` | 46 | 22 |  |
| `core/twilio_balance.py` | `core.canal.twilio_balance` | 5 | 1 |  |
| `core/twilio_content_preview.py` | `core.canal.twilio_content_preview` | 4 | 1 |  |
| `core/twilio_inbound_media.py` | `core.canal.twilio_inbound_media` | 4 | 1 |  |
| `core/twilio_media.py` | `core.canal.twilio_media` | 27 | 3 |  |
| `core/twilio_puerta.py` | `core.canal.twilio_puerta` | 3 | 1 |  |
| `core/twilio_timeout.py` | `core.canal.twilio_timeout` | 1 | 0 |  |
| `core/twilio_webhook_security.py` | `core.canal.twilio_webhook_security` | 3 | 1 |  |
| `core/utils.py` | `core.canal.envios` | 39 | 2 |  |
| `core/utils_telefono.py` | `core.canal.utils_telefono` | 42 | 5 |  |
| `core/wa_canal.py` | `core.canal.wa_canal` | 5 | 1 |  |
| `core/wa_reply_context.py` | `core.canal.wa_reply_context` | 4 | 0 |  |
| `core/webhook_evento.py` | `core.canal.webhook_evento` | 9 | 5 |  |
| `core/whatsapp_service.py` | `core.canal.whatsapp_service` | 21 | 2 |  |
| `core/certificado_admin_preview.py` | `core.certificados.certificado_admin_preview` | 1 | 0 |  |
| `core/certificado_artefacto.py` | `core.certificados.certificado_artefacto` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/certificado_diseno_eki.py` | `core.certificados.certificado_diseno_eki` | 3 | 2 |  |
| `core/certificado_presencial_service.py` | `core.certificados.certificado_presencial_service` | 3 | 5 |  |
| `core/certificado_preview.py` | `core.certificados.certificado_preview` | 2 | 1 |  |
| `core/certificado_service.py` | `core.certificados.certificado_service` | 12 | 8 |  |
| `core/generador_certificados.py` | `core.certificados.generador_certificados` | 1 | 0 |  |
| `core/models_certificados.py` | `core.certificados.models_certificados` | 39 | 27 |  |
| `core/signals_certificados.py` | `core.certificados.signals_certificados` | 1 | 0 |  |
| `core/utils_certificados.py` | `core.certificados.utils_certificados` | 2 | 1 |  |
| `core/antiflood.py` | `core.conversacion.antiflood` | 1 | 1 |  |
| `core/avance_whatsapp.py` | `core.conversacion.avance_whatsapp` | 17 | 4 |  |
| `core/consentimiento_wa.py` | `core.conversacion.consentimiento_wa` | 6 | 1 |  |
| `core/correccion_datos.py` | `core.conversacion.correccion_datos` | 4 | 4 |  |
| `core/flujo_whatsapp_b2b.py` | `core.conversacion.flujo_whatsapp_b2b` | 5 | 3 |  |
| `core/habeas_respuestas.py` | `core.conversacion.habeas_respuestas` | 8 | 3 |  |
| `core/intent_detector.py` | `core.conversacion.intent_detector` | 12 | 9 |  |
| `core/locks.py` | `core.conversacion.locks` | 12 | 3 |  |
| `core/onboarding_audio_handler.py` | `core.conversacion.onboarding_audio_handler` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/pregunta_handler.py` | `core.conversacion.pregunta_handler` | 3 | 2 |  |
| `core/rate_limit.py` | `core.conversacion.rate_limit` | 1 | 0 |  |
| `core/response_templates.py` | `core.conversacion.response_templates` | 20 | 23 |  |
| `core/response_templates_backup.py` | `core.conversacion.response_templates_backup` | 0 | 0 | sin referencias directas (posible import vía core.views / __init__) |
| `core/reto_evidencia.py` | `core.conversacion.reto_evidencia` | 4 | 0 |  |
| `core/salida_usuario.py` | `core.conversacion.salida_usuario` | 6 | 1 |  |
| `core/security_handler.py` | `core.conversacion.security_handler` | 5 | 2 |  |
| `core/seguimiento_proactivo.py` | `core.conversacion.seguimiento_proactivo` | 1 | 0 |  |
| `core/selector_curso.py` | `core.conversacion.selector_curso` | 10 | 6 |  |
| `core/avance_reset_service.py` | `core.curso.avance_reset_service` | 1 | 1 |  |
| `core/bloques_modulo.py` | `core.curso.bloques_modulo` | 1 | 0 |  |
| `core/catalogo_demo_carousel.py` | `core.curso.catalogo_demo_carousel` | 2 | 1 |  |
| `core/copiar_cursos.py` | `core.curso.copiar_cursos` | 7 | 2 |  |
| `core/cursos_permitidos.py` | `core.curso.cursos_permitidos` | 3 | 1 |  |
| `core/drip_matriz_service.py` | `core.curso.drip_matriz_service` | 1 | 1 |  |
| `core/drip_schedule.py` | `core.curso.drip_schedule` | 19 | 8 |  |
| `core/facilitador_perfil.py` | `core.curso.facilitador_perfil` | 7 | 2 |  |
| `core/grupos_miembros.py` | `core.curso.grupos_miembros` | 1 | 1 |  |
| `core/helpers_examenes.py` | `core.curso.helpers_examenes` | 6 | 6 |  |
| `core/inicio_curso.py` | `core.curso.inicio_curso` | 5 | 1 |  |
| `core/inscripcion_curso.py` | `core.curso.inscripcion_curso` | 14 | 9 |  |
| `core/media_encode_async.py` | `core.curso.media_encode_async` | 8 | 4 |  |
| `core/media_entrega.py` | `core.curso.media_entrega` | 3 | 2 |  |
| `core/media_pasos_listos.py` | `core.curso.media_pasos_listos` | 6 | 1 |  |
| `core/media_recuperacion.py` | `core.curso.media_recuperacion` | 1 | 1 |  |
| `core/media_upload_servicio.py` | `core.curso.media_upload_servicio` | 2 | 1 |  |
| `core/media_wa_audit.py` | `core.curso.media_wa_audit` | 5 | 1 |  |
| `core/models_media_entrega.py` | `core.curso.models_media_entrega` | 6 | 1 |  |
| `core/models_video.py` | `core.curso.models_video` | 3 | 1 |  |
| `core/module_builder.py` | `core.curso.module_builder` | 4 | 6 |  |
| `core/module_builder_config.py` | `core.curso.module_builder_config` | 2 | 0 |  |
| `core/module_builder_lectura.py` | `core.curso.module_builder_lectura` | 1 | 0 |  |
| `core/module_steps.py` | `core.curso.module_steps` | 27 | 8 |  |
| `core/module_structure.py` | `core.curso.module_structure` | 4 | 3 |  |
| `core/modulo_authoring_mode.py` | `core.curso.modulo_authoring_mode` | 2 | 2 |  |
| `core/modulo_publicacion.py` | `core.curso.modulo_publicacion` | 25 | 10 |  |
| `core/orden_bloques.py` | `core.curso.orden_bloques` | 2 | 3 |  |
| `core/plantillas_ejercicios.py` | `core.curso.plantillas_ejercicios` | 1 | 0 |  |
| `core/signals_publicacion_wa.py` | `core.curso.signals_publicacion_wa` | 1 | 0 |  |
| `core/signals_videos.py` | `core.curso.signals_videos` | 1 | 0 |  |
| `core/video_links.py` | `core.curso.video_links` | 6 | 1 |  |
| `core/gamificacion_actions.py` | `core.gamificacion.actions` | 2 | 0 |  |
| `core/gamificacion_ajuste_service.py` | `core.gamificacion.ajuste_service` | 1 | 1 |  |
| `core/gamificacion_modo.py` | `core.gamificacion.modo` | 15 | 6 |  |
| `core/rachas_linea.py` | `core.gamificacion.rachas_linea` | 5 | 0 |  |
| `core/recompensas.py` | `core.gamificacion.recompensas` | 3 | 0 |  |
| `core/signals_gamificacion.py` | `core.gamificacion.signals` | 1 | 0 |  |
