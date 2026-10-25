"""C4: líneas en la base detrás de EKI_LINEAS_BD_ENABLED; el entorno queda de respaldo."""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.lineas.campana import waba_de_linea
from core.lineas.meta import lineas_producto, linea_por_phone_id, nombre_de_linea
from core.lineas.oferta import cliente_de_la_linea
from core.lineas.perfil import PERFIL_COMPLETA, PERFIL_SOLO_CURSOS, USO_SOLO_CURSOS
from core.lineas.variante import perfil_de
from core.models import Cliente, LineaWhatsapp

ENTORNO = 'PN_ENV|+573000000009|Del entorno'


def _cliente(nombre, **extra):
    return Cliente.objects.create(
        nombre=nombre, contacto_principal='C', email=f'{nombre.lower()}@eki.test', telefono='573000000111',
        activo=True, fecha_fin_suscripcion=date(2099, 12, 31), **extra,
    )


@override_settings(
    META_LINEAS=ENTORNO,
    WHATSAPP_BUSINESS_ACCOUNT_ID='WABA_ENV',
    WHATSAPP_BUSINESS_ACCOUNT_ID_2='WABA_ENV_2',
)
class LineasBdTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _filas(self):
        LineaWhatsapp.objects.create(phone_id='PN_B', e164='+57 300 000 0002', nombre='Dos', uso=USO_SOLO_CURSOS, orden=2)
        LineaWhatsapp.objects.create(phone_id='PN_A', e164='573000000001', nombre='Uno', orden=1)
        LineaWhatsapp.objects.create(phone_id='PN_X', nombre='Apagada', activo=False, orden=0)

    def test_apagado_manda_el_entorno_aunque_haya_filas(self):
        self._filas()
        self.assertEqual([l.phone_id for l in lineas_producto()], ['PN_ENV'])

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_encendido_lee_las_activas_en_orden(self):
        self._filas()
        lineas = lineas_producto()
        self.assertEqual([l.phone_id for l in lineas], ['PN_A', 'PN_B'])
        self.assertEqual(lineas[1].e164, '573000000002')
        self.assertEqual(nombre_de_linea('PN_B'), 'Dos')
        self.assertIs(perfil_de('PN_A'), PERFIL_COMPLETA)
        self.assertIs(perfil_de('PN_B'), PERFIL_SOLO_CURSOS)

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_encendido_sin_filas_activas_sigue_el_entorno(self):
        LineaWhatsapp.objects.create(phone_id='PN_X', nombre='Apagada', activo=False)
        self.assertEqual([l.phone_id for l in lineas_producto()], ['PN_ENV'])

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_guardar_y_borrar_olvidan_la_cache(self):
        linea = LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno')
        self.assertEqual(nombre_de_linea('PN_A'), 'Uno')
        linea.nombre = 'Uno nuevo'
        linea.save()
        self.assertEqual(nombre_de_linea('PN_A'), 'Uno nuevo')
        linea.delete()
        self.assertEqual([l.phone_id for l in lineas_producto()], ['PN_ENV'])

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_tabla_caida_sigue_el_entorno(self):
        with patch('core.lineas.modelo.LineaWhatsapp.objects.filter', side_effect=DatabaseError('caida')):
            with self.assertLogs('core.lineas.modelo', level='WARNING'):
                self.assertEqual([l.phone_id for l in lineas_producto()], ['PN_ENV'])

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_waba_de_la_fila_gana_y_vacia_sigue_el_entorno(self):
        LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno', waba_id='WABA_FILA')
        LineaWhatsapp.objects.create(phone_id='PN_B', nombre='Dos', uso=USO_SOLO_CURSOS)
        LineaWhatsapp.objects.create(phone_id='PN_C', nombre='Tres')
        self.assertEqual(waba_de_linea('PN_A'), 'WABA_FILA')
        self.assertEqual(waba_de_linea('PN_B'), 'WABA_ENV_2')
        self.assertEqual(waba_de_linea('PN_C'), 'WABA_ENV')

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_cliente_de_la_fila_gana_sobre_phone_id_meta(self):
        dueno = _cliente('Duena')
        _cliente('Vieja', phone_id_meta='PN_A')
        LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno', cliente=dueno)
        self.assertEqual(cliente_de_la_linea('PN_A'), dueno)

    @override_settings(EKI_LINEAS_BD_ENABLED=True)
    def test_cliente_inactivo_de_la_fila_cae_a_phone_id_meta(self):
        dueno = _cliente('Inactiva')
        Cliente.objects.filter(pk=dueno.pk).update(activo=False)
        vieja = _cliente('Vieja', phone_id_meta='PN_A')
        LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno', cliente=dueno)
        self.assertEqual(cliente_de_la_linea('PN_A'), vieja)

    def test_entorno_no_trae_waba_ni_cliente(self):
        linea = linea_por_phone_id('PN_ENV')
        self.assertEqual((linea.waba_id, linea.cliente_id), ('', None))
        self.assertIsNone(linea_por_phone_id(''))


class LineaWhatsappAdminTests(TestCase):
    def test_listado_y_alta_abren(self):
        admin = get_user_model().objects.create_superuser('linea_admin', 'linea@eki.test', 'x-prueba-123')
        self.client.force_login(admin)
        LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno')
        self.assertEqual(self.client.get(reverse('admin:core_lineawhatsapp_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_lineawhatsapp_add')).status_code, 200)
