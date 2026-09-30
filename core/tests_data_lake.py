"""Data lake raw: el outbox llega a S3 y un fallo no se marca como publicado."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.event_engine import correr_correlacion_territorial, publicar_evento


@override_settings(
    DATA_LAKE_ENABLED=True,
    AWS_STORAGE_BUCKET_NAME='eki-produccion',
    AWS_S3_BUCKET_NAME='',
    AWS_S3_REGION_NAME='us-east-2',
    DATA_LAKE_S3_PREFIX='',
)
class DataLakeFlushTests(TestCase):
    @patch('boto3.client')
    def test_publicar_escribe_raw_y_marca_publicado(self, client):
        s3 = MagicMock()
        client.return_value = s3
        row = publicar_evento(
            event_type='aprendizaje.listo.recibido',
            payload={'ok': True},
            territory_id='05001',
        )
        row.refresh_from_db()
        self.assertIsNotNone(row.published_at)
        self.assertTrue(row.lake_uri.startswith('s3://eki-produccion/lake/raw/aprendizaje/'))
        kwargs = s3.put_object.call_args.kwargs
        self.assertEqual(kwargs['Bucket'], 'eki-produccion')
        self.assertTrue(kwargs['Key'].startswith('lake/raw/aprendizaje/'))
        self.assertTrue(kwargs['Key'].endswith(f'{row.event_id}.json'))
        self.assertEqual(kwargs['ContentType'], 'application/json')

    @patch('boto3.client')
    def test_fallo_s3_deja_sin_publicar(self, client):
        s3 = MagicMock()
        s3.put_object.side_effect = RuntimeError('denied')
        client.return_value = s3
        row = publicar_evento(
            event_type='aprendizaje.listo.recibido',
            payload={'ok': False},
        )
        row.refresh_from_db()
        self.assertIsNone(row.published_at)
        self.assertFalse(row.lake_uri)

    @override_settings(AWS_STORAGE_BUCKET_NAME='', AWS_S3_BUCKET_NAME='')
    def test_sin_bucket_marca_uri_local(self):
        row = publicar_evento(event_type='system.ping', payload={})
        row.refresh_from_db()
        self.assertTrue(row.lake_uri.startswith('local://lake/raw/system/'))
        self.assertIsNotNone(row.published_at)


@override_settings(DATA_LAKE_ENABLED=True)
class DataLakeCeleryTests(TestCase):
    @patch('core.event_engine.correlacionar_clusters', return_value=[])
    @patch('core.event_engine.flush_outbox_pendientes', return_value=2)
    def test_celery_reintenta_el_lake_si_esta_prendido(self, flush, _clusters):
        out = correr_correlacion_territorial()
        flush.assert_called_once_with(limit=200)
        self.assertEqual(out['lake_flush'], 2)

    @override_settings(DATA_LAKE_ENABLED=False)
    @patch('core.event_engine.correlacionar_clusters', return_value=[])
    @patch('core.event_engine.flush_outbox_pendientes', return_value=9)
    def test_celery_no_flushea_si_esta_apagado(self, flush, _clusters):
        out = correr_correlacion_territorial()
        flush.assert_not_called()
        self.assertEqual(out['lake_flush'], 0)


class DataLakeProdDefaultTests(TestCase):
    def test_produccion_prende_el_lake_si_eb_no_lo_define(self):
        raiz = Path(__file__).resolve().parent.parent
        src = (raiz / 'mvp_project' / 'settings_production.py').read_text(encoding='utf-8')
        self.assertIn("os.environ.get('DATA_LAKE_ENABLED', '').strip() == ''", src)
        self.assertIn('DATA_LAKE_ENABLED = True', src)
