"""Tests utilidades de prueba empleabilidad."""

import sys
from contextlib import nullcontext
from types import ModuleType
from unittest.mock import MagicMock, patch

from django.test import Client as HttpClient
from django.test import TestCase, override_settings

from core.empleabilidad_prueba import (
    completar_mision_con_codigo,
    configurar_cliente_empleabilidad,
    crear_aliados_demo,
    setup_prueba_empleabilidad,
    simular_ubicacion_whatsapp,
)
from core.models import (
    AliadoEmpleabilidad,
    Cliente,
    Curso,
    Estudiante,
    MisionEmpleabilidad,
    Modulo,
    ProgresoEstudiante,
)
from core.response_templates import get_response_for_intent


def _install_twilio_rest_stub(client_class):
    root = sys.modules.get('twilio') or ModuleType('twilio')
    rest = sys.modules.get('twilio.rest') or ModuleType('twilio.rest')
    rest.Client = client_class
    sys.modules.setdefault('twilio', root)
    sys.modules['twilio.rest'] = rest


def _bodies_from_twilio_mock(create_mock):
    bodies = []
    for call in create_mock.call_args_list:
        kw = call.kwargs or {}
        args = call.args or ()
        body = kw.get('body') if 'body' in kw else (args[0] if args else None)
        if body:
            bodies.append(body)
    return bodies


class EmpleabilidadPruebaSetupTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Emp Prueba',
            contacto_principal='X',
            email='emp@test.com',
            telefono='573001100001',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='emp99',
            nombre='Joven Prueba',
            telefono='573001100099',
            cliente=self.cliente,
            activo=True,
            estado_chat='ACTIVO',
        )

    def test_configura_cliente_y_aliados(self):
        cambios = configurar_cliente_empleabilidad(self.cliente, radio_metros=1200)
        self.assertTrue(any('empleabilidad_exploracion_activa' in c for c in cambios))
        self.cliente.refresh_from_db()
        self.assertIn('empleabilidad', self.cliente.portal_productos)

        aliados = crear_aliados_demo(self.cliente, lat_base=4.926, lng_base=-74.173)
        self.assertEqual(len(aliados), 3)
        self.assertEqual(AliadoEmpleabilidad.objects.filter(cliente=self.cliente).count(), 3)

    def test_flujo_simulado_ubicacion_y_codigo(self):
        setup_prueba_empleabilidad(self.cliente, telefono=self.est.telefono)
        msg = simular_ubicacion_whatsapp(self.est, 4.926, -74.173)
        self.est.refresh_from_db()
        self.assertIn('código secreto', msg.lower())
        self.assertEqual(self.est.estado_onboarding, 'esperando_codigo_empleabilidad')
        self.assertEqual(MisionEmpleabilidad.objects.filter(estudiante=self.est).count(), 1)

        ok, detalle = completar_mision_con_codigo(self.est, 'EKI-DEMO-01')
        self.assertTrue(ok, detalle)
        mision = MisionEmpleabilidad.objects.get(estudiante=self.est)
        self.assertEqual(mision.estado, 'completada')
        self.assertTrue(mision.codigo_validado)


@override_settings(SECURE_SSL_REDIRECT=False)
class EmpleabilidadListoBypassWebhookTests(TestCase):
    """Regresión: en radar el código no cae al gate *listo*; en curso normal *listo* sigue."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Emp Webhook',
            contacto_principal='X',
            email='empwh@test.com',
            telefono='573001100010',
            activo=True,
            empleabilidad_exploracion_activa=True,
            portal_productos='empleabilidad',
        )
        self.tel = '573001100088'
        self.est = Estudiante.objects.create(
            cedula='emp88',
            nombre='Joven Webhook',
            telefono=self.tel,
            cliente=self.cliente,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_codigo_empleabilidad',
        )
        self.aliado = AliadoEmpleabilidad.objects.create(
            nombre_empresa='Punto Demo',
            cliente=self.cliente,
            latitud=4.717,
            longitud=-74.031,
            vacantes_activas=True,
            codigo_secreto='EKI-USQ-01',
            indicacion_sector='Av. 9 con 140',
        )
        self.mision = MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=self.est,
            aliado=self.aliado,
            estado='descubierta',
            latitud=4.717,
            longitud=-74.031,
            distancia_metros=40.0,
        )
        self.est.contexto_temporal = {
            'radar_empleabilidad_activo': True,
            'aliado_empleabilidad_objetivo_id': self.aliado.id,
            'mision_empleabilidad_id': self.mision.id,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def _post(self, body, create_mock):
        create_mock.return_value = MagicMock(sid=f'SM_emp_{abs(hash(body)) % 10**8}')

        class FakeTwilioClient:
            def __init__(self, *args, **kwargs):
                self.messages = MagicMock()
                self.messages.create = create_mock

        twilio_ctx = nullcontext()
        try:
            import twilio.rest  # noqa: F401

            twilio_ctx = patch('twilio.rest.Client', FakeTwilioClient)
        except ImportError:
            _install_twilio_rest_stub(FakeTwilioClient)

        with twilio_ctx:
            resp = HttpClient().post(
                '/webhook/whatsapp/',
                {
                    'From': f'whatsapp:+{self.tel}',
                    'To': 'whatsapp:+573202948806',
                    'Body': body,
                    'MessageSid': f'SM_emp_{body[:12].replace(" ", "_")}',
                    'NumMedia': '0',
                },
            )
        return resp

    def test_listo_en_radar_pide_codigo_no_gate_curso(self):
        create_mock = MagicMock()
        resp = self._post('listo', create_mock)
        self.assertEqual(resp.status_code, 200)
        joined = '\n'.join(_bodies_from_twilio_mock(create_mock)).lower()
        self.assertIn('radar de empleabilidad', joined)
        self.assertIn('código secreto', joined)
        self.assertNotIn('no entendí', joined)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_codigo_empleabilidad')

    def test_codigo_secreto_valida_mision(self):
        create_mock = MagicMock()
        resp = self._post('EKI-USQ-01', create_mock)
        self.assertEqual(resp.status_code, 200)
        joined = '\n'.join(_bodies_from_twilio_mock(create_mock)).lower()
        self.assertIn('logro desbloqueado', joined)
        self.mision.refresh_from_db()
        self.assertEqual(self.mision.estado, 'completada')
        self.assertTrue(self.mision.codigo_validado)

    def test_listo_curso_normal_sigue_avanzando(self):
        """Sin estado de radar, *listo* entrega contenido de curso (no mensaje de código)."""
        curso = Curso.objects.create(
            nombre='Curso normal listo',
            activo=True,
            cliente=self.cliente,
            dias_espera_entre_modulos=0,
        )
        m1 = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='Intro',
            descripcion='D',
            contenido='CONTENIDO_CURSO_NORMAL_LISTO',
        )
        Modulo.objects.create(
            curso=curso,
            numero=2,
            titulo='Segunda',
            descripcion='D',
            contenido='CONTENIDO_MOD_2',
        )
        est = Estudiante.objects.create(
            cedula='emp77',
            nombre='Curso Normal',
            telefono='573001100077',
            cliente=self.cliente,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        ProgresoEstudiante.objects.create(
            estudiante=est,
            curso=curso,
            modulo_actual=m1,
            completado=False,
        )
        msg = get_response_for_intent(
            'continuar_leccion',
            est.nombre,
            estudiante_id=est.id,
            mensaje_original='listo',
        )
        self.assertTrue(
            'CONTENIDO_CURSO_NORMAL_LISTO' in msg or 'CONTENIDO_MOD_2' in msg,
            msg,
        )
        self.assertNotIn('radar de empleabilidad', msg.lower())
        self.assertNotIn('código secreto', msg.lower())
