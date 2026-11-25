"""Cifras de Uso de plataforma: cursos del cliente, generales y sin inventar tasas."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, WhatsappLog
from core.certificados.models_certificados import Certificado
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

    def test_en_curso_no_cuenta_solo_aceptar_flujo(self):
        """Progreso abierto sin avance real no entra en En curso."""
        solo_acepto = self._est('Solo', '573001110006')
        ProgresoEstudiante.objects.create(
            estudiante=solo_acepto, curso=self.propio, completado=False,
            fecha_ultimo_avance=None,
        )
        data = uso_plataforma(self.org)
        self.assertEqual(data['registrados'], 6)
        self.assertEqual(data['en_curso'], 3)

    def test_no_cuenta_telefono_prueba_ni_fuera_de_flow(self):
        """Hook 0629 y quien no viene de flow_registro no entran si ya hay cohorte flow."""
        for est in (self.ana, self.beto, self.caro, self.dani, self.eva):
            est.wa_optin_origen = 'flow_registro'
            est.save(update_fields=['wa_optin_origen'])
        hook = self._est('Julian', '573026480629')
        hook.wa_optin_origen = 'habeas'
        hook.save(update_fields=['wa_optin_origen'])
        ProgresoEstudiante.objects.create(
            estudiante=hook, curso=self.propio, completado=True,
            fecha_ultimo_avance=timezone.now(),
        )
        Certificado.objects.create(
            estudiante=hook,
            curso=self.propio,
            calificacion_final=Decimal('95.00'),
            fecha_inicio=timezone.localdate(),
            emitido=True,
        )
        andres = self._est('Andres Prueba', '573001110085')
        andres.wa_optin_origen = 'habeas'
        andres.save(update_fields=['wa_optin_origen'])
        with self.settings(EKI_ANALITICA_EXCLUIR_TELEFONOS=['573001110085']):
            data = uso_plataforma(self.org)
        self.assertEqual(data['registrados'], 5)
        self.assertEqual(data['certificados'], 1)

    def test_cajas_con_definicion_real(self):
        data = uso_plataforma(self.org)
        self.assertEqual(data['registrados'], 5)
        self.assertEqual(data['en_curso'], 3)
        self.assertEqual(data['certificados'], 1)
        self.assertEqual(data['no_inicio_pct'], 20.0)
        self.assertEqual(data['no_inicio_n'], 1)
        # Beto en curso sin actividad reciente (40 días) → abandono 2 semanas.
        # Ana activa, Eva activa por WA, Beto frío → 1 de 3.
        self.assertEqual(data['abandono_2s_n'], 1)
        self.assertEqual(data['abandono_2s_base'], 3)
        self.assertEqual(data['abandono_2s_pct'], round(100 / 3, 1))
        self.assertEqual(data['activos_mes'], 2)
        # Retorno sobre histórico de curso: Beto y Eva tenían actividad >30d; Eva volvió.
        self.assertEqual(data['retorno_pct'], 50.0)
        self.assertEqual(data['retorno_n'], 1)
        self.assertEqual(data['retorno_base'], 2)
        self.assertEqual(data['uso_pct'], 60.0)
        self.assertEqual(len(data['serie_activos']), 6)
        self.assertEqual(data['serie_abandonos'][-1]['valor'], 1)
        self.assertEqual(data['serie_activos'][-1]['valor'], 3)
        self.assertNotIn('respuesta', data)
        self.assertNotIn('finalizacion_pct', data)

    def test_sin_registrados_no_inventa_porcentaje(self):
        vacia = Cliente.objects.create(
            nombre='Vacia',
            contacto_principal='B',
            email='vacia@test.com',
            telefono='573009990001',
            activo=True,
        )
        data = uso_plataforma(vacia)
        self.assertEqual(data['registrados'], 0)
        self.assertIsNone(data['no_inicio_pct'])
        self.assertIsNone(data['abandono_2s_pct'])
        self.assertIsNone(data['retorno_pct'])
        self.assertIsNone(data['uso_pct'])

    def test_pagina_muestra_menu_y_cajas(self):
        user = User.objects.create_user('uso_admin', 'u@t.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=self.org, rol='admin')
        http = Client()
        http.post('/portal/login/', {'username': 'uso_admin', 'password': 'pass'})
        r = http.get('/portal/analitica/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="analitica-sub"', html)
        self.assertIn('Uso de plataforma', html)
        for etiqueta in (
            'Registrados', 'En curso', 'Certificados', 'Tasa de no inicio',
            'Tasa de abandono 2 semanas', 'Activos este mes',
            'Tasa de retorno', 'Uso del producto', 'Uso de agentes',
            'Tasa de inicio', 'Culminación sobre iniciadores', 'Culminación sobre aceptantes',
        ):
            self.assertIn(etiqueta, html)
        self.assertNotIn('Tasa de finalización', html)
        self.assertNotIn('Tiempo de respuesta', html)
        self.assertIn('>Activos<', html)
        self.assertIn('20.0%', html)
        self.assertIn('/portal/analitica/nps/', html)
        hab = http.get('/portal/analitica/?s=habilidades')
        self.assertEqual(hab.status_code, 200)
        cuerpo = hab.content.decode()
        self.assertIn('id="ana-habilidades"', cuerpo)
        self.assertIn('id="ana-uso" aria-labelledby="ana-uso-title" hidden', cuerpo)
