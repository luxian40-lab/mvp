from unittest.mock import patch

from django.test import TestCase

from core import rag_manager as rag_manager_mod
from core.rag_manager import RAGManager, _pista_permisos


class PistaPermisosChromaTests(TestCase):
    """'attempt to write a readonly database' = CHROMA_DB_DIR no escribible por el usuario."""

    def test_error_de_permisos_explica_causa_y_salida(self):
        pista = _pista_permisos(Exception('attempt to write a readonly database'))

        self.assertIn('CHROMA_DB_DIR', pista)
        self.assertIn('sudo -u webapp', pista)

    def test_otros_errores_no_reciben_pista_enganosa(self):
        self.assertEqual(_pista_permisos(Exception('connection refused')), '')

    def test_el_log_de_instancia_fallida_incluye_la_pista(self):
        manager = RAGManager()

        with patch.object(rag_manager_mod, '_CHROMADB_OK', True), patch.object(
            rag_manager_mod,
            'RAGClienteCurso',
            side_effect=Exception('attempt to write a readonly database'),
        ):
            with self.assertLogs('core.rag_manager', level='ERROR') as logs:
                self.assertIsNone(manager.obtener_rag(cliente_id=1, curso_id=35))

        self.assertIn('sudo -u webapp', '\n'.join(logs.output))
