"""Mueve un archivo suelto de core/ a su paquete de dominio (fase H2).

El archivo nuevo es el original, con los `from .` vueltos `from core.`
(el archivo ya no vive en el paquete core). En la ruta vieja queda un
reexport que reemplaza el módulo, así `import core.foo` sigue siendo
el mismo objeto.

    python scripts/mover_suelto.py --list
    python scripts/mover_suelto.py certificados
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORE = RAIZ / 'core'

CONGELADOS = {
    '__init__.py',
    'apps.py',
    'middleware.py',
    'tasks.py',
    'tasks_infra.py',
}

# nombre.py -> (paquete, archivo destino dentro del paquete)
MANUAL: dict[str, tuple[str, str]] = {
    'gamificacion.py': ('gamificacion', '__init__.py'),
    'gamificacion_actions.py': ('gamificacion', 'actions.py'),
    'gamificacion_ajuste_service.py': ('gamificacion', 'ajuste_service.py'),
    'gamificacion_modo.py': ('gamificacion', 'modo.py'),
    'recompensas.py': ('gamificacion', 'recompensas.py'),
    'rachas_linea.py': ('gamificacion', 'rachas_linea.py'),
    'signals_gamificacion.py': ('gamificacion', 'signals.py'),
    'utils.py': ('canal', 'envios.py'),
    'utils_telefono.py': ('canal', 'utils_telefono.py'),
    'sandbox_canal.py': ('canal', 'sandbox_canal.py'),
    'whatsapp_service.py': ('canal', 'whatsapp_service.py'),
    'sandbox_menu.py': ('conversacion', 'sandbox_menu.py'),
    'intent_detector.py': ('conversacion', 'intent_detector.py'),
    'response_templates.py': ('conversacion', 'response_templates.py'),
    'response_templates_backup.py': ('conversacion', 'response_templates_backup.py'),
    'selector_curso.py': ('conversacion', 'selector_curso.py'),
    'habeas_respuestas.py': ('conversacion', 'habeas_respuestas.py'),
    'pregunta_handler.py': ('conversacion', 'pregunta_handler.py'),
    'correccion_datos.py': ('conversacion', 'correccion_datos.py'),
    'helpers_examenes.py': ('curso', 'helpers_examenes.py'),
    'inscripcion_curso.py': ('curso', 'inscripcion_curso.py'),
    'modulo_publicacion.py': ('curso', 'modulo_publicacion.py'),
    'inicio_curso.py': ('curso', 'inicio_curso.py'),
    'admin_actions.py': ('admin_vistas', 'admin_actions.py'),
    'admin_command_search.py': ('admin_vistas', 'admin_command_search.py'),
    'admin_dashboard.py': ('admin_vistas', 'admin_dashboard.py'),
    'admin_mixins.py': ('admin_vistas', 'admin_mixins.py'),
    'admin_ranking.py': ('admin_vistas', 'admin_ranking.py'),
    'admin_campana_actualizado.py': ('campanas', 'admin_campana_actualizado.py'),
    'api.py': ('admin_vistas', 'api.py'),
    'widgets.py': ('admin_vistas', 'widgets.py'),
    'agrosavia_connector.py': ('analitica', 'agrosavia_connector.py'),
    'fao_connector.py': ('analitica', 'fao_connector.py'),
    'clima_open_meteo.py': ('analitica', 'clima_open_meteo.py'),
    'email_service.py': ('analitica', 'email_service.py'),
    'health_deep.py': ('analitica', 'health_deep.py'),
    'host_isolation.py': ('analitica', 'host_isolation.py'),
    'ops_slack.py': ('analitica', 'ops_slack.py'),
    'sentry_eki.py': ('analitica', 'sentry_eki.py'),
    'import_estudiantes_excel.py': ('analitica', 'import_estudiantes_excel.py'),
    'excel_celdas.py': ('analitica', 'excel_celdas.py'),
    'extractores_documento.py': ('analitica', 'extractores_documento.py'),
    'documento_identidad.py': ('analitica', 'documento_identidad.py'),
    'empleabilidad_pausa.py': ('analitica', 'empleabilidad_pausa.py'),
    'empleabilidad_prueba.py': ('analitica', 'empleabilidad_prueba.py'),
    'form_externo_service.py': ('analitica', 'form_externo_service.py'),
    'client_logos.py': ('analitica', 'client_logos.py'),
    'models_extras.py': ('analitica', 'models_extras.py'),
    'planes_linea.py': ('canal', 'planes_linea.py'),
    'linea_registrados.py': ('canal', 'linea_registrados.py'),
    'antiflood.py': ('conversacion', 'antiflood.py'),
    'locks.py': ('conversacion', 'locks.py'),
    'rate_limit.py': ('conversacion', 'rate_limit.py'),
    'consentimiento_wa.py': ('conversacion', 'consentimiento_wa.py'),
    'avance_whatsapp.py': ('conversacion', 'avance_whatsapp.py'),
    'flujo_whatsapp_b2b.py': ('conversacion', 'flujo_whatsapp_b2b.py'),
    'onboarding_audio_handler.py': ('conversacion', 'onboarding_audio_handler.py'),
    'security_handler.py': ('conversacion', 'security_handler.py'),
    'salida_usuario.py': ('conversacion', 'salida_usuario.py'),
    'seguimiento_proactivo.py': ('conversacion', 'seguimiento_proactivo.py'),
    'reto_evidencia.py': ('conversacion', 'reto_evidencia.py'),
    'bot_comercial_routing.py': ('agentes', 'bot_comercial_routing.py'),
    'audio_processor.py': ('agentes', 'audio_processor.py'),
    'contexto_agro.py': ('agentes', 'contexto_agro.py'),
    'faq_organizacion.py': ('agentes', 'faq_organizacion.py'),
    'knowledge_studio.py': ('agentes', 'knowledge_studio.py'),
    'facilitador_perfil.py': ('curso', 'facilitador_perfil.py'),
    'plantillas_ejercicios.py': ('curso', 'plantillas_ejercicios.py'),
    'avance_reset_service.py': ('curso', 'avance_reset_service.py'),
    'catalogo_demo_carousel.py': ('curso', 'catalogo_demo_carousel.py'),
    'grupos_miembros.py': ('curso', 'grupos_miembros.py'),
    'signals_videos.py': ('curso', 'signals_videos.py'),
    'signals_publicacion_wa.py': ('curso', 'signals_publicacion_wa.py'),
    'catalogo_precios.py': ('campanas', 'catalogo_precios.py'),
    'precios_excel.py': ('campanas', 'precios_excel.py'),
    'precios_import.py': ('campanas', 'precios_import.py'),
}


def _prefijo(nombre: str) -> str | None:
    reglas = (
        ('views_', 'admin_vistas'),
        ('certificado_', 'certificados'),
        ('generador_certificados', 'certificados'),
        ('utils_certificados', 'certificados'),
        ('signals_certificados', 'certificados'),
        ('models_certificados', 'certificados'),
        ('campana_', 'campanas'),
        ('plantilla_', 'campanas'),
        ('enviar_plantillas', 'campanas'),
        ('mensajes_push', 'campanas'),
        ('reenganche_meta', 'campanas'),
        ('models_campana', 'campanas'),
        ('twilio_', 'canal'),
        ('meta_', 'canal'),
        ('wa_', 'canal'),
        ('webhook_evento', 'canal'),
        ('models_meta', 'canal'),
        ('module_', 'curso'),
        ('drip_', 'curso'),
        ('modulo_', 'curso'),
        ('bloques_modulo', 'curso'),
        ('orden_bloques', 'curso'),
        ('copiar_cursos', 'curso'),
        ('cursos_', 'curso'),
        ('video_links', 'curso'),
        ('media_', 'curso'),
        ('models_media', 'curso'),
        ('models_video', 'curso'),
        ('tutor_', 'agentes'),
        ('agentes_', 'agentes'),
        ('agente_', 'agentes'),
        ('utils_ia', 'agentes'),
        ('openai_compat', 'agentes'),
        ('nat_', 'agentes'),
        ('nati.py', 'agentes'),
        ('rag_', 'agentes'),
        ('ia_', 'agentes'),
        ('ai_', 'agentes'),
        ('prompts_', 'agentes'),
        ('conocimiento_agentes', 'agentes'),
        ('monitoreo_agentes', 'agentes'),
        ('evaluacion_ia', 'agentes'),
        ('generador_ejercicios_ia', 'agentes'),
        ('generador_preguntas_ia', 'agentes'),
        ('learning_system', 'agentes'),
        ('base_conocimientos', 'agentes'),
        ('biblioteca_nat', 'agentes'),
        ('copiar_conocimiento', 'agentes'),
        ('pqrs_', 'agentes'),
        ('cafe_', 'agentes'),
        ('sandbox_agentes', 'agentes'),
        ('models_agentes', 'agentes'),
        ('eki_ia_', 'agentes'),
        ('presupuesto_llm', 'agentes'),
        ('models_uso_llm', 'agentes'),
        ('signals_conocimientos', 'agentes'),
        ('signals_eventos_ia', 'agentes'),
        ('eventos_ia', 'agentes'),
        ('event_engine', 'agentes'),
        ('dashboard_', 'analitica'),
        ('metricas_', 'analitica'),
        ('telemetria', 'analitica'),
        ('infra_monitor', 'analitica'),
        ('copiloto', 'analitica'),
        ('alerta_', 'analitica'),
        ('territorio', 'analitica'),
        ('clasificador_senales', 'analitica'),
        ('taxonomia_senales', 'analitica'),
        ('senal_', 'analitica'),
        ('impacto_', 'analitica'),
        ('export_', 'analitica'),
        ('exportar_', 'analitica'),
        ('conversaciones_service', 'analitica'),
        ('services.py', 'analitica'),
        ('services_estudiante', 'analitica'),
        ('signals_telemetria', 'analitica'),
        ('models_audit', 'analitica'),
        ('models_notas', 'analitica'),
    )
    for prefijo, paquete in reglas:
        if nombre.startswith(prefijo) or nombre == prefijo:
            return paquete
    return None


def destino(nombre: str) -> tuple[str, str] | None:
    if nombre in CONGELADOS:
        return None
    if nombre in MANUAL:
        return MANUAL[nombre]
    paquete = _prefijo(nombre)
    if not paquete:
        return None
    return paquete, nombre


def sueltos() -> list[str]:
    return sorted(
        p.name for p in CORE.glob('*.py')
        if 'test' not in p.name and not p.name.startswith('tests')
    )


def absolutizar(texto: str, origen: str) -> str:
    def repl(m: re.Match) -> str:
        indent, puntos, resto = m.group(1), m.group(2), m.group(3)
        if len(puntos) != 1:
            raise SystemExit(f'{origen}: import relativo de {len(puntos)} niveles')
        if resto.startswith('import '):
            return f'{indent}from core {resto}'
        return f'{indent}from core.{resto}'

    return re.sub(r'(?m)^([ \t]*)from (\.+)(\S.*)$', repl, texto)


def mover(nombre: str) -> None:
    donde = destino(nombre)
    if not donde:
        raise SystemExit(f'sin dominio: {nombre}')
    paquete, archivo = donde
    origen = CORE / nombre
    carpeta = CORE / paquete
    texto = absolutizar(origen.read_text(encoding='utf-8'), nombre)
    if archivo == '__init__.py':
        origen.unlink()
        carpeta.mkdir(exist_ok=True)
        (carpeta / '__init__.py').write_text(texto, encoding='utf-8')
        print(f'{nombre} -> {paquete}/__init__.py (el paquete reemplaza al módulo)')
        return
    carpeta.mkdir(exist_ok=True)
    init = carpeta / '__init__.py'
    if not init.exists():
        init.write_text(f'"""Dominio {paquete}. Fase H2: solo movimiento."""\n', encoding='utf-8')
    final = carpeta / archivo
    if final.exists():
        raise SystemExit(f'ya existe {final}')
    final.write_text(texto, encoding='utf-8')
    modulo = f'core.{paquete}.{archivo[:-3]}'
    origen.write_text(
        f'"""Reexport de fase H2. El código vive en {modulo}."""\n'
        'import importlib as _importlib\n'
        'import sys as _sys\n'
        f'_sys.modules[__name__] = _importlib.import_module("{modulo}")\n',
        encoding='utf-8',
    )
    print(f'{nombre} -> {paquete}/{archivo}')


def main(argv: list[str]) -> int:
    if not argv or argv == ['--list']:
        por: dict[str, list[str]] = {}
        huerfanos = []
        for nombre in sueltos():
            donde = destino(nombre)
            if not donde:
                if nombre not in CONGELADOS:
                    huerfanos.append(nombre)
                continue
            por.setdefault(donde[0], []).append(nombre)
        for paquete, nombres in sorted(por.items()):
            print(f'[{paquete}] {len(nombres)}')
        print(f'[sin dominio] {len(huerfanos)}')
        for nombre in huerfanos:
            print(f'  {nombre}')
        return 0
    paquete = argv[0]
    movidos = [n for n in sueltos() if destino(n) and destino(n)[0] == paquete]
    if not movidos:
        raise SystemExit(f'nada que mover en {paquete}')
    for nombre in movidos:
        mover(nombre)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
