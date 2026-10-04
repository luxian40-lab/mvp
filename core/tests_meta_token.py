"""El error 190 para envíos y guarda el código sin escribir el token."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.meta_token import CLAVE_TOKEN_INVALIDO, es_token_invalido
from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante
from core.tasks import reenganche_drip_content_diario
from datetime import timedelta
from django.utils import timezone


class _Redis:
    def __init__(self):
        self.datos = {}

    def set(self, clave, valor, ex=None):
        self.datos[clave] = valor

    def get(self, clave):
        return self.datos.get(clave)

    def delete(self, clave):
        self.datos.pop(clave, None)


def _respuesta(code, tipo='OAuthException', message='expired'):
    resp = MagicMock()
    resp.status_code = 401
    resp.json.return_value = {'error': {'code': code, 'type': tipo, 'message': message}}
    resp.text = ''
    return resp


@override_settings(
    WHATSAPP_TOKEN='TOKEN-NO-DEBE-SALIR',
    WHATSAPP_PHONE_ID='111',
    SANDBOX_WHATSAPP_PHONE_ID='111',
    META_REENGANCHE_ENABLED=True,
    META_TEMPLATE_DRIP_REENGANCHE='',
    WA_VENTANA_HORAS=23,
)
class MetaTokenTests(TestCase):
    def test_190_activa_bandera_y_el_reenganche_no_envia(self):
        from core.sandbox_canal import _post_graph

        redis = _Redis()
        curso = Curso.objects.create(nombre='C', descripcion='d', dias_espera_entre_modulos=2)
        actual = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c', duracion_dias=1,
        )
        Modulo.objects.create(
            curso=curso, numero=2, titulo='M2', descripcion='d', contenido='c', duracion_dias=1,
        )
        est = Estudiante.objects.create(cedula='CC190', nombre='Ana', telefono='573001110190')
        ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, modulo_actual=actual,
            fecha_ultimo_avance=timezone.now() - timedelta(days=2),
        )
        with patch('core.locks._cliente_redis', return_value=redis), \
                patch('core.sandbox_canal.requests.post', return_value=_respuesta(190)), \
                self.assertLogs('core.meta_token', level='CRITICAL') as logs, \
                patch('core.sandbox_canal.enviar_meta') as envio:
            _post_graph({
                'messaging_product': 'whatsapp',
                'to': '573001110190',
                'type': 'text',
                'text': {'body': 'hola'},
            })
            resultado = reenganche_drip_content_diario()
        self.assertEqual(redis.datos.get(CLAVE_TOKEN_INVALIDO), '1')
        self.assertEqual(resultado['omitidos_token'], 1)
        self.assertEqual(resultado['enviados'], 0)
        envio.assert_not_called()
        from core.models import WhatsappLog
        log = WhatsappLog.objects.filter(tipo='SENT').order_by('-id').first()
        self.assertEqual(log.error_codigo, '190')
        self.assertIn('expired', log.error_detalle)
        capturado = '\n'.join(logs.output)
        self.assertNotIn('TOKEN-NO-DEBE-SALIR', capturado)
        self.assertIn('meta_token_invalido', capturado)

    def test_otro_codigo_no_activa_la_bandera(self):
        from core.sandbox_canal import _post_graph

        redis = _Redis()
        with patch('core.locks._cliente_redis', return_value=redis), \
                patch('core.sandbox_canal.requests.post', return_value=_respuesta(131026, 'GraphMethodException', 'undeliverable')):
            _post_graph({
                'messaging_product': 'whatsapp',
                'to': '573001110191',
                'type': 'text',
                'text': {'body': 'hola'},
            })
        self.assertNotIn(CLAVE_TOKEN_INVALIDO, redis.datos)
        self.assertFalse(es_token_invalido({'code': 131026, 'type': 'OAuthException', 'message': 'undeliverable'}))


class MetaTokenResetTests(TestCase):
    def test_comando_borra_la_bandera(self):
        from io import StringIO

        from django.core.management import call_command

        redis = _Redis()
        redis.datos[CLAVE_TOKEN_INVALIDO] = '1'
        out = StringIO()
        with patch('core.locks._cliente_redis', return_value=redis):
            call_command('meta_token_reset', stdout=out)
        self.assertNotIn(CLAVE_TOKEN_INVALIDO, redis.datos)
        self.assertIn('borrada', out.getvalue())
