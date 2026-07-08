"""Tests extracción PDF para RAG."""

from unittest.mock import patch

from django.test import SimpleTestCase

from core.extractores_documento import extraer_texto_pdf


class ExtractoresPdfTests(SimpleTestCase):
    @patch('core.extractores_documento._extraer_pymupdf', return_value='Texto agrícola suficientemente largo para indexar en Nat.')
    @patch('core.extractores_documento._extraer_pypdf2', return_value='')
    @patch('core.extractores_documento._ocr_disponible', return_value=False)
    def test_pymupdf_prioritario(self, *_mocks):
        texto, metodo = extraer_texto_pdf('/tmp/fake.pdf')
        self.assertIn('agrícola', texto)
        self.assertEqual(metodo, 'pymupdf')

    @patch('core.extractores_documento._extraer_pymupdf', return_value='')
    @patch('core.extractores_documento._extraer_pypdf2', return_value='Contenido cartilla técnica con más de cuarenta caracteres.')
    @patch('core.extractores_documento._ocr_disponible', return_value=False)
    def test_fallback_pypdf2(self, *_mocks):
        texto, metodo = extraer_texto_pdf('/tmp/fake.pdf')
        self.assertIn('cartilla', texto)
        self.assertEqual(metodo, 'pypdf2')
