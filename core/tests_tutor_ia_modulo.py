from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import Cliente, Curso, Modulo
from core.tutor_ia_modulo import (
    RETO_GUIA_DEFAULT,
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

    def test_armar_guia_sin_tipo_ni_guia_usa_default(self):
        """Impulso 22: módulo y curso sin guía → tipo aplicación + guía genérica."""
        self.curso.preguntas_ejemplo_ia = ''
        self.curso.save(update_fields=['preguntas_ejemplo_ia'])
        m = Modulo.objects.create(
            curso=self.curso,
            numero=5,
            titulo='ideas a negocios',
            contenido='De idea a oferta.',
            tipo_reto_ia='',
            reto_guia_ia='',
        )
        texto, tipo = armar_guia_reto_para_prompt(self.curso, m)
        self.assertEqual(tipo, Modulo.TIPO_RETO_APLICACION)
        self.assertIn('GUÍA POR DEFECTO', texto)
        self.assertIn(RETO_GUIA_DEFAULT[:40], texto)

    def test_armar_guia_no_pisa_guia_del_instructor_con_default(self):
        texto, tipo = armar_guia_reto_para_prompt(self.curso, self.m3)
        self.assertEqual(tipo, Modulo.TIPO_RETO_PLAN)
        self.assertNotIn('GUÍA POR DEFECTO', texto)
        self.assertIn('plan de 7 días', texto)

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
        self.assertEqual(tipo, Modulo.TIPO_RETO_APLICACION)
        self.assertNotIn('GUÍA POR DEFECTO', texto)
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

    def _prompt_reto(self, modulos, checkpoint, **kwargs):
        choice = MagicMock()
        choice.message.content = 'Situación. ¿Qué haría?'
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        with patch('core.tutor_ia_modulo._get_client', return_value=client), \
                patch('core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''):
            generar_reto_facilitador(
                modulos, self.curso.nombre, estudiante_nombre='Ana',
                curso=self.curso, modulo_checkpoint=checkpoint, **kwargs,
            )
        return client.chat.completions.create.call_args.kwargs['messages'][1]['content']

    def test_plantilla_aplicacion_no_asume_finca(self):
        from core.tutor_ia_modulo import _INSTRUCCION_TIPO_RETO

        texto = _INSTRUCCION_TIPO_RETO[Modulo.TIPO_RETO_APLICACION]
        self.assertNotIn('finca', texto.lower())
        self.assertIn('negocio', texto)
        self.assertIn('según el curso', texto)

    def test_reto_se_centra_en_el_modulo_que_cierra(self):
        m2 = Modulo.objects.create(curso=self.curso, numero=2, titulo='Ahorro semanal', contenido='Guardar.')
        user_msg = self._prompt_reto([m2, self.m3], self.m3)
        self.assertIn('Centre la situación en el módulo 3 (Presupuesto semanal)', user_msg)

    def test_reto_de_un_solo_modulo_no_agrega_foco(self):
        self.assertNotIn('Centre la situación', self._prompt_reto([self.m3], self.m3))

    def test_reto_no_repite_los_que_ya_recibio(self):
        from core.models import Estudiante
        from core.telemetria import registrar_reto_planteado

        est = Estudiante.objects.create(nombre='Ana', telefono='573001110098', cedula='9001110098', cliente=self.cli)
        otro = Estudiante.objects.create(nombre='Luis', telefono='573001110097', cedula='9001110097', cliente=self.cli)
        registrar_reto_planteado(est, curso=self.curso, modulo=self.m3, reto_texto='Reto viejo de la feria.')
        registrar_reto_planteado(otro, curso=self.curso, modulo=self.m3, reto_texto='Reto de otra persona.')
        user_msg = self._prompt_reto([self.m3], self.m3, estudiante=est)
        self.assertIn('RETOS QUE YA RECIBIÓ', user_msg)
        self.assertIn('Reto viejo de la feria.', user_msg)
        self.assertNotIn('Reto de otra persona.', user_msg)

    def test_reto_respondido_cuenta_y_no_se_repite_en_la_lista(self):
        from core.models import Estudiante
        from core.telemetria import registrar_reto_planteado, registrar_reto_respondido

        est = Estudiante.objects.create(nombre='Ana', telefono='573001110096', cedula='9001110096', cliente=self.cli)
        registrar_reto_planteado(est, curso=self.curso, modulo=self.m3, reto_texto='Reto de la tienda.')
        registrar_reto_respondido(est, curso=self.curso, modulo=self.m3, reto_texto='Reto de la tienda.')
        registrar_reto_respondido(est, curso=self.curso, modulo=self.m3, reto_texto='Reto del mercado.')
        user_msg = self._prompt_reto([self.m3], self.m3, estudiante=est)
        self.assertEqual(user_msg.count('Reto de la tienda.'), 1)
        self.assertIn('Reto del mercado.', user_msg)

    def test_sin_estudiante_no_hay_bloque_de_retos_previos(self):
        self.assertNotIn('RETOS QUE YA RECIBIÓ', self._prompt_reto([self.m3], self.m3))


class AsistenteDominioCursoTests(TestCase):
    """Carlos no debe recortar el tema al título del módulo (ej. Bienvenida)."""

    def test_prompt_sistema_ustea_sin_emojis(self):
        from core.tutor_ia_modulo import _prompt_sistema_asistente

        p = _prompt_sistema_asistente('Carlos')
        self.assertIn('Carlos', p)
        self.assertIn('TRATO DE USTED', p)
        self.assertNotIn('TUTEA', p)
        self.assertIn('PROHIBIDO usar emojis', p)
        self.assertIn('dominio del curso', p.lower())

    def test_respuestas_caben_en_un_mensaje_con_boton(self):
        from core.tutor_ia_modulo import (
            PROMPT_FACILITADOR_EVALUACION,
            PROMPT_FACILITADOR_EVALUACION_NOTAS,
            _prompt_sistema_asistente,
        )

        self.assertIn('Máximo 120 palabras', _prompt_sistema_asistente('Carlos'))
        self.assertIn('Máximo 90 palabras de retroalimentación', PROMPT_FACILITADOR_EVALUACION)
        self.assertIn('Máximo 90 palabras', PROMPT_FACILITADOR_EVALUACION_NOTAS)

    @patch('core.tutor_ia_modulo._get_client')
    def test_pregunta_de_abejas_usa_el_curso_aunque_el_modulo_sea_bienvenida(self, mock_client):
        from core.prompts_tecnicoagro import PERFIL_TECNICOAGRO
        from core.tutor_ia_modulo import generar_respuesta_asistente

        cli = Cliente.objects.create(
            nombre='AGROSAVIA',
            contacto_principal='A',
            email='agro@test.co',
            telefono='573001110088',
            perfil_facilitador=PERFIL_TECNICOAGRO,
        )
        curso = Curso.objects.create(
            nombre='Identificación y Toma de Muestras en Apiarios',
            cliente=cli,
            descripcion='Manejo sanitario y muestreo en colmenas.',
            perfil_facilitador=PERFIL_TECNICOAGRO,
        )
        m1 = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='Bienvenida',
            contenido='Presentación del programa.',
        )
        choice = MagicMock()
        choice.message.content = 'En un apiario revise la piquera y el estado de la cría. 🐝'
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        mock_client.return_value = client

        with patch(
            'core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''
        ), patch(
            'core.agrosavia_connector.enriquecer_contexto_con_agrosavia',
            return_value=('FUENTE AGROSAVIA: varroa en colmenas', {'agrosavia_usada': True}),
        ) as mock_agro:
            out = generar_respuesta_asistente(
                [m1],
                'que puedo saber de cuidado de abejas en ese caso',
                estudiante_nombre='Julian',
                nombre_asistente='Carlos',
            )

        mock_agro.assert_called()
        kwargs = client.chat.completions.create.call_args.kwargs
        user_msg = kwargs['messages'][1]['content']
        self.assertIn('Identificación y Toma de Muestras en Apiarios', user_msg)
        self.assertIn('cuidado de abejas', user_msg.lower())
        self.assertNotIn('SOLO en el contenido de los módulos', user_msg)
        self.assertNotIn('🐝', out)
