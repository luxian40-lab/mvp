"""C2: el perfil de cada línea sale de su uso y coincide con es_modo_twilio."""
from dataclasses import fields

from django.test import SimpleTestCase, override_settings

from core.lineas.meta import USO_COMPLETA, USO_SOLO_CURSOS, LineaMeta
from core.lineas.perfil import PERFIL_COMPLETA, PERFIL_SOLO_CURSOS, PerfilLinea, perfil_por_uso
from core.lineas.variante import es_modo_twilio, perfil_de

LINEAS = 'PN_UNO|+573000000001|Principal;PN_DOS|+573000000002|Segunda|cursos'


def _capacidades(perfil: PerfilLinea) -> set[str]:
    return {f.name for f in fields(perfil) if f.name != 'uso' and getattr(perfil, f.name)}


class PerfilLineaTests(SimpleTestCase):
    def test_capacidad_nueva_entra_apagada(self):
        self.assertEqual(_capacidades(PerfilLinea(uso='otra')), set())

    def test_principal_tiene_todo_menos_curso_directo(self):
        todas = {f.name for f in fields(PerfilLinea)} - {'uso'}
        self.assertEqual(_capacidades(PERFIL_COMPLETA), todas - {'curso_directo'})

    def test_linea_2_es_curso_lineal(self):
        self.assertEqual(
            _capacidades(PERFIL_SOLO_CURSOS),
            {'agentes_en_curso', 'certificado', 'campanas', 'curso_directo'},
        )

    def test_uso_desconocido_es_la_principal(self):
        self.assertIs(perfil_por_uso(''), PERFIL_COMPLETA)
        self.assertIs(perfil_por_uso(None), PERFIL_COMPLETA)
        self.assertIs(perfil_por_uso('raro'), PERFIL_COMPLETA)

    def test_linea_meta_trae_su_perfil(self):
        self.assertIs(LineaMeta('a', '1', 'x').perfil, PERFIL_COMPLETA)
        self.assertIs(LineaMeta('b', '2', 'y', uso=USO_SOLO_CURSOS).perfil, PERFIL_SOLO_CURSOS)
        self.assertEqual(USO_COMPLETA, 'completa')


@override_settings(META_LINEAS=LINEAS)
class PerfilDeLineaTests(SimpleTestCase):
    def test_perfil_por_phone_id(self):
        self.assertIs(perfil_de('PN_UNO'), PERFIL_COMPLETA)
        self.assertIs(perfil_de('PN_DOS'), PERFIL_SOLO_CURSOS)

    def test_linea_fuera_del_registro_es_la_principal(self):
        self.assertIs(perfil_de('PN_OTRO'), PERFIL_COMPLETA)
        self.assertIs(perfil_de(''), PERFIL_COMPLETA)

    def test_sin_phone_id_usa_el_del_turno(self):
        from core.sandbox_canal import salida_por_phone_id

        with salida_por_phone_id('PN_DOS'):
            self.assertIs(perfil_de(), PERFIL_SOLO_CURSOS)
        with salida_por_phone_id('PN_UNO'):
            self.assertIs(perfil_de(), PERFIL_COMPLETA)

    def test_curso_directo_coincide_con_es_modo_twilio(self):
        for pnid in ('PN_UNO', 'PN_DOS', 'PN_OTRO', ''):
            with self.subTest(pnid=pnid):
                self.assertEqual(perfil_de(pnid).curso_directo, es_modo_twilio(pnid))
