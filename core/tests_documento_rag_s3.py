"""DocumentoRAG indexación cuando el storage es S3 (sin .path local)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase

from core.models import Curso, DocumentoRAG


class DocumentoRAGIndexarS3Tests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Curso RAG S3')

    def _make_doc(self):
        doc = DocumentoRAG(curso=self.curso, nombre='manual_rag', tipo='contenido', estado='pendiente')
        doc.archivo.save('manual.pdf', ContentFile(b'%PDF-1.4 ' + b'x' * 200), save=True)
        return doc

    def test_indexar_cuando_path_lanza_usa_descarga_temp(self):
        doc = self._make_doc()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        tmp.write(b'%PDF-1.4 texto agricola para indexar ' * 30)
        tmp.close()

        with patch.object(doc, '_descargar_temp', return_value=tmp.name) as mock_dl, patch(
            'core.rag_manager.rag_manager.procesar_documento', return_value=4
        ) as mock_proc, patch.object(
            type(doc.archivo),
            'path',
            property(lambda self: (_ for _ in ()).throw(
                NotImplementedError("This backend doesn't support absolute paths.")
            )),
        ):
            n = doc.indexar()

        self.assertEqual(n, 4)
        mock_dl.assert_called_once()
        mock_proc.assert_called_once()
        doc.refresh_from_db()
        self.assertEqual(doc.estado, 'indexado')
        self.assertEqual(doc.chunks_indexados, 4)
        self.assertFalse(Path(tmp.name).exists(), 'debe borrar el temporal')

    def test_indexar_error_si_no_hay_ruta(self):
        doc = self._make_doc()
        with patch.object(doc, '_descargar_temp', return_value=None), patch.object(
            type(doc.archivo),
            'path',
            property(lambda self: (_ for _ in ()).throw(NotImplementedError('no path'))),
        ):
            n = doc.indexar()
        self.assertEqual(n, 0)
        doc.refresh_from_db()
        self.assertEqual(doc.estado, 'error')


class CrearDocumentoCursoUnicoTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Curso upload')

    @patch('portal.rag_curso_service.encolar_indexacion_rag_curso')
    def test_reupload_mismo_nombre_no_rompe(self, _encolar):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from portal.rag_curso_service import crear_documento_curso

        f1 = SimpleUploadedFile('Rentabilidad.pdf', b'%PDF-1.4 aaa', content_type='application/pdf')
        f2 = SimpleUploadedFile('Rentabilidad.pdf', b'%PDF-1.4 bbb', content_type='application/pdf')
        d1 = crear_documento_curso(self.curso, nombre='Rentabilidad', tipo='contenido', archivo=f1)
        d2 = crear_documento_curso(self.curso, nombre='Rentabilidad', tipo='contenido', archivo=f2)
        self.assertEqual(d1.nombre, 'rentabilidad')
        self.assertNotEqual(d1.nombre, d2.nombre)
        self.assertTrue(d2.nombre.startswith('rentabilidad'))

    @patch('portal.rag_curso_service.encolar_indexacion_rag_curso')
    def test_pptx_rechazado_con_mensaje_claro(self, _encolar):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from portal.rag_curso_service import crear_documento_curso

        f = SimpleUploadedFile('deck.pptx', b'PK fake', content_type='application/vnd.ms-powerpoint')
        with self.assertRaises(ValueError) as ctx:
            crear_documento_curso(self.curso, nombre='deck', tipo='contenido', archivo=f)
        self.assertIn('PowerPoint', str(ctx.exception))
