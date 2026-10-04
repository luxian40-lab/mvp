"""Límites del código de aula.

En CI el cliente es Redis real (redis:7, base 15). Sin daemon local, un
sustituto con INCR/TTL. En CI ese sustituto está prohibido.
"""
import os
import uuid
import warnings
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase, override_settings

from aprende.models import CodigoAccesoAprende
from core.models import Estudiante


class _RedisMem:
    def __init__(self):
        self.data = {}
        self.vida = {}

    def incr(self, clave):
        self.data[clave] = int(self.data.get(clave) or 0) + 1
        return self.data[clave]

    def expire(self, clave, segundos):
        self.vida[clave] = int(segundos)
        return True

    def ttl(self, clave):
        return self.vida.get(clave, -1)

    def get(self, clave):
        valor = self.data.get(clave)
        if valor is None:
            return None
        if isinstance(valor, bytes):
            return valor
        return str(valor).encode()

    def set(self, clave, valor, ex=None):
        self.data[clave] = valor
        if ex:
            self.vida[clave] = int(ex)
        return True

    def delete(self, clave):
        self.data.pop(clave, None)
        self.vida.pop(clave, None)
        return 1


def url_redis_pruebas() -> str:
    """Siempre la base 15. Un REDIS_URL de broker (db 0) no se vacía aquí."""
    from django.conf import settings

    url = str(getattr(settings, 'REDIS_URL', '') or '').strip()
    if url.rstrip('/').endswith('/15'):
        return url
    return 'redis://127.0.0.1:6379/15'


def redis_de_test():
    try:
        from redis import Redis

        cliente = Redis.from_url(url_redis_pruebas(), socket_connect_timeout=0.3)
        cliente.ping()
        return cliente
    except Exception as exc:
        if os.environ.get('CI'):
            raise
        warnings.warn(
            f'Redis de prueba no responde ({exc}); se usa memoria',
            stacklevel=2,
        )
        return _RedisMem()


def _prefijo():
    return f'eki:aula:t{uuid.uuid4().hex[:8]}'


class _Base(TestCase):
    def setUp(self):
        self.http = Client()
        self.est = Estudiante.objects.create(
            cedula='999000111',
            nombre='Ana',
            telefono='573000000111',
            activo=True,
        )
        self.prefijo = _prefijo()
        self.redis = redis_de_test()
        self._patch = patch('core.locks._cliente_redis', return_value=self.redis)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def _codigo(self, valor='123456'):
        CodigoAccesoAprende.objects.filter(estudiante=self.est).delete()
        return CodigoAccesoAprende.objects.create(codigo=valor, estudiante=self.est)


@override_settings(SECURE_SSL_REDIRECT=False, AULA_LOGIN_MAX_GLOBAL=500)
class AulaRateTests(_Base):
    def test_cinco_fallos_queman_el_codigo(self):
        self._codigo('654321')
        with override_settings(
            AULA_LOGIN_REQUIERE_DOCUMENTO=True,
            AULA_LOGIN_MAX_POR_ESTUDIANTE=5,
            AULA_LOGIN_MAX_POR_IP=50,
            AULA_LOGIN_PREFIJO=self.prefijo,
        ):
            frase = 'Código inválido o vencido'
            for _ in range(5):
                r = self.http.post('/aprende/estudiante/login/', {
                    'codigo': '000000',
                    'documento': '999000111',
                    'accion': 'codigo',
                })
                self.assertIn(frase, r.content.decode())
        self.assertFalse(CodigoAccesoAprende.objects.filter(estudiante=self.est).exists())

    def test_once_desde_una_ip_bloquea_sin_gastar_el_codigo(self):
        row = self._codigo('111222')
        with override_settings(
            AULA_LOGIN_MAX_POR_IP=10,
            AULA_LOGIN_PREFIJO=self.prefijo,
        ):
            for _ in range(10):
                self.http.post('/aprende/estudiante/login/', {'codigo': '000000', 'accion': 'codigo'})
            bloqueado = self.http.post('/aprende/estudiante/login/', {
                'codigo': '111222',
                'accion': 'codigo',
            })
        self.assertEqual(bloqueado.status_code, 200)
        self.assertTrue(CodigoAccesoAprende.objects.filter(pk=row.pk).exists())

    def test_exito_resetea_estudiante_y_no_la_ip(self):
        from core.locks import _cliente_redis, telefono_hash

        self._codigo('333444')
        with override_settings(
            AULA_LOGIN_REQUIERE_DOCUMENTO=True,
            AULA_LOGIN_MAX_POR_ESTUDIANTE=5,
            AULA_LOGIN_MAX_POR_IP=20,
            AULA_LOGIN_PREFIJO=self.prefijo,
        ):
            self.http.post('/aprende/estudiante/login/', {
                'codigo': '000000',
                'documento': '999000111',
                'accion': 'codigo',
            })
            ok = self.http.post('/aprende/estudiante/login/', {
                'codigo': '333444',
                'documento': '999000111',
                'accion': 'codigo',
            })
        self.assertEqual(ok.status_code, 302)
        cliente = _cliente_redis()
        est = telefono_hash(str(self.est.pk))
        self.assertIsNone(cliente.get(f'{self.prefijo}:est:{est}'))
        ip = telefono_hash('127.0.0.1')
        self.assertIsNotNone(cliente.get(f'{self.prefijo}:ip:{ip}'))

    def test_codigo_de_un_solo_uso_y_mensajes_iguales(self):
        self._codigo('555666')
        with override_settings(AULA_LOGIN_PREFIJO=self.prefijo, AULA_LOGIN_MAX_POR_IP=20):
            primero = self.http.post('/aprende/estudiante/login/', {
                'codigo': '555666',
                'accion': 'codigo',
            })
            segundo = self.http.post('/aprende/estudiante/login/', {
                'codigo': '555666',
                'accion': 'codigo',
            })
            inexistente = self.http.post('/aprende/estudiante/login/', {
                'codigo': '000000',
                'accion': 'codigo',
            })
        self.assertEqual(primero.status_code, 302)
        frase = 'Código inválido o vencido'
        self.assertIn(frase, segundo.content.decode())
        self.assertIn(frase, inexistente.content.decode())

    def test_modo_estricto_global(self):
        self._codigo('777888')
        with override_settings(
            AULA_LOGIN_MAX_GLOBAL=2,
            AULA_LOGIN_MAX_POR_IP=100,
            AULA_LOGIN_PREFIJO=self.prefijo,
        ), self.assertLogs('aprende.acceso_whatsapp', level='WARNING') as logs:
            for _ in range(3):
                self.http.post('/aprende/estudiante/login/', {'codigo': '000000', 'accion': 'codigo'})
            cuarto = self.http.post('/aprende/estudiante/login/', {
                'codigo': '777888',
                'accion': 'codigo',
            })
        self.assertTrue(any('aula_login_ataque_probable' in linea for linea in logs.output))
        self.assertEqual(cuarto.status_code, 200)
        self.assertTrue(CodigoAccesoAprende.objects.filter(codigo='777888').exists())

    def test_redis_caido_rechaza(self):
        self._codigo('121212')
        with override_settings(AULA_LOGIN_PREFIJO=self.prefijo), \
                patch('core.locks._cliente_redis', side_effect=ConnectionError('redis')), \
                self.assertLogs('core.rate_limit', level='ERROR') as logs:
            r = self.http.post('/aprende/estudiante/login/', {
                'codigo': '121212',
                'accion': 'codigo',
            })
        self.assertEqual(r.status_code, 200)
        self.assertIn('inválido', r.content.decode())
        self.assertTrue(CodigoAccesoAprende.objects.filter(codigo='121212').exists())
        self.assertTrue(any('rate_limit_redis_caido' in linea for linea in logs.output))


class RedisDeTestTests(SimpleTestCase):
    def test_ci_sin_redis_no_usa_memoria(self):
        with patch.dict(os.environ, {'CI': 'true'}):
            with patch('redis.Redis.from_url', side_effect=ConnectionError('no')):
                with self.assertRaises(ConnectionError):
                    redis_de_test()
