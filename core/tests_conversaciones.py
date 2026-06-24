from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from core.conversaciones_service import construir_contexto_inbox
from core.models import Cliente, Estudiante, WhatsappLog
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class ConversacionesServiceTests(TestCase):
    def setUp(self):
        self.cliente_a = Cliente.objects.create(
            nombre='Org A',
            contacto_principal='A',
            email='a@test.com',
            telefono='573001100010',
            activo=True,
        )
        self.cliente_b = Cliente.objects.create(
            nombre='Org B',
            contacto_principal='B',
            email='b@test.com',
            telefono='573001100011',
            activo=True,
        )
        self.est_a = Estudiante.objects.create(
            cedula='9001', nombre='Ana Org A', telefono='573111100001', cliente=self.cliente_a,
        )
        self.est_b = Estudiante.objects.create(
            cedula='9002', nombre='Bob Org B', telefono='573111100002', cliente=self.cliente_b,
        )
        WhatsappLog.objects.create(
            telefono=self.est_a.telefono, mensaje='Hola desde A', tipo='INCOMING', estudiante=self.est_a,
        )
        WhatsappLog.objects.create(
            telefono=self.est_b.telefono, mensaje='Hola desde B', tipo='INCOMING', estudiante=self.est_b,
        )

    def test_filtro_por_org_fijo_portal(self):
        ctx = construir_contexto_inbox(org_fijo=self.cliente_a)
        self.assertEqual(ctx['total_contactos'], 1)
        self.assertFalse(ctx['mostrar_filtro_clientes'])
        self.assertEqual(ctx['org_nombre'], 'Org A')

    def test_mensajes_sin_truncar(self):
        largo = 'Linea uno\nLinea dos ' + ('x' * 500)
        WhatsappLog.objects.create(
            telefono=self.est_a.telefono, mensaje=largo, tipo='INCOMING', estudiante=self.est_a,
        )
        ctx = construir_contexto_inbox(
            org_fijo=self.cliente_a,
            estudiante_id=self.est_a.id,
            telefono=self.est_a.telefono,
        )
        self.assertTrue(ctx['mensajes'])
        self.assertIn('Linea dos', ctx['mensajes'][-1]['mensaje'])


class PortalConversacionesVistaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Portal Conv',
            contacto_principal='X',
            email='pc@test.com',
            telefono='573001100012',
            activo=True,
            portal_productos='cursos',
        )
        self.est = Estudiante.objects.create(
            cedula='9010', nombre='Joven Chat', telefono='573111100010', cliente=self.cliente,
        )
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='Mensaje portal',
            tipo='INCOMING',
            estudiante=self.est,
        )
        user = User.objects.create_user('conv_portal', password='pass1234')
        PortalUsuario.objects.create(user=user, organizacion=self.cliente, rol='admin')
        self.http = Client()
        session = self.http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=user).pk
        session.save()

    def test_portal_conversaciones_solo_su_org(self):
        r = self.http.get('/portal/conversaciones/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Joven Chat')
        self.assertContains(r, 'Mensaje portal')
        self.assertContains(r, 'wa-inbox')

    def test_portal_conversaciones_chat_directo(self):
        r = self.http.get(f'/portal/conversaciones/?estudiante={self.est.pk}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Mensaje portal')
