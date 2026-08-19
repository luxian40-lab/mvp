"""Atajos extra para la command palette Unfold (Ctrl+K / Cmd+K)."""
from __future__ import annotations

from django.urls import reverse

from unfold.dataclasses import SearchResult


def _result(title: str, description: str, link: str, icon: str = 'link') -> SearchResult:
    return SearchResult(title=title, description=description, link=link, icon=icon)


def eki_command_search_callback(request, search_term: str) -> list[SearchResult]:
    """Teléfono, conversación, manual, triage WA y acciones ops frecuentes."""
    q = (search_term or '').strip().lower()
    if not q:
        return []

    out: list[SearchResult] = []

    # Atajos fijos (palabras clave)
    shortcuts = [
        (('manual', 'instrucciones', 'ayuda', 'guia', 'guía'), _result(
            'Manual operativo',
            'Guías rápidas del admin eki',
            '/admin/instrucciones/',
            'menu_book',
        )),
        (('conversacion', 'conversaciones', 'inbox', 'chat wa'), _result(
            'Conversaciones WhatsApp',
            'Inbox staff · filtro por org',
            '/admin/conversaciones/',
            'forum',
        )),
        (('fallido', 'fallidos', 'envio fallido'), _result(
            'Envíos fallidos (7 días)',
            'EnvioLog con estado FALLIDO',
            '/admin/core/enviolog/?estado__exact=FALLIDO',
            'error',
        )),
        (('63019', '63021', 'media twilio'), _result(
            'WhatsappLog · error media',
            'Filtro código Twilio 63019',
            '/admin/core/whatsapplog/?codigo_twilio=63019',
            'bug_report',
        )),
        (('certificado', 'certificados', 'diploma'), _result(
            'Envío certificados',
            'Masivo por org y curso',
            '/admin/envio-certificados/',
            'verified',
        )),
        (('sin progreso', 'progreso cero'), _result(
            'Estudiantes sin progreso',
            'Activos sin inscripción/avance',
            '/admin/core/estudiante/?eki_progreso=sin',
            'person_off',
        )),
        (('infra', 'salud', 'celery', 'health'), _result(
            'Monitor infra',
            'Salud EB, Celery, S3',
            '/admin/infra/',
            'monitor_heart',
        )),
        (('push', 'recordatorio'), _result(
            'Push recordatorios',
            'Reenganche sin reiniciar curso',
            '/admin/push-estudiantes/',
            'notifications_active',
        )),
        (('calendario', 'campana hoy'), _result(
            'Calendario campañas',
            'Programación de envíos',
            '/admin/calendario/',
            'event',
        )),
    ]
    for keys, item in shortcuts:
        if any(k in q for k in keys):
            out.append(item)

    # Teléfono → conversación + estudiante
    digits = ''.join(c for c in q if c.isdigit())
    if len(digits) >= 7:
        from core.models import Estudiante, WhatsappLog
        from core.utils_telefono import normalizar_telefono

        tel = normalizar_telefono(digits) or digits
        est = (
            Estudiante.objects.filter(telefono__icontains=digits[-10:])
            .select_related('cliente')
            .first()
        )
        if est:
            out.append(_result(
                f'Estudiante · {est.nombre}',
                est.telefono or tel,
                reverse('admin:core_estudiante_change', args=[est.pk]),
                'person',
            ))
        conv_url = f'/admin/conversaciones/?telefono={tel}'
        out.append(_result(
            f'Conversación · …{tel[-4:]}',
            'Abrir inbox WhatsApp',
            conv_url,
            'chat',
        ))
        if WhatsappLog.objects.filter(telefono__icontains=digits[-8:]).exists():
            out.append(_result(
                'WhatsappLog (teléfono)',
                'Auditoría de mensajes',
                f'/admin/core/whatsapplog/?q={digits}',
                'history',
            ))

    # Nombre / cédula estudiante (consulta corta)
    if len(q) >= 3 and not q.isdigit():
        from core.models import Estudiante

        for est in (
            Estudiante.objects.filter(activo=True)
            .filter(nombre__icontains=q)
            .select_related('cliente')[:5]
        ):
            org = est.cliente.nombre if est.cliente_id else 'Sin org'
            out.append(_result(
                est.nombre,
                f'{org} · {est.telefono or "sin tel"}',
                reverse('admin:core_estudiante_change', args=[est.pk]),
                'person',
            ))
        for est in Estudiante.objects.filter(cedula__icontains=q)[:3]:
            out.append(_result(
                f'{est.nombre} ({est.cedula})',
                'Por documento',
                reverse('admin:core_estudiante_change', args=[est.pk]),
                'badge',
            ))

    # Campaña por nombre
    if len(q) >= 3:
        from core.models import Campana, Curso

        for camp in Campana.objects.filter(nombre__icontains=q).select_related('cliente')[:4]:
            out.append(_result(
                f'Campaña · {camp.nombre}',
                camp.cliente.nombre if camp.cliente_id else 'Sin org',
                reverse('admin:core_campana_change', args=[camp.pk]),
                'campaign',
            ))
        for curso in Curso.objects.filter(nombre__icontains=q).select_related('cliente')[:4]:
            out.append(_result(
                f'Curso · {curso.nombre}',
                curso.cliente.nombre if curso.cliente_id else 'General',
                reverse('admin:core_curso_change', args=[curso.pk]),
                'school',
            ))

    # Dedupe by link
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for item in out:
        if item.link in seen:
            continue
        seen.add(item.link)
        unique.append(item)
    return unique[:24]
