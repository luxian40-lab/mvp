"""Reenganche drip de las 08:00. Solo Graph. No envía si el flag está apagado."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def reenganche_habilitado() -> bool:
    return bool(getattr(settings, 'META_REENGANCHE_ENABLED', False))


def enmascarar_telefono(telefono: str) -> str:
    digitos = ''.join(ch for ch in str(telefono or '') if ch.isdigit())
    if len(digitos) < 4:
        return '***'
    return f'***{digitos[-4:]}'


def _digitos(telefono: str) -> str:
    return ''.join(ch for ch in str(telefono or '') if ch.isdigit())


def ultimo_entrante(estudiante):
    from core.models import WhatsappLog

    digitos = _digitos(getattr(estudiante, 'telefono', ''))
    formas = set()
    if digitos:
        formas.update({digitos, f'+{digitos}', f'whatsapp:+{digitos}', f'whatsapp:{digitos}'})
    consulta = Q()
    if estudiante.pk:
        consulta |= Q(estudiante_id=estudiante.pk)
    if formas:
        consulta |= Q(telefono__in=formas)
    if not consulta:
        return None
    return (
        WhatsappLog.objects.filter(tipo='INCOMING', canal='meta')
        .filter(consulta)
        .order_by('-fecha')
        .first()
    )


def ventana_abierta(estudiante, ahora: datetime | None = None) -> bool:
    ahora = ahora or timezone.now()
    try:
        horas = int(getattr(settings, 'WA_VENTANA_HORAS', 23) or 23)
    except (TypeError, ValueError):
        horas = 23
    log = ultimo_entrante(estudiante)
    if log is None or not log.fecha:
        return False
    return log.fecha >= ahora - timedelta(hours=horas)


def _plantilla() -> str:
    return (getattr(settings, 'META_TEMPLATE_DRIP_REENGANCHE', '') or '').strip()


def candidatos_en(fecha):
    """Progresos cuyo siguiente módulo se desbloquea en esa fecha calendario local."""
    from core.drip_schedule import dias_espera_efectivos, fecha_desbloqueo_drip
    from core.models import ProgresoEstudiante
    from core.modulo_publicacion import siguiente_modulo_publicado_wa

    queryset = ProgresoEstudiante.objects.select_related(
        'estudiante', 'curso', 'modulo_actual',
    ).filter(
        completado=False,
        fecha_ultimo_avance__isnull=False,
        modulo_actual__isnull=False,
    )
    for progreso in queryset:
        dias = dias_espera_efectivos(progreso.estudiante, progreso.curso)
        if dias <= 0:
            continue
        siguiente = siguiente_modulo_publicado_wa(progreso.curso, progreso.modulo_actual)
        if not siguiente:
            continue
        desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, dias)
        if desbloqueo == fecha:
            yield progreso, siguiente


def plan_del_dia(fecha, ahora: datetime | None = None) -> dict:
    ahora = ahora or timezone.now()
    plantilla = _plantilla()
    filas = []
    texto = plantilla_n = omitidos = 0
    for progreso, siguiente in candidatos_en(fecha):
        estudiante = progreso.estudiante
        if ventana_abierta(estudiante, ahora):
            modo = 'texto'
            texto += 1
        elif plantilla:
            modo = 'plantilla'
            plantilla_n += 1
        else:
            modo = 'omitido'
            omitidos += 1
        filas.append({
            'telefono': enmascarar_telefono(estudiante.telefono),
            'modo': modo,
            'curso': progreso.curso.nombre,
            'modulo_id': siguiente.pk,
            'progreso': progreso,
            'siguiente': siguiente,
        })
    return {
        'fecha': fecha.isoformat(),
        'candidatos': len(filas),
        'texto': texto,
        'plantilla': plantilla_n,
        'omitidos_sin_ventana': omitidos,
        'filas': filas,
    }


def previsualizar(dias: int = 1, ahora: datetime | None = None) -> list[dict]:
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    dias = max(0, int(dias))
    return [plan_del_dia(hoy + timedelta(days=i), ahora) for i in range(dias + 1)]


def _texto_libre(progreso) -> str:
    return (
        "👋 ¡Hola! Tu nuevo módulo ya está disponible.\n\n"
        f"Curso: *{progreso.curso.nombre}*\n"
        "Responde *LISTO* para continuar."
    )


def ejecutar(ahora: datetime | None = None) -> dict:
    ahora = ahora or timezone.now()
    if not reenganche_habilitado():
        return {
            'habilitado': False,
            'enviados': 0,
            'omitidos_sin_ventana': 0,
            'omitidos_token': 0,
        }
    from core.meta_token import token_invalido

    if token_invalido():
        plan = plan_del_dia(timezone.localdate(ahora), ahora)
        return {
            'habilitado': True,
            'enviados': 0,
            'omitidos_sin_ventana': 0,
            'omitidos_token': plan['candidatos'],
        }
    from core.sandbox_canal import enviar_meta, enviar_meta_plantilla

    plan = plan_del_dia(timezone.localdate(ahora), ahora)
    enviados = 0
    plantilla = _plantilla()
    idioma = (getattr(settings, 'META_TEMPLATE_DRIP_IDIOMA', 'es') or 'es').strip() or 'es'
    for fila in plan['filas']:
        if fila['modo'] == 'omitido':
            continue
        progreso = fila['progreso']
        estudiante = progreso.estudiante
        if fila['modo'] == 'texto':
            resultado = enviar_meta(
                estudiante.telefono,
                _texto_libre(progreso),
                canal_evento='reenganche_drip',
                agente_evento='reenganche_drip',
            )
        else:
            resultado = enviar_meta_plantilla(
                estudiante.telefono,
                plantilla,
                {
                    '1': estudiante.nombre or 'estudiante',
                    '2': progreso.curso.nombre,
                },
                idioma=idioma,
            )
        if not resultado.get('success'):
            continue
        enviados += 1
        try:
            from core.models import EstudianteEventoAprendizaje
            from core.telemetria import registrar_evento

            registrar_evento(
                tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
                estudiante=estudiante,
                curso=progreso.curso,
                modulo=fila['siguiente'],
                metadata={
                    'origen': 'reenganche_drip',
                    'template': fila['modo'] == 'plantilla',
                    'modulo_desbloqueado_id': fila['siguiente'].pk,
                },
            )
        except Exception:
            pass
    return {
        'habilitado': True,
        'enviados': enviados,
        'omitidos_sin_ventana': plan['omitidos_sin_ventana'],
    }


def campanas_pendientes() -> list[dict]:
    """Campañas no ejecutadas que todavía tienen destinatarios activos. No envía."""
    from core.models import Campana, Estudiante
    from core.models_campana_meta import CampanaMeta

    salida = []
    campanas = Campana.objects.filter(ejecutada=False).select_related('plantilla')
    for campana in campanas:
        if getattr(campana, 'tipo_audiencia', '') == 'grupo' and campana.grupo_id:
            total = Estudiante.objects.filter(grupos__id=campana.grupo_id, activo=True).count()
        else:
            total = campana.destinatarios.filter(activo=True).count()
        if total <= 0:
            continue
        content = (campana.template_twilio_id or '').strip()
        content = content or (getattr(campana.plantilla, 'content_sid', None) or '').strip()
        if content or getattr(campana.plantilla, 'cuerpo_mensaje', None):
            proveedor = 'twilio'
        else:
            proveedor = 'incompleto'
        salida.append({
            'modelo': 'Campana',
            'id': campana.pk,
            'nombre': campana.nombre,
            'fecha': campana.fecha_programada,
            'destinatarios': total,
            'proveedor': proveedor,
        })
    for campana in CampanaMeta.objects.filter(ejecutada=False):
        if campana.grupo_id:
            total = Estudiante.objects.filter(grupos__id=campana.grupo_id, activo=True).count()
        else:
            total = campana.destinatarios.filter(activo=True).count()
        if total <= 0:
            continue
        salida.append({
            'modelo': 'CampanaMeta',
            'id': campana.pk,
            'nombre': campana.nombre,
            'fecha': None,
            'destinatarios': total,
            'proveedor': 'meta',
        })
    return salida
