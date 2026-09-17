"""Diagnóstico: ¿por qué el admin rechaza guardar estos módulos?

Reconstruye el POST completo del change form (campos del módulo + todos los
inlines) a partir de lo que ya está guardado, cambia solo el tipo/guía del
reto y reporta qué campo falla. Solo valida; no guarda nada.

Uso: DIAG_CURSO_ID=35 python manage.py shell < scripts/diag_form_modulo.py
"""
import os

from django.contrib import admin as dj_admin
from django.contrib.auth import get_user_model
from django.db.models.fields.files import FieldFile
from django.test import RequestFactory

from core.models import Modulo

CURSO_ID = os.environ.get('DIAG_CURSO_ID')
MODULO_IDS = [int(x) for x in (os.environ.get('DIAG_MODULO_IDS') or '').split(',') if x.strip()]


def valor(form, name, field):
    val = form.initial.get(name, field.initial)
    if val is None:
        return ''
    if isinstance(val, FieldFile):
        return ''
    if hasattr(val, 'pk'):
        return val.pk
    if isinstance(val, bool):
        return 'on' if val else ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%dT%H:%M')
    return val


def campos(form, prefijo=''):
    data = {}
    for nombre, field in form.fields.items():
        if field.disabled:
            continue
        data[f'{prefijo}{nombre}'] = valor(form, nombre, field)
    return data


from django.contrib.sessions.backends.db import SessionStore

rf = RequestFactory()
# ?avanzado=1 = la vista «legacy / más opciones», que sí trae los inlines.
request = rf.get('/?avanzado=1')
request.user = get_user_model().objects.filter(is_superuser=True).first()
request.session = SessionStore()
ma = dj_admin.site._registry[Modulo]

qs = Modulo.objects.all()
if MODULO_IDS:
    qs = qs.filter(id__in=MODULO_IDS)
elif CURSO_ID:
    qs = qs.filter(curso_id=int(CURSO_ID))
else:
    qs = qs.none()

for modulo in qs.order_by('numero', 'id'):
    print(f'\n===== MODULO {modulo.id} num={modulo.numero} {modulo.titulo!r}')
    form_cls = ma.get_form(request, modulo, change=True)
    data = campos(form_cls(instance=modulo))
    data['tipo_reto_ia'] = 'plan_accion'
    data['reto_guia_ia'] = 'PRUEBA DIAGNOSTICO'

    inlines = []
    for inline in ma.get_inline_instances(request, modulo):
        FS = inline.get_formset(request, modulo)
        fs = FS(instance=modulo)
        p = fs.prefix
        data[f'{p}-TOTAL_FORMS'] = fs.total_form_count()
        data[f'{p}-INITIAL_FORMS'] = fs.initial_form_count()
        data[f'{p}-MIN_NUM_FORMS'] = 0
        data[f'{p}-MAX_NUM_FORMS'] = 1000
        for i, sub in enumerate(fs.forms):
            data.update(campos(sub, prefijo=f'{p}-{i}-'))
        inlines.append((FS, p))

    form = form_cls(data=data, instance=Modulo.objects.get(id=modulo.id))
    ok = form.is_valid()
    print(f'  FORM PRINCIPAL valido={ok}')
    for campo, errores in form.errors.items():
        print(f'    CAMPO {campo}: {[str(e) for e in errores]}')

    for FS, p in inlines:
        fs = FS(data=data, instance=Modulo.objects.get(id=modulo.id))
        if fs.is_valid():
            continue
        print(f'  INLINE {p} INVALIDO')
        for e in fs.non_form_errors():
            print(f'    GRUPO: {e}')
        for i, errores in enumerate(fs.errors):
            if errores:
                print(f'    fila {i}: {dict(errores)}')
