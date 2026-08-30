# -*- coding: utf-8 -*-
"""Formularios admin — catalogo voces Course Engine."""
from django import forms

from core.course_engine.voice_config import choices_voces, label_voz


class CourseEngineVoiceMixin:
    """Dropdown catalogo eki (2F+2M) + sync a course_engine_voice_id."""

    course_engine_voz_catalogo = forms.ChoiceField(
        label='Voz narracion (catalogo eki)',
        required=False,
        help_text='2 mujer + 2 hombre. Tambien puede pegar Voice ID manual abajo (clon cliente).',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        heredar = 'course_engine_tier' in self.fields
        self.fields['course_engine_voz_catalogo'].choices = choices_voces(
            incluir_vacio=not heredar,
            incluir_heredar=heredar,
        )
        vid = ''
        if getattr(self.instance, 'pk', None):
            vid = (getattr(self.instance, 'course_engine_voice_id', None) or '').strip()
        if vid:
            self.fields['course_engine_voz_catalogo'].initial = vid

    def clean(self):
        cleaned = super().clean()
        cat = (cleaned.get('course_engine_voz_catalogo') or '').strip()
        manual = (cleaned.get('course_engine_voice_id') or '').strip()
        if cat:
            cleaned['course_engine_voice_id'] = cat
            if not (cleaned.get('course_engine_voice_label') or '').strip():
                cleaned['course_engine_voice_label'] = label_voz(cat)
        elif manual:
            cleaned['course_engine_voice_id'] = manual
        return cleaned


class CursoCourseEngineForm(CourseEngineVoiceMixin, forms.ModelForm):
    class Meta:
        from core.models import Curso

        model = Curso
        fields = '__all__'


class ModuloCourseEngineVoiceMixin(CourseEngineVoiceMixin):
    pass
