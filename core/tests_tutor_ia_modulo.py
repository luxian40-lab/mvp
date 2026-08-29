from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import Cliente, Curso, Modulo
from core.tutor_ia_modulo import (
    _es_respuesta_sin_contenido_reto,
    armar_guia_reto_para_prompt,
    evaluar_reto_facilitador,
    generar_reto_facilitador,
)


def test_detector_respuesta_sin_contenido_variantes():
    assert _es_respuesta_sin_contenido_reto("no se")
    assert _es_respuesta_sin_contenido_reto("No sé")
    assert _es_respuesta_sin_contenido_reto("ni idea")
    assert _es_respuesta_sin_contenido_reto("   ")
    assert not _es_respuesta_sin_contenido_reto("Aplicaría MIP y monitoreo semanal")


def test_evaluacion_reto_no_inventa_evidencia_cuando_responde_no_se():
    puntaje, feedback = evaluar_reto_facilitador(
        modulos_cubiertos=[],
        respuesta_estudiante="no se",
        reto_original="¿Cómo diagnosticaría y controlaría la plaga?",
        estudiante_nombre="Juliana",
    )

    assert puntaje == 1
    lower = feedback.lower()
    assert "indicó que no sabía" in lower
    assert "hojas amarillas" not in lower
    assert "mip" not in lower


def test_evaluacion_reto_bueno_sin_contenido():
    puntaje, feedback = evaluar_reto_facilitador(
        modulos_cubiertos=[],
        respuesta_estudiante="bueno",
        reto_original="¿Qué haría con su presupuesto?",
        estudiante_nombre="Pedro",
    )
    assert puntaje == 1
    assert "no sabía" in feedback.lower() or "no hay evidencia" in feedback.lower()


class GuiaRetoIaTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Org Reto',
            contacto_principal='A',
            email='reto@test.co',
            telefono='573001110099',
        )
        self.curso = Curso.objects.create(
            nombre='Finanzas del hogar',
            cliente=self.cli,
            preguntas_ejemplo_ia='Ejemplo curso: diga qué gasto revisaría primero.',
        )
        self.m3 = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Presupuesto semanal',
            contenido='Ingresos y gastos del hogar.',
            tipo_reto_ia=Modulo.TIPO_RETO_PLAN,
            reto_guia_ia='Que diga un plan de 7 días para anotar gastos.',
            facilitador_checkpoint=Modulo.FACILITADOR_CP_SI,
        )

    def test_armar_guia_modulo_manda_sobre_curso(self):
        texto, tipo = armar_guia_reto_para_prompt(self.curso, self.m3)
        self.assertEqual(tipo, Modulo.TIPO_RETO_PLAN)
        self.assertIn('GUÍA DEL MÓDULO CHECKPOINT 3', texto)
        self.assertIn('plan de 7 días', texto)
        self.assertIn('GUÍA DEL CURSO', texto)
        self.assertIn('gasto revisaría', texto)

    def test_armar_guia_tipo_vacio_usa_aplicacion_y_micros(self):
        from core.models import PasoModulo, SeccionModulo

        m = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Ahorro semanal',
            contenido='Guardar una parte.',
            tipo_reto_ia='',
            reto_guia_ia='',
        )
        sec = SeccionModulo.objects.create(modulo=m, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=m, seccion=sec, orden=1, titulo='Sobre de ahorro', contenido='x', activo=True,
        )
        texto, tipo = armar_guia_reto_para_prompt(self.curso, m)
        self.assertEqual(tipo, Modulo.TIPO_RETO_APLICACION)
        self.assertIn('Sobre de ahorro', texto)
        self.assertIn('MICROLECCIONES', texto)

    def test_armar_guia_solo_curso(self):
        texto, tipo = armar_guia_reto_para_prompt(self.curso, None)
        self.assertEqual(tipo, '')
        self.assertIn('PREGUNTAS/RETOS EJEMPLO', texto)
        self.assertIn('gasto revisaría', texto)

    @patch('core.tutor_ia_modulo._get_client')
    def test_generar_reto_inyecta_tipo_y_guia(self, mock_client):
        choice = MagicMock()
        choice.message.content = 'Situación breve. ¿Qué haría usted esta semana?'
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        mock_client.return_value = client

        with patch('core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''):
            out = generar_reto_facilitador(
                [self.m3],
                self.curso.nombre,
                estudiante_nombre='Ana',
                curso=self.curso,
                modulo_checkpoint=self.m3,
            )

        self.assertIn('Situación breve', out)
        kwargs = client.chat.completions.create.call_args.kwargs
        user_msg = kwargs['messages'][1]['content']
        self.assertIn('FORMATO OBLIGATORIO DEL RETO', user_msg)
        self.assertIn('plan concreto', user_msg.lower())
        self.assertIn('plan de 7 días', user_msg)
        self.assertIn('Finanzas del hogar', user_msg)
