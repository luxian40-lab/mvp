"""Uso de IA por persona en Desarrollo de habilidades."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Estudiante, WhatsappLog
from portal.models import PortalUsuario


def _org(nombre):
    return Cliente.objects.create(
        nombre=nombre, contacto_principal='A', email=f'{nombre.lower()}@test.com',
        telefono='573009990300', activo=True, portal_productos='cursos',
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class UsoIaPorPersonaTests(TestCase):
    def test_cuenta_preguntas_por_persona_y_agente(self):
        org = _org('IaOrg')
        otra = _org('IaOtra')
        ana = Estudiante.objects.create(nombre='Ana', cedula='400001', telefono='573001400001', cliente=org, activo=True)
        Estudiante.objects.create(nombre='Beto', cedula='400002', telefono='573001400002', cliente=org, activo=True)
        ajena = Estudiante.objects.create(nombre='Ajena', cedula='400099', telefono='573001400099', cliente=otra, activo=True)

        def log(telefono, agente, *, estudiante=None, dias=1, tipo='INCOMING'):
            fila = WhatsappLog.objects.create(
                telefono=telefono, mensaje='hola', tipo=tipo, agente_usado=agente, estudiante=estudiante,
            )
            WhatsappLog.objects.filter(pk=fila.pk).update(fecha=timezone.now() - timedelta(days=dias))

        log(ana.telefono, 'sandbox_coach')
        log(ana.telefono, 'sandbox_coach')
        log(ana.telefono, 'BOT_COMERCIAL', estudiante=ana)
        log(ana.telefono, 'sandbox_ventas', dias=120)
        log(ana.telefono, 'sandbox_coach', tipo='SENT')
        log(ana.telefono, '')
        log(ajena.telefono, 'sandbox_coach', estudiante=ajena)

        user = User.objects.create_user('ia_admin', 'ia@t.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=org, rol='admin')
        http = Client()
        http.post('/portal/login/', {'username': 'ia_admin', 'password': 'pass'})
        r = http.get('/portal/analitica/?s=habilidades')
        self.assertEqual(r.status_code, 200)

        uso = r.context['uso_ia']
        self.assertEqual(uso['agentes'], ['Coach', 'Agrónomo (Nat)'])
        self.assertEqual(uso['total'], 3)
        self.assertEqual(uso['usan'], 1)
        self.assertEqual(uso['usan_pct'], 50.0)
        self.assertEqual(len(uso['personas']), 1)
        self.assertEqual(uso['personas'][0]['nombre'], 'Ana')
        self.assertEqual(uso['personas'][0]['por_agente'], [2, 1])
        self.assertEqual(uso['mas_usadas'], ['Coach'])
        self.assertEqual(uso['mas_usada_n'], 2)
        self.assertEqual(uso['mas_usada_pct'], round(200 / 3, 1))
        self.assertEqual(
            [(fila['nombre'], fila['n'], fila['pct']) for fila in uso['comparacion']],
            [('Coach', 2, round(200 / 3, 1)), ('Agrónomo (Nat)', 1, round(100 / 3, 1))],
        )

        html = r.content.decode()
        self.assertIn('IA más usada', html)
        self.assertIn('Comparación por agentes', html)
        self.assertIn('Uso de IA por persona', html)
        self.assertIn('Agrónomo (Nat)', html)
        self.assertNotIn('Ajena', html)
        self.assertIsNone(http.get('/portal/analitica/').context['uso_ia'])
