"""Línea de curso lineal: el sí de los datos arranca el curso que no ha empezado."""
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.inicio_curso import inicio_ya_entregado
from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.lineas.variante import TEXTO_LINEA_MODO_TWILIO
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    SandboxCanalSesion,
)
from core.sandbox_canal import salida_por_phone_id
from core.sandbox_menu import _responder_confirmacion

PRINCIPAL = '100000000000001'
LINEA_2 = '100000000000002'
TEL = '573001110060'


def _curso(nombre, cliente):
    curso = Curso.objects.create(
        nombre=nombre, descripcion='d', cliente=cliente, activo=True, dias_espera_entre_modulos=0,
    )
    for numero in (1, 2):
        Modulo.objects.create(
            curso=curso, numero=numero, titulo=f'{nombre} M{numero}', descripcion='d',
            contenido=f'CONTENIDO_{nombre}_{numero}',
        )
    return curso


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    WHATSAPP_PHONE_ID=PRINCIPAL,
    SANDBOX_WHATSAPP_PHONE_ID=PRINCIPAL,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009990002',
    WHATSAPP_TOKEN='tok',
    META_LINEAS='',
    SECURE_SSL_REDIRECT=False,
)
class Linea2CursoDirectoTests(TestCase):
    def setUp(self):
        self.enviados = []

        def graph(payload, agente=''):
            self.enviados.append(payload)
            return {'success': True, 'mensaje_id': f'wamid.{len(self.enviados)}', 'response': ''}

        patch('core.lineas.envio._post_graph', side_effect=graph).start()
        patch('core.lineas.envio.time.sleep').start()
        self.addCleanup(patch.stopall)
        self.org = Cliente.objects.create(
            nombre='Org L2', contacto_principal='C', email='l2@eki.test', telefono='573000000666',
            activo=True, fecha_fin_suscripcion=date(2099, 12, 31),
        )
        self.curso = _curso('Lineal1', self.org)
        self.est = Estudiante.objects.create(
            cedula='1099999999', nombre='Beto', telefono=TEL, cliente=self.org, activo=True,
            estado_chat='CONFIRMANDO_DATOS', acepto_terminos=True,
        )
        inscribir_estudiante_en_curso(self.est, self.curso)

    def _confirmar(self, phone_id=LINEA_2):
        with salida_por_phone_id(phone_id):
            self.assertEqual(_responder_confirmacion(TEL, TEL, 'si'), 'handled')
        return [p.get('text', {}).get('body', '') for p in self.enviados]

    def _progreso(self):
        return ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)

    def test_curso_sin_empezar_arranca_con_saludo_y_modulo_1(self):
        textos = self._confirmar()
        self.assertIn('Soy el Formador', textos[0])
        self.assertIn('Compañero', textos[1])
        self.assertIn('CONTENIDO_Lineal1_1', textos[-1])
        self.assertFalse([t for t in textos if '[MULTI_MSG]' in t or '[SEP]' in t])
        self.assertNotIn(TEXTO_LINEA_MODO_TWILIO, textos)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ACTIVO')
        self.assertTrue(inicio_ya_entregado(self.est, self.curso.id))
        self.assertEqual(self.est.contexto_temporal['curso_activo_id'], self.curso.id)
        self.assertEqual(self._progreso().modulo_actual.numero, 1)
        self.assertFalse(ModuloCompletado.objects.filter(progreso=self._progreso()).exists())
        sesion = SandboxCanalSesion.objects.get(telefono=TEL, phone_id=LINEA_2)
        self.assertEqual(sesion.modo, 'cursos')
        self.assertTrue(sesion.habeas_aceptado)

    def test_curso_ya_empezado_sigue_con_el_texto_de_la_linea(self):
        progreso = self._progreso()
        ModuloCompletado.objects.create(progreso=progreso, modulo=progreso.modulo_actual)
        self.assertEqual(self._confirmar(), [TEXTO_LINEA_MODO_TWILIO])

    def test_saludo_ya_entregado_no_se_repite(self):
        self.est.contexto_temporal = {'inicio_curso_id': self.curso.id}
        self.est.save(update_fields=['contexto_temporal'])
        self.assertEqual(self._confirmar(), [TEXTO_LINEA_MODO_TWILIO])

    def test_dos_cursos_abiertos_no_elige_por_la_persona(self):
        inscribir_estudiante_en_curso(self.est, _curso('Lineal2', self.org))
        self.assertEqual(self._confirmar(), [TEXTO_LINEA_MODO_TWILIO])

    def test_linea_principal_no_arranca_el_curso(self):
        textos = self._confirmar(PRINCIPAL)
        self.assertFalse([t for t in textos if 'Formador' in t or 'CONTENIDO_' in t])
        self.assertFalse(inicio_ya_entregado(self.est, self.curso.id))
