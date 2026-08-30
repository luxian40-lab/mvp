"""Vistas admin — preview voz Course Engine."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.course_engine.voice_config import (
    resolver_voice_id_curso,
    resolver_voice_id_modulo,
    resolver_voice_label_modulo,
)
from core.course_engine.voice_preview import MUESTRA_VOZ_TEXTO, generar_muestra_voz
from core.models import Curso, Modulo


def _preview_context(request, *, ok, voice_id, voice_label, tts=None, error='', back_url=''):
    audio_url = ''
    if tts and tts.url:
        audio_url = tts.url
    return {
        'ok': ok,
        'voice_id': voice_id,
        'voice_label': voice_label,
        'audio_url': audio_url,
        'error': error,
        'muestra_texto': MUESTRA_VOZ_TEXTO,
        'back_url': back_url or request.META.get('HTTP_REFERER', '/admin/'),
    }


def preview_voz_curso_view(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if not request.user.has_perm('core.change_curso'):
        messages.error(request, 'Sin permiso.')
        return redirect('admin:core_curso_change', curso_id)

    voice_id = (request.GET.get('voice_id') or '').strip() or resolver_voice_id_curso(curso)
    label = (curso.course_engine_voice_label or '').strip() or 'Curso'
    back = reverse('admin:core_curso_change', args=[curso_id])

    out = generar_muestra_voz(voice_id, voice_label=label)
    if not out.ok:
        messages.error(request, f'Muestra voz: {out.error}')

    return render(
        request,
        'admin/course_engine/voice_preview.html',
        _preview_context(
            request,
            ok=out.ok,
            voice_id=out.voice_id,
            voice_label=out.voice_label,
            tts=out.tts,
            error=out.error,
            back_url=back,
        ),
    )


def preview_voz_modulo_view(request, modulo_id):
    modulo = get_object_or_404(Modulo.objects.select_related('curso'), pk=modulo_id)
    if not request.user.has_perm('core.change_modulo'):
        messages.error(request, 'Sin permiso.')
        return redirect('admin:core_modulo_change', modulo_id)

    voice_id = (request.GET.get('voice_id') or '').strip() or resolver_voice_id_modulo(modulo)
    label = resolver_voice_label_modulo(modulo)
    back = reverse('admin:core_modulo_change', args=[modulo_id])

    out = generar_muestra_voz(voice_id, voice_label=label)
    if not out.ok:
        messages.error(request, f'Muestra voz: {out.error}')

    return render(
        request,
        'admin/course_engine/voice_preview.html',
        _preview_context(
            request,
            ok=out.ok,
            voice_id=out.voice_id,
            voice_label=out.voice_label,
            tts=out.tts,
            error=out.error,
            back_url=back,
        ),
    )


def html_boton_preview_voz(*, preview_url: str, voice_id: str | None, label: str, curso_or_modulo_id: int | None = None, es_modulo: bool = False) -> str:
    from django.utils.html import format_html, format_html_join

    from core.course_engine.voice_config import catalogo_voces

    if not voice_id:
        return format_html(
            '<p style="color:#e65100;margin:0;">Elija voz del catalogo o pegue <strong>Voice ID</strong> '
            '(clon cliente) y guarde.</p>'
        )
    links = format_html(
        '<a class="button" href="{}" target="_blank" rel="noopener" '
        'style="margin-bottom:0.5rem;display:inline-block;">Escuchar muestra (~5 s)</a>',
        preview_url,
    )
    catalogo_bits = []
    if curso_or_modulo_id is not None:
        base = preview_url.split('?')[0]
        for v in catalogo_voces():
            u = f"{base}?voice_id={v['id']}"
            catalogo_bits.append(format_html(
                '<a href="{}" target="_blank" rel="noopener" style="margin-right:8px;font-size:12px;">{}</a>',
                u,
                v['label'],
            ))
    catalogo_html = format_html('<p style="margin:0.35rem 0 0;font-size:12px;">Probar catalogo: {}</p>', format_html_join('', catalogo_bits)) if catalogo_bits else ''

    return format_html(
        '{}'
        '{}'
        '<p style="margin:0.35rem 0 0;font-size:12px;color:#666;">'
        '<strong>Activa:</strong> <code>{}</code> — {}</p>',
        links,
        catalogo_html,
        voice_id,
        label or '—',
    )
