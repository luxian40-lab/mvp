"""Cada línea ofrece los cursos de su lista (LineaWhatsapp.cursos) con EKI_CURSOS_POR_LINEA."""
from datetime import date

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.lineas.cursos_linea import cursos_de_linea, fijar_curso_de_la_linea, solo_de_la_linea
from core.sandbox_canal import salida_por_phone_id
from core.lineas.perfil import USO_SOLO_CURSOS
from core.models import Cliente, Estudiante, LineaWhatsapp, ProgresoEstudiante
from core.planes_linea import PLAN_CURSO_ASESOR
from core.tests_support.contrato_linea import (
    LINEA_2,
    LINEA_PRINCIPAL,
    ContratoLineaTestCase,
    crear_curso,
    mensaje_boton_plantilla,
)

TEL = '573001110044'
CEDULA = '1077777744'


class CursosDeLineaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.uno = crear_curso('Uno', catalogo=True, orden=1)
        self.dos = crear_curso('Dos', catalogo=True, orden=2)
        self.linea = LineaWhatsapp.objects.create(phone_id='PN_B', nombre='Dos', uso=USO_SOLO_CURSOS)
        self.linea.cursos.add(self.dos)

    def test_apagado_no_hay_lista(self):
        self.assertIsNone(cursos_de_linea('PN_B'))

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_encendido_lee_la_lista_de_la_linea(self):
        self.assertEqual(cursos_de_linea('PN_B'), frozenset({self.dos.id}))

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_linea_sin_lista_o_sin_fila_ofrece_todo(self):
        LineaWhatsapp.objects.create(phone_id='PN_A', nombre='Uno')
        self.assertIsNone(cursos_de_linea('PN_A'))
        self.assertIsNone(cursos_de_linea('PN_OTRA'))
        self.assertIsNone(cursos_de_linea(''))

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_linea_apagada_no_recorta(self):
        self.linea.activo = False
        self.linea.save()
        self.assertIsNone(cursos_de_linea('PN_B'))

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_cambiar_la_lista_se_ve_enseguida(self):
        self.assertEqual(cursos_de_linea('PN_B'), frozenset({self.dos.id}))
        self.linea.cursos.add(self.uno)
        self.assertEqual(cursos_de_linea('PN_B'), frozenset({self.uno.id, self.dos.id}))
        self.linea.cursos.clear()
        self.assertIsNone(cursos_de_linea('PN_B'))

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_recorta_el_avance_a_los_cursos_de_la_linea(self):
        est = Estudiante.objects.create(cedula='CC44', nombre='Ana', telefono=TEL, activo=True)
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.uno)
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.dos)
        todos = ProgresoEstudiante.objects.filter(estudiante=est)
        self.assertEqual([p.curso_id for p in solo_de_la_linea(todos, 'PN_B')], [self.dos.id])
        self.assertEqual(solo_de_la_linea(todos, 'PN_OTRA').count(), 2)

    @override_settings(EKI_CURSOS_POR_LINEA=True)
    def test_cursos_empezados_se_recortan_a_la_linea_del_turno(self):
        from core.lineas.principal.cursos import _abiertos_del_mes

        est = Estudiante.objects.create(cedula='CC46', nombre='Ana', telefono=TEL, activo=True)
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.uno)
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.dos)
        with salida_por_phone_id('PN_B'):
            self.assertEqual([p.curso_id for p in _abiertos_del_mes(TEL)], [self.dos.id])
        with salida_por_phone_id('PN_A'):
            self.assertEqual(len(_abiertos_del_mes(TEL)), 2)


@override_settings(EKI_CURSOS_POR_LINEA=True, EKI_ESTADO_LINEA_LECTURA=True)
class FijarCursoDeLaLineaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.uno = crear_curso('Uno', catalogo=True, orden=1)
        self.dos = crear_curso('Dos', catalogo=True, orden=2)
        self.linea = LineaWhatsapp.objects.create(phone_id='PN_B', nombre='Dos', uso=USO_SOLO_CURSOS)
        self.linea.cursos.add(self.dos)
        self.est = Estudiante.objects.create(
            cedula='CC45', nombre='Ana', telefono=TEL, activo=True,
            contexto_temporal={'curso_activo_id': self.uno.id, 'otra': 1},
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.uno)
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.dos)

    def _buscar(self):
        return Estudiante.objects.get(pk=self.est.pk)

    def test_pone_en_foco_el_unico_curso_abierto_de_la_linea(self):
        self.assertTrue(fijar_curso_de_la_linea('PN_B', self._buscar))
        self.est.refresh_from_db()
        self.assertEqual(self.est.contexto_temporal, {'curso_activo_id': self.dos.id, 'otra': 1})

    def test_si_ya_esta_en_foco_no_escribe(self):
        fijar_curso_de_la_linea('PN_B', self._buscar)
        self.assertFalse(fijar_curso_de_la_linea('PN_B', self._buscar))

    def test_con_dos_cursos_abiertos_de_la_lista_no_elige(self):
        self.linea.cursos.add(self.uno)
        self.assertFalse(fijar_curso_de_la_linea('PN_B', self._buscar))
        self.est.refresh_from_db()
        self.assertEqual(self.est.contexto_temporal['curso_activo_id'], self.uno.id)

    def test_curso_de_la_linea_completado_no_se_pone_en_foco(self):
        ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.dos).update(completado=True)
        self.assertFalse(fijar_curso_de_la_linea('PN_B', self._buscar))

    @override_settings(EKI_ESTADO_LINEA_LECTURA=False)
    def test_sin_lectura_no_mueve_el_foco_compartido(self):
        self.assertFalse(fijar_curso_de_la_linea('PN_B', self._buscar))
        self.est.refresh_from_db()
        self.assertEqual(self.est.contexto_temporal['curso_activo_id'], self.uno.id)

    @override_settings(EKI_CURSOS_POR_LINEA=False)
    def test_sin_flag_no_busca_al_estudiante(self):
        self.assertFalse(fijar_curso_de_la_linea('PN_B', self.fail))

    def test_linea_sin_lista_no_busca_al_estudiante(self):
        self.assertFalse(fijar_curso_de_la_linea('PN_OTRA', self.fail))

    def test_sin_estudiante_no_hace_nada(self):
        self.assertFalse(fijar_curso_de_la_linea('PN_B', lambda: None))


@override_settings(EKI_CURSOS_POR_LINEA=True, EKI_ESTADO_LINEA_LECTURA=True)
class DosLineasConCursosPorLineaTests(ContratoLineaTestCase):
    """La persona va en un curso de la principal y la línea 2 le asigna el suyo."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.org = Cliente.objects.create(
            nombre='Org Cursos Linea', contacto_principal='Coord', email='cl@eki.test',
            telefono='573000000444', activo=True, fecha_fin_suscripcion=date(2099, 12, 31),
            plan_linea_meta=PLAN_CURSO_ASESOR,
        )
        self.general = crear_curso('General1', catalogo=True, orden=1)
        self.lineal = crear_curso('Lineal1', cliente=self.org, orden=1, modulos=3)
        self.est = Estudiante.objects.create(
            cedula=CEDULA, nombre='Caro Cursos', telefono=TEL, cliente=self.org, activo=True,
        )
        fila = LineaWhatsapp.objects.create(phone_id=LINEA_2.phone_id, nombre='Línea 2', uso=USO_SOLO_CURSOS)
        fila.cursos.add(self.lineal)

    def _identidad(self, linea, nombre):
        self.lanzar_campana([self.est], linea=linea, nombre=nombre)
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'), linea=linea)
        self.escribir(TEL, 'acepto', linea=linea)
        self.escribir(TEL, CEDULA, linea=linea)
        return self.escribir(TEL, 'si', linea=linea)

    def _principal_en_modulo_1(self):
        self._identidad(LINEA_PRINCIPAL, 'principal')
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.general.id}', 'Ver curso')
        self.tocar(TEL, 'continuemos', 'Continuar')
        inscribir_estudiante_en_curso(self.est, self.lineal)

    def _modulo(self, curso):
        return ProgresoEstudiante.objects.get(estudiante=self.est, curso=curso).modulo_actual.numero

    def test_al_confirmar_en_la_linea_2_entrega_el_modulo_1_de_su_curso(self):
        self._principal_en_modulo_1()
        envios = self._identidad(LINEA_2, 'linea2')
        textos = '\n'.join(e.texto for e in envios)
        self.assertEqual({e.phone_id for e in envios}, {LINEA_2.phone_id})
        self.assertIn('Lineal1 M1', textos)
        self.assertNotIn('General1', textos)

    def test_continuar_en_la_linea_2_sigue_su_curso_y_no_toca_la_principal(self):
        self._principal_en_modulo_1()
        self._identidad(LINEA_2, 'linea2')
        envios = self.escribir(TEL, 'continuemos', linea=LINEA_2)
        textos = '\n'.join(e.texto for e in envios)
        self.assertIn('Lineal1', textos)
        self.assertNotIn('General1', textos)
        self.assertEqual(self._modulo(self.general), 1)
        principal = self.tocar(TEL, 'continuemos', 'Continuar')
        self.assertIn('*Módulo 2: General1 M2*', principal[0].texto)
