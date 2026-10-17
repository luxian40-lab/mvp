"""La lista de líneas Meta crece sin un hueco nuevo en el código."""
from django.test import SimpleTestCase, override_settings

from core.lineas.meta import lineas_producto, numeros_e164, phone_ids
from core.sandbox_canal import e164_lineas_meta, phone_ids_meta


@override_settings(
    SANDBOX_WHATSAPP_PHONE_ID='111',
    WHATSAPP_PHONE_ID='111',
    BOT_COMERCIAL_SANDBOX_NUMBER='573000000001',
    WHATSAPP_PHONE_NUMBER_ID_2='222',
    WHATSAPP_NUMERO_2_E164='573208998063',
    META_LINEAS='',
)
class LineasHistoricasTests(SimpleTestCase):
    def test_sin_lista_nueva_siguen_las_dos_de_siempre(self):
        self.assertEqual(phone_ids(), ('111', '222'))
        self.assertEqual(phone_ids_meta(), ('111', '222'))
        self.assertEqual(numeros_e164(), ('573000000001', '573208998063'))
        self.assertEqual(e164_lineas_meta(), numeros_e164())
        lineas = list(lineas_producto())
        self.assertEqual([linea.nombre for linea in lineas], ['Línea principal', 'Línea 2'])
        self.assertEqual(lineas[0].uso, 'completa')
        self.assertEqual(lineas[1].uso, 'solo_cursos')


@override_settings(
    META_LINEAS='111|573000000001|Principal;222|573208998063|Norte;333|573009990003|Sur;222|573208998063|Repetida',
)
class LineasExplicitasTests(SimpleTestCase):
    def test_tres_lineas_y_no_repite_el_mismo_id(self):
        self.assertEqual(phone_ids_meta(), ('111', '222', '333'))
        self.assertEqual(
            [linea.nombre for linea in lineas_producto()],
            ['Principal', 'Norte', 'Sur'],
        )
        self.assertIn('573009990003', e164_lineas_meta())
        self.assertTrue(all(linea.uso == 'completa' for linea in lineas_producto()))


@override_settings(
    META_LINEAS='111|573000000001|Principal;222|573208998063|Campo|cursos',
)
class LineaSoloCursosMarcadaTests(SimpleTestCase):
    def test_la_marca_cursos_deja_esa_linea_sin_planes(self):
        lineas = {linea.phone_id: linea.uso for linea in lineas_producto()}
        self.assertEqual(lineas['111'], 'completa')
        self.assertEqual(lineas['222'], 'solo_cursos')
