"""Las dos copias de esperando_seleccion_curso en el cuerpo, y a quién atiende cada una.

La del bloque ACTIVO corta el turno, pero ese bloque solo entra con
`estado_chat == 'ACTIVO'` (o `estado_onboarding == 'completado'`). Con un
`estado_chat` legado que no es barrera, el turno pasa de largo y lo atiende la
copia del despachador (`core/conversacion/estados/seleccion_curso.py`). Por eso
esa copia no se borra en D4.
"""
from datetime import date
from unittest.mock import patch

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Estudiante, SandboxCanalSesion
from core.tests_support.contrato_linea import LINEA_2, ContratoLineaTestCase, crear_curso

ESTADO = 'esperando_seleccion_curso'
PREGUNTA = 'cómo riego mejor el cultivo'
COPIA_ACTIVO = 'Escribe *tomar 1* para escoger un curso'
COPIA_DESPACHADOR = 'Escribe *menú* para ver las opciones'


class SeleccionCursoDosCopiasTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Seleccion', contacto_principal='Coord', email='sel@eki.test',
            telefono='573000000555', activo=True, fecha_fin_suscripcion=date(2099, 12, 31),
        )
        self.cursos = [crear_curso(f'Sel{i}', cliente=self.org, modulos=2) for i in (1, 2)]
        self.salida.llm_responde('RESPUESTA_LLM_FIJA')
        self.n = 0

    def _estudiante_eligiendo(self, estado_chat):
        self.n += 1
        tel = f'5730013300{self.n:02d}'
        est = Estudiante.objects.create(
            cedula=f'10700000{self.n:02d}', nombre='Sel Prueba', telefono=tel, cliente=self.org,
            activo=True, estado_chat=estado_chat, acepto_terminos=True,
        )
        for curso in self.cursos:
            inscribir_estudiante_en_curso(est, curso)
        SandboxCanalSesion.objects.create(
            telefono=tel, phone_id=LINEA_2.phone_id, modo='cursos', habeas_aceptado=True,
        )
        est.estado_onboarding = ESTADO
        est.contexto_temporal = {'tipo': 'seleccion_curso'}
        est.save()
        return est

    def _turno(self, estado_chat, texto):
        from core.conversacion.estados import despacho

        est = self._estudiante_eligiendo(estado_chat)
        with patch.object(despacho, 'agente_de', wraps=despacho.agente_de) as espia:
            envios = self.escribir(est.telefono, texto, linea=LINEA_2)
        vistos = [llamada.args[0] for llamada in espia.call_args_list]
        return envios, vistos

    def test_con_activo_responde_la_copia_del_bloque_activo(self):
        for texto in ('listo', 'menú', '1', 'tomar 2', 'hola', PREGUNTA):
            with self.subTest(texto=texto):
                envios, vistos = self._turno('ACTIVO', texto)
                self.assertTrue(envios)
                self.assertNotIn(ESTADO, vistos)
        envios, _ = self._turno('ACTIVO', PREGUNTA)
        self.assertIn(COPIA_ACTIVO, envios[0].texto)

    def test_con_estado_chat_legado_responde_la_copia_del_despachador(self):
        envios, vistos = self._turno('nuevo', PREGUNTA)
        self.assertIn(ESTADO, vistos)
        self.assertIn(COPIA_DESPACHADOR, envios[0].texto)
