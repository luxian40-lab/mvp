"""Bandeja de revisión v2. No cambia el listado si el interruptor está apagado."""
import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.conocimiento_agentes import bloque_conocimiento
from core.models import ConversacionRAGCandidata
from core.models_agentes import ConocimientoAgente


def _candidata(tag, estado=ConversacionRAGCandidata.ESTADO_PENDIENTE):
    return ConversacionRAGCandidata.objects.create(
        telefono=f'57300{tag[:7]}',
        pregunta=f'Consulta {tag}. Correo ana{tag}@example.com y numero 3001234567',
        respuesta_nati='Respuesta de prueba sin datos.',
        estado=estado,
    )


@override_settings(SECURE_SSL_REDIRECT=False, ADMIN_AGENTES_V2=False)
class BandejaAgentesTests(TestCase):
    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.user = get_user_model().objects.create_superuser(
            f'band_{self.tag}', f'band-{self.tag}@x.co', 'pass12345',
        )
        self.http = Client()
        self.http.force_login(self.user)
        self.fila = _candidata(self.tag)
        self.lista = reverse('admin:agents_commercial_conversacionragcandidata_changelist')
        self.ficha = reverse(
            'admin:agents_commercial_conversacionragcandidata_change',
            args=[self.fila.pk],
        )

    def test_apagado_sigue_el_listado_anterior(self):
        respuesta = self.http.get(self.lista)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.fila.telefono)
        self.assertNotContains(respuesta, 'eki_rev=pendientes')

    def test_ui_v2_oculta_el_telefono_y_enmascara(self):
        respuesta = self.http.get(self.lista, {'ui': 'v2'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.fila.telefono)
        self.assertNotContains(respuesta, '3001234567')
        self.assertNotContains(respuesta, f'ana{self.tag}@example.com')
        self.assertContains(respuesta, '[número]')
        self.assertContains(respuesta, '[correo]')
        self.assertContains(respuesta, 'eki_rev=pendientes')
        ficha = self.http.get(self.ficha, {'ui': 'v2'})
        self.assertContains(ficha, 'Pregunta de la persona')
        self.assertContains(ficha, 'Aprobar')
        self.assertNotContains(ficha, self.fila.telefono)

    @override_settings(ADMIN_AGENTES_V2=True)
    def test_aprobar_usa_la_revision_existente(self):
        respuesta = self.http.post(self.ficha, {
            'respuesta_revisada': 'Respuesta corregida por el equipo.',
            'agentes': ['ventas', 'coach'],
            'alcance': 'todos',
            'agents_commercial_conversacionragcandidata_bandeja_aprobar': '1',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, ConversacionRAGCandidata.ESTADO_APROBADA)
        self.assertEqual(self.fila.revisado_por_id, self.user.id)
        self.assertEqual(self.fila.respuesta_revisada, 'Respuesta corregida por el equipo.')
        self.assertEqual(self.fila.agentes, ['ventas', 'coach'])
        self.assertIsNotNone(self.fila.fecha_revision)
        self.assertEqual(
            ConocimientoAgente.objects.filter(estado=ConocimientoAgente.ESTADO_APROBADO).count(),
            2,
        )
        self.assertIn('Respuesta corregida', bloque_conocimiento('ventas'))
        self.assertIn('Respuesta corregida', bloque_conocimiento('coach'))
        self.assertNotIn('Respuesta corregida', bloque_conocimiento('finanzas'))

    def test_personal_sin_ser_superusuario_no_entra_con_ui_v2(self):
        alguien = get_user_model().objects.create_user(
            f'staff_{self.tag}', f'staff-{self.tag}@x.co', 'pass12345', is_staff=True,
        )
        from django.contrib.auth.models import Permission

        permiso = Permission.objects.get(
            codename='view_conversacionragcandidata',
            content_type__app_label='agents_commercial',
        )
        alguien.user_permissions.add(permiso)
        cliente = Client()
        cliente.force_login(alguien)
        respuesta = cliente.get(self.lista, {'ui': 'v2'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.fila.telefono)
        self.assertNotContains(respuesta, 'eki_rev=pendientes')
