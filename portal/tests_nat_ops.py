"""Tests Fase C: checklist endurecido + reporte ops Nat."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, ProductoCatalogo, ProductoComercial, SesionComercial
from portal.models import PortalUsuario
from portal.nat_service import checklist_preparacion_nat, reporte_ops_nat


@override_settings(SECURE_SSL_REDIRECT=False)
class NatOpsFaseCTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Ops Nat SA',
            contacto_principal='A',
            email='opsnat@test.com',
            telefono='573004444001',
            activo=True,
            portal_productos='nat',
            tipo_proyecto='nat',
        )
        self.user = User.objects.create_user('ops_nat', 'o@nat.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')
        self.http = Client()
        self.http.post('/portal/login/', {'username': 'ops_nat', 'password': 'pass'})

    def test_checklist_sin_catalogo_es_bloqueante(self):
        items = {i['clave']: i for i in checklist_preparacion_nat(self.org)}
        self.assertFalse(items['catalogo']['ok'])
        self.assertEqual(items['catalogo']['nivel'], 'bad')
        self.assertTrue(items['catalogo']['bloqueante'])
        self.assertFalse(items['precios']['ok'])
        self.assertEqual(items['precios']['nivel'], 'bad')

    def test_checklist_ok_con_minimos(self):
        # Sin número propio: sandbox Twilio no debe bloquear.
        self.org.numero_whatsapp_nat = ''
        self.org.save(update_fields=['numero_whatsapp_nat'])
        ProductoCatalogo.objects.create(
            cliente=self.org,
            nombre='Bio X',
            descripcion='Bioestimulante foliar para estrés hídrico en café.',
            problema_que_resuelve='Estrés hídrico, amarillamiento por sequía en café.',
            activo=True,
        )
        ProductoComercial.objects.create(
            cliente=self.org,
            sku='BIO-X-1L',
            nombre='Bio X 1L',
            precio=35000,
            activo=True,
        )
        from core.models import BibliotecaConocimiento

        BibliotecaConocimiento.objects.create(
            cliente=self.org,
            titulo='Cartilla café',
            slug='cartilla-cafe-ops',
            formato='texto',
            texto_contenido='Manejo integrado de café…',
            estado_publicacion='publicado',
            estado_rag='indexado',
        )
        items = {i['clave']: i for i in checklist_preparacion_nat(self.org)}
        self.assertTrue(items['linea']['ok'])
        self.assertFalse(items['linea']['bloqueante'])
        self.assertTrue(items['catalogo']['ok'])
        self.assertTrue(items['precios']['ok'])
        self.assertTrue(items['biblioteca']['ok'])
        bloqueantes = [i for i in items.values() if i.get('bloqueante') and not i['ok']]
        self.assertEqual(bloqueantes, [])

    def test_linea_sin_numero_no_bloquea_con_sandbox(self):
        items = {i['clave']: i for i in checklist_preparacion_nat(self.org)}
        self.assertTrue(items['linea']['ok'])
        self.assertFalse(items['linea']['bloqueante'])
        self.assertEqual(items['linea']['nivel'], 'warn')

    def test_reporte_detecta_pregunta_y_recomendacion(self):
        ProductoCatalogo.objects.create(
            cliente=self.org,
            nombre='Fungicida Azul',
            descripcion='Control de roya en café arabica.',
            problema_que_resuelve='Roya del cafeto, manchas foliares.',
            activo=True,
        )
        SesionComercial.objects.create(
            cliente=self.org,
            telefono='573009998877',
            historial_mensajes=[
                {'role': 'user', 'content': 'Tengo roya en el café'},
                {
                    'role': 'assistant',
                    'content': 'Le recomiendo Fungicida Azul según su catálogo, dosis 300g/200L.',
                },
            ],
            fecha_ultimo_mensaje=timezone.now(),
        )
        data = reporte_ops_nat(self.org, dias=30)
        self.assertEqual(data['sesiones_periodo'], 1)
        self.assertTrue(any('roya' in p['pregunta'].lower() for p in data['preguntas_recientes']))
        self.assertTrue(
            any(r['producto'] == 'Fungicida Azul' for r in data['recomendaciones_detectadas'])
        )

    def test_vista_ops_y_export(self):
        r = self.http.get('/portal/nat/ops/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Operación Nat')
        r2 = self.http.get('/portal/nat/ops/exportar/')
        self.assertEqual(r2.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            r2['Content-Type'],
        )
