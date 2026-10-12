import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.admin.grupos import EMOJI_GRUPO
from core.models import Cliente, Estudiante
from core.models_extras import GrupoEstudiantes
from core.grupos_miembros import (
    agregar_miembros_por_identificadores,
    parsear_lineas_identificadores,
    quitar_miembros_por_identificadores,
)


class GruposMiembrosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Cliente Test', activo=True)
        self.grupo = GrupoEstudiantes.objects.create(
            nombre='Grupo A', emoji='G', cliente=self.cliente, activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='999888777',
            nombre='Ana Test',
            telefono='573001112233',
            cliente=self.cliente,
            activo=True,
            estado_onboarding='completado',
        )

    def test_agregar_y_quitar_por_cedula(self):
        r = agregar_miembros_por_identificadores(self.grupo, ['999888777'])
        self.assertEqual(r['agregados'], 1)
        self.assertTrue(self.grupo.estudiantes.filter(pk=self.est.pk).exists())

        r2 = quitar_miembros_por_identificadores(self.grupo, ['999888777'])
        self.assertEqual(r2['quitados'], 1)
        self.assertFalse(self.grupo.estudiantes.filter(pk=self.est.pk).exists())

    def test_parsear_lineas(self):
        texto = '111\n222, 333;444'
        self.assertEqual(parsear_lineas_identificadores(texto), ['111', '222', '333', '444'])

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_alta_ofrece_emojis_para_elegir(self):
        tag = uuid.uuid4().hex[:8]
        user = get_user_model().objects.create_superuser(
            f'grp_{tag}', f'grp-{tag}@x.co', 'pass12345',
        )
        cliente = Client()
        cliente.force_login(user)
        alta = cliente.get(reverse('admin:core_grupoestudiantes_add'))
        self.assertEqual(alta.status_code, 200)
        for valor, etiqueta in EMOJI_GRUPO:
            self.assertContains(alta, valor)
            self.assertContains(alta, etiqueta.split(' ', 1)[1])
        self.assertContains(alta, 'type="radio"')
        ficha = cliente.get(
            reverse('admin:core_grupoestudiantes_change', args=[self.grupo.pk]),
        )
        self.assertContains(ficha, 'G Actual')
