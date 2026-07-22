"""Regresión: Redis/Celery/Chroma no se rompen sin ElastiCache."""

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from mvp_project.infra_redis import (
    LOCAL_REDIS_URL,
    env_truthy_local_redis,
    is_external_redis_url,
    resolve_eb_celery_redis,
)


class InfraRedisResolveTests(SimpleTestCase):
    """Comportamiento histórico EB = Redis local si no hay broker externo."""

    def test_sin_env_en_eb_usa_local(self):
        broker, backend, mode = resolve_eb_celery_redis(
            broker_env='',
            use_local_redis=True,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'local')
        self.assertEqual(broker, LOCAL_REDIS_URL)
        self.assertEqual(backend, LOCAL_REDIS_URL)

    def test_use_local_0_sin_broker_no_deja_vacio(self):
        """Misconfiguración: no romper Celery; fallback local."""
        broker, backend, mode = resolve_eb_celery_redis(
            broker_env='',
            use_local_redis=False,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'local')
        self.assertEqual(broker, LOCAL_REDIS_URL)
        self.assertTrue(backend)

    def test_elasticache_externo(self):
        url = 'redis://my-cache.xxx.cache.amazonaws.com:6379/0'
        broker, backend, mode = resolve_eb_celery_redis(
            broker_env=url,
            result_backend_env='',
            use_local_redis=False,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'external')
        self.assertEqual(broker, url)
        self.assertEqual(backend, url)

    def test_rediss_tls_cuenta_como_externo(self):
        url = 'rediss://my-cache.xxx.cache.amazonaws.com:6379/0'
        broker, _, mode = resolve_eb_celery_redis(
            broker_env=url,
            use_local_redis=False,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'external')
        self.assertEqual(broker, url)

    def test_localhost_explicito_es_local(self):
        url = 'redis://127.0.0.1:6379/0'
        _, _, mode = resolve_eb_celery_redis(
            broker_env=url,
            use_local_redis=True,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'local')

    def test_fuera_de_eb_no_sobrescribe(self):
        broker, backend, mode = resolve_eb_celery_redis(
            broker_env='redis://external:6379/0',
            on_elastic_beanstalk=False,
        )
        self.assertEqual(mode, 'unchanged')
        self.assertEqual(broker, '')
        self.assertEqual(backend, '')

    def test_backend_custom_se_respeta(self):
        broker_url = 'redis://cache.example:6379/0'
        backend_url = 'redis://cache.example:6379/1'
        broker, backend, mode = resolve_eb_celery_redis(
            broker_env=broker_url,
            result_backend_env=backend_url,
            on_elastic_beanstalk=True,
        )
        self.assertEqual(mode, 'external')
        self.assertEqual(broker, broker_url)
        self.assertEqual(backend, backend_url)

    def test_env_truthy_local_defaults(self):
        self.assertTrue(env_truthy_local_redis(None))
        self.assertTrue(env_truthy_local_redis('1'))
        self.assertFalse(env_truthy_local_redis('0'))
        self.assertFalse(env_truthy_local_redis('false'))

    def test_is_external_helpers(self):
        self.assertFalse(is_external_redis_url(''))
        self.assertFalse(is_external_redis_url('redis://127.0.0.1:6379/0'))
        self.assertFalse(is_external_redis_url('redis://localhost:6379/0'))
        self.assertTrue(is_external_redis_url('redis://foo.cache.amazonaws.com:6379/0'))
        self.assertTrue(is_external_redis_url('rediss://foo:6379/0'))


class InfraSettingsSmokeTests(SimpleTestCase):
    """Settings cargados en test no deben quedar rotos."""

    def test_celery_broker_definido(self):
        self.assertTrue(getattr(settings, 'CELERY_BROKER_URL', ''))
        self.assertTrue(getattr(settings, 'CELERY_RESULT_BACKEND', ''))

    def test_colas_celery_intactas(self):
        queues = getattr(settings, 'CELERY_TASK_QUEUES', {})
        self.assertIn('celery', queues)
        self.assertIn('rag_index', queues)

    def test_chroma_dir_definido(self):
        chroma = getattr(settings, 'CHROMA_DB_DIR', '')
        self.assertTrue(chroma)

    @override_settings(CHROMA_DB_DIR='/tmp/eki_chroma_test')
    def test_chroma_override_settings(self):
        self.assertEqual(settings.CHROMA_DB_DIR, '/tmp/eki_chroma_test')
