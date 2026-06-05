from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from io import StringIO

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from portal.cobertura_geo import resumen_cobertura_geografica
from portal.geo_catalogo import (
    centroide_municipio,
    clave_departamento,
    resolver_ubicacion,
    ruta_geojson_departamentos,
    ruta_geojson_municipios,
)
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class CoberturaGeoTests(TestCase):
    def test_centroide_medellin(self):
        c = centroide_municipio('Medellín', 'Antioquia')
        self.assertIsNotNone(c)
        lat, lng = c
        self.assertTrue(5 < lat < 7)
        self.assertTrue(-76 < lng < -75)

    def test_clave_bogota(self):
        self.assertEqual(clave_departamento('Bogotá'), 'BOGOTA, D.C.')

    def test_resolver_aproximado_typo(self):
        ubic = resolver_ubicacion('Medelin', 'Antioquia')
        self.assertEqual(ubic.nivel, 'municipio')
        self.assertEqual(ubic.metodo, 'aproximado')
        self.assertEqual(ubic.municipio, 'Medellin')

    def test_resolver_cartagena_atlantico_a_bolivar(self):
        ubic = resolver_ubicacion('Cartagena', 'Atlántico')
        self.assertEqual(ubic.nivel, 'municipio')
        self.assertEqual(ubic.clave_municipio, 'CARTAGENA DE INDIAS|BOLIVAR')

    def test_resolver_bogota_cundinamarca(self):
        ubic = resolver_ubicacion('Bogotá', 'Cundinamarca')
        self.assertEqual(ubic.nivel, 'municipio')
        self.assertEqual(ubic.clave_municipio, 'BOGOTA, D.C.|BOGOTA, D.C.')

    def test_resumen_con_coordenadas(self):
        org = Cliente.objects.create(
            nombre='Geo Org',
            contacto_principal='A',
            email='geo@test.com',
            telefono='573001111111',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        curso = Curso.objects.create(cliente=org, nombre='Curso Geo', activo=True)
        est = Estudiante.objects.create(
            cliente=org,
            nombre='Ana',
            telefono='573001111112',
            departamento='Antioquia',
            municipio='Medellín',
            activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        data = resumen_cobertura_geografica(org)
        self.assertEqual(len(data['por_curso']), 1)
        self.assertEqual(data['total_estudiantes'], 1)
        self.assertEqual(data['con_municipio_mapeado'], 1)
        self.assertIsNotNone(data['puntos'][0]['lat'])
        self.assertIn('MEDELLIN|ANTIOQUIA', data['por_municipio_clave'])


class PortalCoberturaMapTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Map Org',
            contacto_principal='A',
            email='map@test.com',
            telefono='573002222221',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.user = User.objects.create_user('portal_map', password='pass1234')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')
        self.http = Client()
        session = self.http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=self.user).pk
        session.save()

    def test_geojson_disponible(self):
        self.assertTrue(ruta_geojson_departamentos().is_file())
        self.assertTrue(ruta_geojson_municipios().is_file())

    def test_vista_cobertura_y_api(self):
        curso = Curso.objects.create(cliente=self.org, nombre='Curso Map', activo=True)
        est = Estudiante.objects.create(
            cliente=self.org,
            nombre='Luis',
            telefono='573002222222',
            departamento='Antioquia',
            municipio='Medellín',
            activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        r = self.http.get('/portal/cobertura/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'mapa-cobertura')

        api = self.http.get('/portal/cobertura/datos.json')
        self.assertEqual(api.status_code, 200)
        payload = api.json()
        self.assertEqual(payload['total_estudiantes'], 1)
        self.assertTrue(payload['puntos'][0]['lat'])
        self.assertTrue(payload['por_municipio_clave'])

        geo = self.http.get('/portal/cobertura/municipios.geojson')
        self.assertEqual(geo.status_code, 200)
        body = b''.join(geo.streaming_content)
        self.assertIn(b'"CLAVE"', body)


class NormalizarUbicacionesCommandTests(TestCase):
    def test_normaliza_typo_medelin(self):
        org = Cliente.objects.create(
            nombre='Norm Org',
            contacto_principal='A',
            email='norm@test.com',
            telefono='573003333331',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        est = Estudiante.objects.create(
            cliente=org,
            nombre='Pepe',
            telefono='573003333332',
            departamento='antioquia',
            municipio='medelin',
            activo=True,
        )
        out = StringIO()
        call_command('normalizar_ubicaciones_estudiantes', '--apply', stdout=out)
        est.refresh_from_db()
        self.assertEqual(est.municipio, 'Medellin')
        self.assertEqual(est.departamento, 'Antioquia')
