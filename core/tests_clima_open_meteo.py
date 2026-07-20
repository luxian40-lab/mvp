"""Tests Open-Meteo → bloque clima para Nat."""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.clima_open_meteo import (
    consulta_necesita_clima,
    formatear_bloque_clima,
    obtener_bloque_clima_para_nat,
    resolver_ubicacion_texto,
)


class ConsultaNecesitaClimaTests(SimpleTestCase):
    def test_detecta_lluvia_y_fumigar(self):
        self.assertTrue(consulta_necesita_clima('¿Va a llover mañana en Ibagué?'))
        self.assertTrue(consulta_necesita_clima('Puedo fumigar hoy el café?'))
        self.assertTrue(consulta_necesita_clima('¿Riego o espero?'))
        self.assertFalse(consulta_necesita_clima('¿Cuánto cuesta el fertilizante X?'))


class ResolverUbicacionTests(SimpleTestCase):
    def test_desde_pregunta_en_municipio(self):
        u = resolver_ubicacion_texto(None, '¿Llueve en ibague?')
        self.assertIn('Ibagué', u)
        self.assertIn('Colombia', u)

    def test_bogota_sin_enganchar_para(self):
        u = resolver_ubicacion_texto(None, 'Cual es el clima en Bogota para fumigar manana?')
        self.assertIn('Bogotá', u)
        self.assertNotIn('Para', u)

    def test_desde_ctx_municipio(self):
        ctx = mock.Mock(spec=['municipio', 'region', 'vereda'])
        ctx.municipio = 'Neiva'
        ctx.region = 'Huila'
        ctx.vereda = ''
        u = resolver_ubicacion_texto(ctx, 'hola')
        self.assertIn('Neiva', u)
        self.assertIn('Huila', u)


class FormatearBloqueTests(SimpleTestCase):
    def test_formatea_probabilidad(self):
        geo = {
            'name': 'Ibagué',
            'admin1': 'Tolima',
            'country': 'Colombia',
            'latitude': 4.44,
            'longitude': -75.24,
        }
        data = {
            'daily': {
                'time': ['2026-07-20', '2026-07-21', '2026-07-22'],
                'precipitation_probability_max': [80, 40, 10],
                'precipitation_sum': [12.5, 2.0, 0.0],
                'temperature_2m_max': [28, 29, 30],
                'temperature_2m_min': [18, 19, 18],
                'wind_speed_10m_max': [15, 12, 10],
            }
        }
        bloque = formatear_bloque_clima(geo, data)
        self.assertIn('CLIMA VERIFICADO', bloque)
        self.assertIn('80%', bloque)
        self.assertIn('Ibagué', bloque)
        self.assertIn('Open-Meteo', bloque)


@override_settings(NAT_OPEN_METEO_ENABLED=True, NAT_OPEN_METEO_CACHE_SECONDS=3600)
class ObtenerBloqueClimaTests(SimpleTestCase):
    def test_sin_necesidad_climatica_vacio(self):
        self.assertEqual(obtener_bloque_clima_para_nat('precio del abono'), '')

    def test_sin_ubicacion_pide_municipio(self):
        out = obtener_bloque_clima_para_nat('¿Va a llover mañana?')
        self.assertIn('municipio', out.lower())
        self.assertIn('departamento', out.lower())
        self.assertIn('vereda', out.lower())

    @mock.patch('core.clima_open_meteo.forecast_open_meteo')
    @mock.patch('core.clima_open_meteo.geocode_open_meteo')
    def test_flujo_ok(self, mock_geo, mock_fc):
        mock_geo.return_value = {
            'name': 'Ibagué',
            'admin1': 'Tolima',
            'country': 'Colombia',
            'latitude': 4.44,
            'longitude': -75.24,
        }
        mock_fc.return_value = {
            'daily': {
                'time': ['2026-07-20'],
                'precipitation_probability_max': [70],
                'precipitation_sum': [5.0],
                'temperature_2m_max': [27],
                'temperature_2m_min': [17],
                'wind_speed_10m_max': [14],
            }
        }
        out = obtener_bloque_clima_para_nat('¿Puedo fumigar en Ibagué mañana?')
        self.assertIn('70%', out)
        self.assertIn('Ibagué', out)
        mock_geo.assert_called_once()
        mock_fc.assert_called_once()

    @mock.patch('core.clima_open_meteo.forecast_open_meteo')
    @mock.patch('core.clima_open_meteo.geocode_open_meteo')
    def test_bogota_live_query_shape(self, mock_geo, mock_fc):
        mock_geo.return_value = {
            'name': 'Bogotá',
            'admin1': 'Bogotá D.C.',
            'country': 'Colombia',
            'latitude': 4.71,
            'longitude': -74.07,
        }
        mock_fc.return_value = {
            'daily': {
                'time': ['2026-07-20', '2026-07-21'],
                'precipitation_probability_max': [55, 40],
                'precipitation_sum': [3.0, 1.0],
                'temperature_2m_max': [20, 19],
                'temperature_2m_min': [10, 9],
                'wind_speed_10m_max': [12, 11],
            }
        }
        ctx = mock.Mock(
            municipio='', region='', vereda='', latitud=None, longitud=None, metadata={},
        )
        ctx.save = mock.Mock()
        out = obtener_bloque_clima_para_nat(
            'Cual es el clima en Bogota para fumigar manana?',
            ctx_agro=ctx,
        )
        self.assertIn('Bogotá', out)
        self.assertIn('55%', out)
        # Debe persistir coords en el contexto
        self.assertTrue(ctx.save.called)
        args = mock_geo.call_args[0][0]
        self.assertIn('Bogotá', args)
        self.assertNotIn('Para', args)

    @override_settings(NAT_OPEN_METEO_ENABLED=False)
    def test_deshabilitado(self):
        self.assertEqual(
            obtener_bloque_clima_para_nat('¿Llueve en Neiva?'),
            '',
        )
