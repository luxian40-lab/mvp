"""El Postgres de prueba no apunta a RDS ni al 5432 de otra app."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from mvp_project.postgres_prueba import host_puerto_postgres_prueba


class PostgresPruebaTests(SimpleTestCase):
    def test_sin_puerto_usa_5433(self):
        host, port = host_puerto_postgres_prueba('localhost', None)
        self.assertEqual(host, 'localhost')
        self.assertEqual(port, '5433')

    def test_ci_puede_pasar_5432(self):
        host, port = host_puerto_postgres_prueba('localhost', '5432')
        self.assertEqual(host, 'localhost')
        self.assertEqual(port, '5432')

    def test_rds_no_arranca(self):
        with self.assertRaises(ImproperlyConfigured):
            host_puerto_postgres_prueba(
                'eki.xxxx.us-east-2.rds.amazonaws.com',
                '5432',
            )
