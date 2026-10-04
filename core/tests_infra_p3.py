"""Roles, colas y migrate con candado. No abre Redis ni Postgres."""
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase


class ColasYRolTests(SimpleTestCase):
    def test_webhooks_van_a_conversacion_y_campanas_a_masivo(self):
        routes = settings.CELERY_TASK_ROUTES
        for nombre in (
            'core.tasks.procesar_sandbox_meta_async',
            'core.tasks.procesar_twilio_webhook_async',
            'core.tasks.procesar_bot_comercial_webhook_async',
        ):
            self.assertEqual(routes[nombre]['queue'], 'conversacion')
        for nombre in (
            'core.tasks.enviar_campanas_programadas',
            'core.tasks.ejecutar_campana_async',
            'core.tasks.ejecutar_campana_meta_async',
            'core.tasks.reenganche_drip_content_diario',
            'core.tasks.generar_reporte_actividad',
        ):
            self.assertEqual(routes[nombre]['queue'], 'masivo')
        self.assertEqual(routes['core.tasks.encode_paso_modulo_media']['queue'], 'media_encode')
        self.assertIn('audio', settings.CELERY_TASK_QUEUES)
        self.assertIn('conversacion', settings.CELERY_TASK_QUEUES)

    def test_run_worker_default_es_prefork_1_y_lee_celery_queues(self):
        texto = Path('scripts/run_worker.sh').read_text(encoding='utf-8')
        self.assertIn('CELERY_POOL:-prefork', texto)
        self.assertIn('CELERY_CONCURRENCY:-1', texto)
        self.assertIn('CELERY_QUEUES:-conversacion,masivo,celery,media_encode', texto)
        self.assertNotIn('--pool="$POOL"', texto)
        self.assertIn('--pool=threads', texto)
        self.assertIn('prefork|threads', texto)
        self.assertEqual(
            settings.CELERY_BROKER_TRANSPORT_OPTIONS['visibility_timeout'],
            600,
        )

    def test_toda_ruta_y_la_cola_de_beat_tienen_consumidor(self):
        import re

        worker = Path('scripts/run_worker.sh').read_text(encoding='utf-8')
        rag = Path('scripts/run_worker_rag.sh').read_text(encoding='utf-8')
        defecto_worker = re.search(r'CELERY_QUEUES:-([^}"\s]+)', worker).group(1)
        defecto_rag = re.search(r'CELERY_QUEUES_RAG:-([^}"\s]+)', rag).group(1)
        escuchadas = set(defecto_worker.split(',')) | set(defecto_rag.split(','))
        for nombre, spec in settings.CELERY_TASK_ROUTES.items():
            self.assertIn(spec['queue'], escuchadas, nombre)
        # Course Engine en prod se genera por CLI, no por esta cola.
        # docs/COURSE_ENGINE_LOCAL.md (2026-08-29): el botón admin + Celery
        # queda como slice futuro. generar_video_course_engine_async declara
        # queue='course_engine' y ningún worker la consume. No se enruta.
        self.assertNotIn(
            'core.tasks.generar_video_course_engine_async',
            settings.CELERY_TASK_ROUTES,
        )
        # Beat no fija cola: publica en la cola por defecto de Celery.
        self.assertIn('celery', escuchadas)

    def test_beat_corre_en_all_y_en_worker_solo_con_run_beat(self):
        texto = Path('scripts/run_beat.sh').read_text(encoding='utf-8')
        self.assertIn('EKI_ROLE:-all', texto)
        self.assertIn('RUN_BEAT:-0', texto)
        self.assertIn('sleep infinity', texto)


class MigrateLockedTests(SimpleTestCase):
    def test_sin_postgres_no_pide_advisory_lock(self):
        from django.db import connections

        from core.management.commands.migrate_locked import Command

        envoltura = connections['default']
        with patch.object(envoltura, 'vendor', 'sqlite'), \
                patch('django.core.management.call_command') as migrate:
            Command().handle()
        migrate.assert_called_once_with('migrate', interactive=False)

    def test_en_postgres_el_candado_va_en_la_misma_conexion(self):
        from core.management.commands.migrate_locked import migrate_con_candado

        sentencias = []
        corridas = []

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                sentencias.append((sql, params))

        class _Conexion:
            vendor = 'postgresql'

            def __init__(self):
                self.ensure_calls = 0

            def ensure_connection(self):
                self.ensure_calls += 1

            def cursor(self):
                return _Cursor()

            def close(self):
                raise AssertionError('close no debe correr con el candado tomado')

        conexion = _Conexion()
        migrate_con_candado(conexion, lambda: corridas.append('migrate'))
        self.assertEqual(corridas, ['migrate'])
        self.assertEqual(conexion.ensure_calls, 1)
        self.assertEqual(sentencias[0], ('SELECT pg_advisory_lock(%s)', [727274]))
        self.assertEqual(sentencias[1], ('SELECT pg_advisory_unlock(%s)', [727274]))
        with self.assertRaises(AssertionError):
            conexion.close()

    def test_close_se_restaura_si_migrate_falla(self):
        from core.management.commands.migrate_locked import migrate_con_candado

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                return None

        class _Conexion:
            vendor = 'postgresql'

            def __init__(self):
                self.cierres = 0

            def ensure_connection(self):
                return None

            def cursor(self):
                return _Cursor()

            def close(self):
                self.cierres += 1

        conexion = _Conexion()
        with self.assertRaises(RuntimeError):
            migrate_con_candado(conexion, lambda: (_ for _ in ()).throw(RuntimeError('migrate')))
        conexion.close()
        self.assertEqual(conexion.cierres, 1)


class MigrateLockedPostgresTests(TransactionTestCase):
    def test_segunda_conexion_no_toma_el_candado_mientras_corre(self):
        from django.db import connection, connections

        from core.management.commands.migrate_locked import migrate_con_candado

        if connection.vendor != 'postgresql':
            self.skipTest('carrera requiere Postgres')

        otra = connections.create_connection('default')
        otra.ensure_connection()
        visto = {}

        def correr():
            with otra.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [727274])
                visto['durante'] = cursor.fetchone()[0]

        try:
            migrate_con_candado(connection, correr)
            self.assertFalse(visto['durante'])
            with otra.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [727274])
                despues = cursor.fetchone()[0]
                self.assertTrue(despues)
                if despues:
                    cursor.execute('SELECT pg_advisory_unlock(%s)', [727274])
        finally:
            otra.close()
