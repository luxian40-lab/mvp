"""Tests documento de identidad LatAm + teléfono multi-país."""

from django.test import TestCase

from core.documento_identidad import (
    normalizar_numero_documento,
    normalizar_tipo_documento,
)
from core.form_externo_service import _buscar_por_cedula
from core.models import Cliente, Estudiante
from core.utils_telefono import normalizar_telefono


class DocumentoIdentidadTests(TestCase):
    def test_tipos_latam(self):
        self.assertEqual(normalizar_tipo_documento('dui'), 'DUI')
        self.assertEqual(normalizar_tipo_documento('CURP'), 'CURP')
        self.assertEqual(normalizar_tipo_documento('credencial'), 'INE')
        self.assertEqual(normalizar_tipo_documento('cédula'), 'CC')

    def test_numero_alfanumerico_curp(self):
        self.assertEqual(
            normalizar_numero_documento('pegj850101hdfrrn09'),
            'PEGJ850101HDFRRN09',
        )
        self.assertEqual(normalizar_numero_documento('12.345.678-9'), '123456789')

    def test_estudiante_guarda_dui_y_curp(self):
        org = Cliente.objects.create(
            nombre='Org LatAm',
            contacto_principal='A',
            email='latam@test.com',
            telefono='573001111111',
            activo=True,
        )
        sv = Estudiante.objects.create(
            tipo_documento='DUI',
            cedula='01234567-8',
            nombre='Ana SV',
            telefono='50371234567',
            cliente=org,
        )
        mx = Estudiante.objects.create(
            tipo_documento='CURP',
            cedula='PEGJ850101HDFRRN09',
            nombre='Jose MX',
            telefono='5215512345678',
            cliente=org,
        )
        sv.refresh_from_db()
        mx.refresh_from_db()
        self.assertEqual(sv.tipo_documento, 'DUI')
        self.assertEqual(sv.cedula, '012345678')
        self.assertEqual(sv.telefono, '50371234567')
        self.assertEqual(mx.tipo_documento, 'CURP')
        self.assertEqual(mx.cedula, 'PEGJ850101HDFRRN09')
        self.assertEqual(mx.telefono, '5215512345678')
        self.assertIn('DUI', str(sv))

    def test_telefono_no_fuerza_57_en_mexico(self):
        self.assertEqual(normalizar_telefono('5215512345678'), '5215512345678')
        self.assertEqual(normalizar_telefono('50371234567'), '50371234567')
        self.assertEqual(normalizar_telefono('3001234567'), '573001234567')

    def test_buscar_form_externo_curp(self):
        org = Cliente.objects.create(
            nombre='Org Form',
            contacto_principal='A',
            email='f2@test.com',
            telefono='573002222222',
            activo=True,
        )
        Estudiante.objects.create(
            tipo_documento='CURP',
            cedula='ABCD900101MDFRRN01',
            nombre='Maria',
            telefono='5215598765432',
            cliente=org,
        )
        qs = Estudiante.objects.filter(cliente=org)
        est = _buscar_por_cedula(qs, 'abcd-900101-mdfrrn01')
        self.assertIsNotNone(est)
        self.assertEqual(est.cedula, 'ABCD900101MDFRRN01')
