# -*- coding: utf-8 -*-
"""Formularios admin — catalogo voces Course Engine."""
from django import forms

from core.course_engine.voice_config import choices_voces, label_voz


def _widget_voz_catalogo(*, heredar: bool = False):
    return forms.Select(
        choices=choices_voces(incluir_vacio=not heredar, incluir_heredar=heredar),
    )


def configure_course_engine_voice_field(form, *, heredar: bool = False):
    name = 'course_engine_voice_id'
    if name not in form.fields:
        return
    form.fields[name].widget = _widget_voz_catalogo(heredar=heredar)
    if heredar:
        form.fields[name].help_text = (
            'Vacío = hereda voz del curso. Catalogo eki o pegue Voice ID de clon cliente.'
        )
    else:
        form.fields[name].help_text = (
            'Catalogo eki: 2 mujer + 2 hombre. Vacio = ELEVENLABS_VOICE_ID del entorno. '
            'Para voz clonada del cliente, pegue el Voice ID de ElevenLabs.'
        )
    inst = getattr(form, 'instance', None)
    vid = (getattr(inst, name, None) or '').strip() if inst else ''
    if vid and vid not in {c[0] for c in form.fields[name].widget.choices}:
        form.fields[name].widget.choices = list(form.fields[name].widget.choices) + [
            (vid, f'{label_voz(vid)} (custom)'),
        ]


class CursoCourseEngineForm(forms.ModelForm):
    class Meta:
        from core.models import Curso

        model = Curso
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_course_engine_voice_field(self, heredar=False)

    def clean(self):
        cleaned = super().clean()
        vid = (cleaned.get('course_engine_voice_id') or '').strip()
        if vid and not (cleaned.get('course_engine_voice_label') or '').strip():
            cleaned['course_engine_voice_label'] = label_voz(vid)
        return cleaned


def autofill_voice_label(cleaned: dict) -> dict:
    vid = (cleaned.get('course_engine_voice_id') or '').strip()
    if vid and not (cleaned.get('course_engine_voice_label') or '').strip():
        cleaned['course_engine_voice_label'] = label_voz(vid)
    return cleaned
