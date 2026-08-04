"""Tests territorio canónico DIVIPOLA + inventario de señales."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import Cliente, Estudiante
from core.territorio import aplicar_territorio_estudiante, resolver_territorio
from portal.geo_catalogo import _divipola_por_clave, resolver_ubicacion


class TerritorioDivipolaTests(TestCase):
    def test_catalogo_divipola_cargado(self):
        cat = _divipola_por_clave()
        self.assertGreaterEqual(len(cat), 1100)
        self.assertEqual(cat['MEDELLIN|ANTIOQUIA']['codigo'], '05001')

    def test_resolver_territory_id_medellin(self):
        ubic = resolver_territorio('Medellín', 'Antioquia')
        self.assertEqual(ubic.nivel, 'municipio')
        self.assertEqual(ubic.territory_id, '05001')
        self.assertGreaterEqual(ubic.confianza, 0.9)

    def test_resolver_bogota_divipola(self):
        ubic = resolver_ubicacion('Bogotá', 'Cundinamarca')
        self.assertEqual(ubic.territory_id, '11001')

    def test_aplicar_territory_id_en_estudiante(self):
        org = Cliente.objects.create(
            nombre='Org Tid',
            contacto_principal='A',
            email='tid@test.com',
            telefono='3001110001',
        )
        est = Estudiante.objects.create(
            cliente=org,
            nombre='Ana',
            cedula='tid1',
            telefono='573001110001',
            municipio='Medellín',
            departamento='Antioquia',
        )
        aplicar_territorio_estudiante(est, save=True)
        est.refresh_from_db()
        self.assertEqual(est.territory_id, '05001')
        self.assertEqual(est.municipio, 'Medellin')

    def test_inventario_comando(self):
        org = Cliente.objects.create(
            nombre='Org Inv',
            contacto_principal='A',
            email='inv@test.com',
            telefono='3001110002',
        )
        Estudiante.objects.create(
            cliente=org,
            nombre='Bo',
            cedula='inv1',
            telefono='573001110002',
            municipio='Cali',
            departamento='Valle del Cauca',
        )
        out = StringIO()
        call_command('inventario_senales_territoriales', stdout=out)
        text = out.getvalue()
        self.assertIn('Inventario señales territoriales', text)
        self.assertIn('DIVIPOLA', text)
        self.assertIn('Estudiantes total', text)

    def test_normalizar_escribe_territory_id(self):
        org = Cliente.objects.create(
            nombre='Org Norm',
            contacto_principal='A',
            email='norm@test.com',
            telefono='3001110003',
        )
        est = Estudiante.objects.create(
            cliente=org,
            nombre='Ce',
            cedula='norm1',
            telefono='573001110003',
            municipio='Medelin',
            departamento='Antioquia',
        )
        call_command('normalizar_ubicaciones_estudiantes', apply=True, verbosity=0)
        est.refresh_from_db()
        self.assertEqual(est.territory_id, '05001')
