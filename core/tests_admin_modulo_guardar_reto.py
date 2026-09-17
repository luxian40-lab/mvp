"""Guardar un módulo desde el admin tocando solo los campos del reto de Claudia.

Reproduce el flujo del navegador: GET del change form, se reenvían todos los
campos tal cual vinieron y solo se cambian «Tipo de reto» y «Guía del reto».
"""
from django.contrib.auth import get_user_model
from django.db.models.fields.files import FieldFile
from django.test import TestCase, override_settings

from core.models import (
    Cliente,
    Curso,
    Modulo,
    PasoModulo,
    SeccionModulo,
)


def _valor_inicial(form, name, field):
    val = form.initial.get(name, field.initial)
    if val is None:
        return ''
    if isinstance(val, FieldFile):
        # El navegador no reenvía el archivo ya guardado; mandar vacío lo conserva.
        return ''
    if hasattr(val, 'pk'):
        return val.pk
    if isinstance(val, bool):
        return 'on' if val else ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%dT%H:%M')
    if isinstance(val, (list, tuple)):
        return [getattr(v, 'pk', v) for v in val]
    return val


def payload_desde_changeform(response):
    """Arma el POST completo (form principal + management forms de inlines)."""
    data = {}
    form = response.context['adminform'].form
    for name, field in form.fields.items():
        if field.disabled:
            continue
        data[name] = _valor_inicial(form, name, field)

    for inline in response.context['inline_admin_formsets']:
        fs = inline.formset
        p = fs.prefix
        data[f'{p}-TOTAL_FORMS'] = fs.total_form_count()
        data[f'{p}-INITIAL_FORMS'] = fs.initial_form_count()
        data[f'{p}-MIN_NUM_FORMS'] = 0
        data[f'{p}-MAX_NUM_FORMS'] = 1000
        for i, subform in enumerate(fs.forms):
            for name, field in subform.fields.items():
                if field.disabled:
                    continue
                data[f'{p}-{i}-{name}'] = _valor_inicial(subform, name, field)
    return data


@override_settings(SECURE_SSL_REDIRECT=False)
class GuardarRetoDesdeAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser('qa_reto', 'qa@eki.test', 'x')
        self.client.force_login(self.admin)

        self.cliente = Cliente.objects.create(nombre='QA Admin Reto', activo=True)
        self.curso = Curso.objects.create(
            nombre='QA Admin Reto',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=True,
        )
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1 admin',
            descripcion='d',
            contenido='Contenido M1',
            publicado_wa=True,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        sec = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='S1')
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=sec,
            orden=1,
            titulo='P1',
            contenido='Micro 1',
            activo=True,
        )
        self.url = f'/admin/core/modulo/{self.modulo.pk}/change/'

    def _guardar_solo_el_reto(self):
        get = self.client.get(self.url)
        self.assertEqual(get.status_code, 200)
        data = payload_desde_changeform(get)
        data['tipo_reto_ia'] = Modulo.TIPO_RETO_PLAN
        data['reto_guia_ia'] = 'Pida un plan de manejo para la próxima semana.'
        data['_continue'] = 'Guardar y continuar editando'
        return self.client.post(self.url, data, follow=False)

    def test_guardar_el_reto_con_secciones_intercaladas(self):
        """Estructura heredada del Builder: no debe bloquear un cambio ajeno a los pasos."""
        sec_a = self.modulo.secciones.first()
        sec_b = SeccionModulo.objects.create(modulo=self.modulo, orden=2, titulo='S2')
        PasoModulo.objects.create(
            modulo=self.modulo, seccion=sec_b, orden=2, titulo='P2',
            contenido='Micro 2', activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.modulo, seccion=sec_a, orden=3, titulo='P3',
            contenido='Micro 3', activo=True,
        )

        post = self._guardar_solo_el_reto()

        if post.status_code == 200:
            errores = post.context['adminform'].form.errors.as_json()
            formsets = [
                fs.formset.non_form_errors()
                for fs in post.context['inline_admin_formsets']
                if fs.formset.non_form_errors()
            ]
            self.fail(f'El admin rechazó el guardado: {errores} | inlines: {formsets}')
        self.assertEqual(post.status_code, 302)
        self.modulo.refresh_from_db()
        self.assertEqual(self.modulo.tipo_reto_ia, Modulo.TIPO_RETO_PLAN)

    def test_guardar_tipo_reto_y_guia(self):
        get = self.client.get(self.url)
        self.assertEqual(get.status_code, 200)

        data = payload_desde_changeform(get)
        data['tipo_reto_ia'] = Modulo.TIPO_RETO_PLAN
        data['reto_guia_ia'] = 'Pida un plan de manejo para la próxima semana.'
        data['_continue'] = 'Guardar y continuar editando'

        post = self.client.post(self.url, data, follow=False)

        if post.status_code == 200:
            form = post.context['adminform'].form
            self.fail(f'El admin rechazó el guardado: {form.errors.as_json()}')
        self.assertEqual(post.status_code, 302)

        self.modulo.refresh_from_db()
        self.assertEqual(self.modulo.tipo_reto_ia, Modulo.TIPO_RETO_PLAN)
        self.assertIn('plan de manejo', self.modulo.reto_guia_ia)
