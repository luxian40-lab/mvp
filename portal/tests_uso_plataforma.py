"""Cifras de Uso de plataforma: cursos del cliente, generales y sin inventar tasas."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, WhatsappLog
from core.models_certificados import Certificado
from portal.models import PortalUsuario
from portal.uso_plataforma import uso_plataforma


@override_settings(SECURE_SSL_REDIRECT=False)
class UsoPlataformaTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Amalthea',
            contacto_principal='A',
            email='uso@test.com',
            telefono='573009990000',
            activo=True,
            portal_productos='cursos',
        )
        self.propio = Curso.objects.create(nombre='Curso finca', cliente=self.org, activo=True)
        self.general = Curso.objects.create(
            nombre='Tome las riendas de su dinero',
            cliente=None,
            catalogo_menu=True,
            activo=True,
        )
        ahora = timezone.now()
        self.ana = self._est('Ana', '573001110001')
        self.beto = self._est('Beto', '573001110002')
        self.caro = self._est('Caro', '573001110003')
        self.dani = self._est('Dani', '573001110004')
        self.eva = self._est('Eva', '573001110005')
        ProgresoEstudiante.objects.create(
            estudiante=self.ana, curso=self.propio, completado=False,
            fecha_ultimo_avance=ahora,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.beto, curso=self.general, completado=False,
            fecha_ultimo_avance=ahora - timedelta(days=40),
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.caro, curso=self.propio, completado=True,
            fecha_ultimo_avance=ahora,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.eva, curso=self.propio, completado=False,
            fecha_ultimo_avance=ahora - timedelta(days=40),
        )
        Certificado.objects.create(
            estudiante=self.caro,
            curso=self.propio,
            calificacion_final=Decimal('90.00'),
            fecha_inicio=timezone.localdate(),
            emitido=True,
        )
        t0 = ahora - timedelta(minutes=10)
        entra = WhatsappLog.objects.create(
            telefono=self.ana.telefono, mensaje='hola', tipo='INCOMING', estudiante=self.ana,
        )
        sale = WhatsappLog.objects.create(
            telefono=self.ana.telefono, mensaje='sigo', tipo='SENT', estudiante=self.ana,
        )
        WhatsappLog.objects.filter(pk=entra.pk).update(fecha=t0)
        WhatsappLog.objects.filter(pk=sale.pk).update(fecha=t0 + timedelta(seconds=120))
        reciente = WhatsappLog.objects.create(
            telefono=self.eva.telefono, mensaje='sigo', tipo='INCOMING', estudiante=self.eva,
        )
        WhatsappLog.objects.filter(pk=reciente.pk).update(fecha=ahora)

    def _est(self, nombre, telefono):
        return Estudiante.objects.create(
            nombre=nombre,
            cedula=telefono[-6:],
            telefono=telefono,
            cliente=self.org,
            activo=True,
        )

    def test_cajas_con_definicion_real(self):
        data = uso_plataforma(self.org)
        self.assertEqual(data['registrados'], 5)
        self.assertEqual(data['en_curso'], 3)
        self.assertEqual(data['certificados'], 1)
        self.assertEqual(data['abandono_pct'], 20.0)
        self.assertEqual(data['abandono_n'], 1)
        self.assertEqual(data['finalizacion_pct'], 20.0)
        self.assertEqual(data['finalizacion_n'], 1)
        self.assertEqual(data['activos_mes'], 3)
        self.assertEqual(data['respuesta'], '2 min')
        self.assertEqual(data['retorno_pct'], 50.0)
        self.assertEqual(data['retorno_n'], 1)
        self.assertEqual(data['retorno_base'], 2)
        self.assertEqual(data['uso_pct'], 60.0)
        self.assertEqual(len(data['serie_activos']), 6)
        self.assertEqual(data['serie_abandonos'][-1]['valor'], 1)
        self.assertEqual(data['serie_activos'][-1]['valor'], data['activos_mes'])

    def test_sin_registrados_no_inventa_porcentaje(self):
        from core.models import Cliente

        vacia = Cliente.objects.create(
            nombre='Vacia',
            contacto_principal='B',
            email='vacia@test.com',
            telefono='573009990001',
            activo=True,
        )
        data = uso_plataforma(vacia)
        self.assertEqual(data['registrados'], 0)
        self.assertIsNone(data['abandono_pct'])
        self.assertIsNone(data['finalizacion_pct'])
        self.assertIsNone(data['retorno_pct'])
        self.assertIsNone(data['uso_pct'])
        self.assertIsNone(data['respuesta'])

    def test_pagina_muestra_menu_y_nueve_cajas(self):
        user = User.objects.create_user('uso_admin', 'u@t.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=self.org, rol='admin')
        http = Client()
        http.post('/portal/login/', {'username': 'uso_admin', 'password': 'pass'})
        r = http.get('/portal/analitica/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="analitica-sub"', html)
        self.assertIn('analitica-toggle', html)
        self.assertNotIn('ana-burger', html)
        self.assertIn('Uso de plataforma', html)
        self.assertIn('Desarrollo de habilidades', html)
        self.assertIn('>Retención</a>', html)
        self.assertIn('>Impacto</a>', html)
        self.assertNotIn('>Centro de éxito</a>', html)
        for etiqueta in (
            'Registrados', 'En curso', 'Certificados', 'Tasa de abandono',
            'Tasa de finalización', 'Activos este mes', 'Tiempo de respuesta',
            'Tasa de retorno', 'Uso del producto',
        ):
            self.assertIn(etiqueta, html)
        self.assertIn('>Activos<', html)
        self.assertIn('>Abandonos<', html)
        self.assertIn('>Uso<', html)
        self.assertIn('20.0%', html)
        self.assertIn('2 min', html)
        hab = http.get('/portal/analitica/?s=habilidades')
        self.assertEqual(hab.status_code, 200)
        cuerpo = hab.content.decode()
        self.assertIn('id="ana-habilidades"', cuerpo)
        self.assertIn('id="ana-uso" aria-labelledby="ana-uso-title" hidden', cuerpo)
        self.assertIn('Desarrollo de habilidades', cuerpo)
        impacto = http.get('/portal/analitica/?s=impacto')
        self.assertEqual(impacto.status_code, 200)
        limpio = impacto.content.decode()
        self.assertIn('id="ana-impacto"', limpio)
        self.assertIn('id="ana-uso" aria-labelledby="ana-uso-title" hidden', limpio)
        self.assertIn('Impacto.', limpio)
        self.assertIn('Alcance inclusivo', limpio)
        self.assertIn('S1', limpio)
        self.assertNotIn('Power skills', limpio)
        self.assertIn('<section id="ana-impacto"', limpio)
        self.assertNotIn('id="ana-impacto" hidden', limpio)
