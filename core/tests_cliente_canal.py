"""B1: twilio.rest.Client se decide por canal en un solo punto."""
import threading
from unittest.mock import patch

import twilio.rest as twilio_rest
from django.test import SimpleTestCase, override_settings

from core.lineas import cliente_canal
from core.lineas.cliente_canal import ClienteCanal, capa_cliente, instalar


class _Base:
    def __init__(self, *args, **kwargs):
        self.origen = 'base'


class _Otro:
    def __init__(self, *args, **kwargs):
        self.origen = 'otro'


def _marca(nombre):
    def envolver(base):
        def construir(*args, **kwargs):
            cliente = base(*args, **kwargs)
            cliente.origen = f'{nombre}({cliente.origen})'
            return cliente
        return construir
    return envolver


class CapaClienteTests(SimpleTestCase):
    def setUp(self):
        patcher = patch.object(twilio_rest, 'Client', _Base)
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=False)
    def test_modo_viejo_cambia_el_atributo_y_lo_restaura(self):
        with capa_cliente('meta', lambda _base: _Otro):
            self.assertIs(twilio_rest.Client, _Otro)
            self.assertEqual(twilio_rest.Client().origen, 'otro')
        self.assertIs(twilio_rest.Client, _Base)

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True)
    def test_modo_permanente_instala_una_vez_y_decide_por_turno(self):
        with capa_cliente('meta', lambda _base: _Otro):
            self.assertIs(twilio_rest.Client, ClienteCanal)
            self.assertEqual(twilio_rest.Client().origen, 'otro')
        self.assertIs(twilio_rest.Client, ClienteCanal)
        self.assertEqual(twilio_rest.Client().origen, 'base')
        instalar()
        self.assertIs(cliente_canal._original, _Base)

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True)
    def test_capas_anidadas_se_aplican_en_orden(self):
        with capa_cliente('a', _marca('a')), capa_cliente('b', _marca('b')):
            self.assertEqual(twilio_rest.Client().origen, 'b(a(base))')

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=False)
    def test_capas_anidadas_en_modo_viejo_dan_lo_mismo(self):
        with capa_cliente('a', _marca('a')), capa_cliente('b', _marca('b')):
            self.assertEqual(twilio_rest.Client().origen, 'b(a(base))')

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True)
    def test_la_misma_clave_no_se_aplica_dos_veces(self):
        with capa_cliente('a', _marca('a')), capa_cliente('a', _marca('a')):
            self.assertEqual(twilio_rest.Client().origen, 'a(base)')

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True)
    def test_dos_hilos_con_canales_distintos_no_se_pisan(self):
        instalar()
        barrera = threading.Barrier(2)
        vistos = {}

        def turno(nombre, envolver):
            with capa_cliente(nombre, envolver):
                barrera.wait(timeout=5)
                vistos[nombre] = twilio_rest.Client().origen
                barrera.wait(timeout=5)

        hilos = [
            threading.Thread(target=turno, args=('meta', lambda _base: _Otro)),
            threading.Thread(target=turno, args=('boton', _marca('boton'))),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=10)
        self.assertEqual(vistos, {'meta': 'otro', 'boton': 'boton(base)'})


class CanalesRealesTests(SimpleTestCase):
    def setUp(self):
        patcher = patch.object(twilio_rest, 'Client', _Base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _por_meta(self):
        from core.sandbox_canal import canal_sandbox_meta

        with patch('core.sandbox_canal.enviar_meta', return_value={'success': True, 'mensaje_id': 'wamid.x'}) as meta:
            with canal_sandbox_meta():
                from twilio.rest import Client

                sid = Client('ac', 'tok').messages.create(to='whatsapp:+573001110080', body='Hola')
        return meta, sid

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=False, SANDBOX_PROVEEDOR='meta')
    def test_sandbox_meta_sale_por_graph_en_modo_viejo(self):
        meta, sid = self._por_meta()
        meta.assert_called_once_with('whatsapp:+573001110080', 'Hola', media_url=None)
        self.assertEqual(sid.sid, 'wamid.x')

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True, SANDBOX_PROVEEDOR='meta')
    def test_sandbox_meta_sale_por_graph_en_modo_permanente(self):
        meta, sid = self._por_meta()
        meta.assert_called_once_with('whatsapp:+573001110080', 'Hola', media_url=None)
        self.assertEqual(sid.sid, 'wamid.x')

    def _boton(self):
        from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS
        from core.views.twilio_transporte import interceptar_envio_boton_twilio

        enviados = []

        class _Registro:
            def __init__(self, *args, **kwargs):
                self.messages = self

            def create(self, **params):
                enviados.append(params)

        twilio_rest.Client = _Registro
        with patch('core.whatsapp_service.enviar_template_twilio', return_value={'mensaje_id': 'HXok'}) as plantilla:
            with interceptar_envio_boton_twilio():
                from twilio.rest import Client

                sid = Client().messages.create(to='whatsapp:+57300', body=f'Listo {MARCADOR_BOTON_CONTINUEMOS}')
        return enviados, plantilla, sid

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=False)
    def test_boton_continuemos_en_modo_viejo(self):
        enviados, plantilla, sid = self._boton()
        self.assertEqual(enviados[0]['body'], 'Listo')
        plantilla.assert_called_once()
        self.assertEqual(sid.sid, 'HXok')

    @override_settings(EKI_CLIENTE_CANAL_PERMANENTE=True)
    def test_boton_continuemos_en_modo_permanente(self):
        enviados, plantilla, sid = self._boton()
        self.assertEqual(enviados[0]['body'], 'Listo')
        plantilla.assert_called_once()
        self.assertEqual(sid.sid, 'HXok')
