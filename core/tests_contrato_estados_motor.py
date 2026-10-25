"""Contrato A5: los 13 estados del motor de curso, tal como responden hoy.

Son los 11 `estado_onboarding` que despacha `_procesar_twilio_webhook_cuerpo`,
más `nuevo` (el valor por defecto) y `esperando_tipo_doc` (flujo de corrección
sin su contexto). Cada caso parte de un estudiante activo en el módulo 1 de 3,
por la línea 2, y manda *listo* o una pregunta libre.
"""
from dataclasses import dataclass
from datetime import date

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Estudiante, ProgresoEstudiante, SandboxCanalSesion
from core.tests_support.contrato_linea import LINEA_2, ContratoLineaTestCase, crear_curso

RESPUESTA_LLM = 'RESPUESTA_LLM_FIJA'
PREGUNTA = 'cómo riego mejor el cultivo'
MODULO_2 = '*Módulo 2: Motor1 M2*'
NO_ENTENDI = 'No entendí. Si quiere avanzar'


@dataclass(frozen=True)
class Caso:
    fragmento: str
    estado_despues: str
    modulo_despues: int
    llamadas_llm: int
    mensajes: int = 1


AVANZA = Caso(MODULO_2, 'completado', 2, 0, mensajes=2)

CASOS = {
    'nuevo': (AVANZA, Caso(NO_ENTENDI, 'nuevo', 1, 0)),
    'completado': (AVANZA, Caso(NO_ENTENDI, 'completado', 1, 0)),
    'esperando_seleccion_curso': (AVANZA, Caso('No entendí tu selección', 'completado', 1, 0)),
    'esperando_codigo_empleabilidad': (AVANZA, Caso(NO_ENTENDI, 'completado', 1, 0)),
    'esperando_respuesta_pregunta_abierta_final': (
        Caso('No encuentro una pregunta abierta final', 'esperando_respuesta_pregunta_abierta_final', 1, 0),
        Caso('No encuentro una pregunta abierta final', 'esperando_respuesta_pregunta_abierta_final', 1, 0),
    ),
    'curso_finalizado': (
        Caso('Tienes un nuevo curso asignado', 'completado', 1, 0),
        Caso(NO_ENTENDI, 'curso_finalizado', 1, 0),
    ),
    'esperando_respuesta_asistente': (
        Caso(RESPUESTA_LLM, 'esperando_respuesta_reto', 1, 1),
        Caso('Le queda 1 pregunta', 'esperando_respuesta_asistente', 1, 1),
    ),
    'esperando_respuesta_reto': (
        Caso('Para el reto necesito su respuesta', 'esperando_respuesta_reto', 1, 0),
        Caso('*+35 puntos*', 'completado', 2, 1),
    ),
    'esperando_respuesta_tutor_ia': (
        Caso('Sin problema', 'completado', 1, 0),
        Caso('*+5 puntos bonus*', 'completado', 1, 0),
    ),
    'esperando_respuesta_progreso': (
        Caso('pasemos al reto de la facilitadora', 'esperando_respuesta_reto', 1, 1),
        Caso('Buena reflexión', 'esperando_respuesta_reto', 1, 2),
    ),
    'esperando_respuesta_recuperacion': (AVANZA, Caso(NO_ENTENDI, 'esperando_respuesta_recuperacion', 1, 0)),
    'esperando_respuesta_modulo': (AVANZA, Caso('No hay una pregunta pendiente', 'completado', 1, 0)),
    'esperando_tipo_doc': (AVANZA, Caso(NO_ENTENDI, 'esperando_tipo_doc', 1, 0)),
}


class ContratoEstadosMotorTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Motor',
            contacto_principal='Coord',
            email='motor@eki.test',
            telefono='573000000444',
            activo=True,
            fecha_fin_suscripcion=date(2099, 12, 31),
        )
        self.curso = crear_curso('Motor1', cliente=self.org, modulos=3)
        self.salida.llm_responde(RESPUESTA_LLM)
        self.n = 0

    def _estudiante_en(self, estado):
        self.n += 1
        tel = f'5730011200{self.n:02d}'
        est = Estudiante.objects.create(
            cedula=f'10600000{self.n:02d}', nombre='Dani Motor', telefono=tel, cliente=self.org,
            activo=True, estado_chat='ACTIVO', acepto_terminos=True,
        )
        inscribir_estudiante_en_curso(est, self.curso)
        SandboxCanalSesion.objects.create(
            telefono=tel, phone_id=LINEA_2.phone_id, modo='cursos', habeas_aceptado=True,
        )
        progreso = ProgresoEstudiante.objects.get(estudiante=est, curso=self.curso)
        est.estado_onboarding = estado
        est.contexto_temporal = {
            'progreso_id': progreso.id,
            'modulo_id': progreso.modulo_actual_id,
            'curso_activo_id': self.curso.id,
        }
        est.save()
        return est

    def _verificar(self, estado):
        self.assertEqual(len(CASOS), 13)
        for texto, caso in zip(('listo', PREGUNTA), CASOS[estado]):
            with self.subTest(texto=texto):
                est = self._estudiante_en(estado)
                antes = len(self.salida.llamadas_llm)
                envios = self.escribir(est.telefono, texto, linea=LINEA_2)
                est.refresh_from_db()
                progreso = ProgresoEstudiante.objects.get(estudiante=est, curso=self.curso)
                self.assertEqual(len(envios), caso.mensajes)
                self.assertIn(caso.fragmento, envios[0].texto)
                self.assertEqual(est.estado_onboarding, caso.estado_despues)
                self.assertEqual(progreso.modulo_actual.numero, caso.modulo_despues)
                self.assertEqual(len(self.salida.llamadas_llm) - antes, caso.llamadas_llm)
                self.assertEqual({e.phone_id for e in envios}, {LINEA_2.phone_id})

    def test_nuevo(self):
        self._verificar('nuevo')

    def test_completado(self):
        self._verificar('completado')

    def test_esperando_seleccion_curso(self):
        self._verificar('esperando_seleccion_curso')

    def test_esperando_codigo_empleabilidad(self):
        self._verificar('esperando_codigo_empleabilidad')

    def test_esperando_respuesta_pregunta_abierta_final(self):
        self._verificar('esperando_respuesta_pregunta_abierta_final')

    def test_curso_finalizado(self):
        self._verificar('curso_finalizado')

    def test_esperando_respuesta_asistente(self):
        self._verificar('esperando_respuesta_asistente')

    def test_esperando_respuesta_reto(self):
        self._verificar('esperando_respuesta_reto')

    def test_esperando_respuesta_tutor_ia(self):
        self._verificar('esperando_respuesta_tutor_ia')

    def test_esperando_respuesta_progreso(self):
        self._verificar('esperando_respuesta_progreso')

    def test_esperando_respuesta_recuperacion(self):
        self._verificar('esperando_respuesta_recuperacion')

    def test_esperando_respuesta_modulo(self):
        self._verificar('esperando_respuesta_modulo')

    def test_esperando_tipo_doc(self):
        self._verificar('esperando_tipo_doc')
