"""Perfil facilitador Claudia vs tecnicoagro + tope WA."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.facilitador_perfil import (
    es_perfil_tecnicoagro,
    nombre_display_facilitador,
    resolver_perfil_facilitador,
    system_prompt_reto_para_curso,
)
from core.models import Cliente, Curso, Modulo
from core.modulo_publicacion import resumen_tope_avance_wa
from core.prompts_tecnicoagro import PERFIL_CLAUDIA, PERFIL_TECNICOAGRO, PROMPT_TECNICOAGRO
from core.tutor_ia_modulo import PROMPT_FACILITADOR_RETO, generar_reto_facilitador


class FacilitadorPerfilTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org Agro', activo=True)
        self.curso = Curso.objects.create(
            nombre='Abejas AGROSAVIA',
            cliente=self.cliente,
            activo=True,
        )

    def test_default_es_claudia(self):
        self.assertEqual(resolver_perfil_facilitador(self.curso), PERFIL_CLAUDIA)
        self.assertFalse(es_perfil_tecnicoagro(self.curso))
        self.assertIn('Facilitadora', PROMPT_FACILITADOR_RETO)
        self.assertEqual(system_prompt_reto_para_curso(self.curso), PROMPT_FACILITADOR_RETO)

    def test_cliente_tecnicoagro_hereda(self):
        self.cliente.perfil_facilitador = Cliente.PERFIL_FACILITADOR_TECNICOAGRO
        self.cliente.save(update_fields=['perfil_facilitador'])
        self.assertEqual(resolver_perfil_facilitador(self.curso), PERFIL_TECNICOAGRO)
        self.assertTrue(es_perfil_tecnicoagro(self.curso))
        prompt = system_prompt_reto_para_curso(self.curso)
        self.assertIn('COPILOTO TÉCNICO', prompt)
        self.assertIn('MICRO-RETO', prompt)
        self.assertIn(PROMPT_TECNICOAGRO[:40], prompt)

    def test_curso_override_claudia_aunque_cliente_tecnicoagro(self):
        self.cliente.perfil_facilitador = Cliente.PERFIL_FACILITADOR_TECNICOAGRO
        self.cliente.save(update_fields=['perfil_facilitador'])
        self.curso.perfil_facilitador = Curso.PERFIL_FACILITADOR_CLAUDIA
        self.curso.save(update_fields=['perfil_facilitador'])
        self.assertEqual(resolver_perfil_facilitador(self.curso), PERFIL_CLAUDIA)

    def test_nombre_display_tecnicoagro(self):
        self.curso.perfil_facilitador = Curso.PERFIL_FACILITADOR_TECNICOAGRO
        self.curso.save(update_fields=['perfil_facilitador'])
        self.assertEqual(nombre_display_facilitador(self.curso), 'Copiloto técnico')
        self.curso.nombre_agente_tutor = 'Extensión Abejas'
        self.curso.save(update_fields=['nombre_agente_tutor'])
        self.assertEqual(nombre_display_facilitador(self.curso), 'Extensión Abejas')

    def test_claudia_prompts_intactos(self):
        """No borrar Claudia: constantes siguen existiendo."""
        self.assertIn('Facilitadora Claudia', __import__('core.tutor_ia_modulo', fromlist=['PROMPT_FACILITADOR_EVALUACION']).PROMPT_FACILITADOR_EVALUACION)

    @patch('core.tutor_ia_modulo._get_client')
    def test_generar_reto_usa_prompt_tecnicoagro(self, mock_client):
        self.curso.perfil_facilitador = Curso.PERFIL_FACILITADOR_TECNICOAGRO
        self.curso.save(update_fields=['perfil_facilitador'])
        m = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Sanidad apícola',
            contenido='Varroa y manejo integrado.',
            publicado_wa=True,
        )
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='🌱 RETO DE CAMPO\nHoy: revise 5 colmenas.\nEscriba o envíe un audio con su respuesta.'))]
        )
        mock_client.return_value = fake
        generar_reto_facilitador([m], self.curso.nombre, curso=self.curso, modulo_checkpoint=m)
        args, kwargs = fake.chat.completions.create.call_args
        system = kwargs['messages'][0]['content']
        self.assertIn('COPILOTO TÉCNICO', system)
        self.assertIn('CHECKPOINT DEL CURSO', system)

    @patch(
        'core.agrosavia_connector.enriquecer_contexto_con_agrosavia',
        return_value=('FUENTE AGROSAVIA: manejo de varroa en apiarios', {'agrosavia_usada': True}),
    )
    @patch('core.tutor_ia_modulo._get_client')
    def test_tecnicoagro_usa_agrosavia_live_cuando_no_hay_rag(self, mock_client, mock_agro):
        self.curso.perfil_facilitador = Curso.PERFIL_FACILITADOR_TECNICOAGRO
        self.curso.save(update_fields=['perfil_facilitador'])
        m = Modulo.objects.create(
            curso=self.curso,
            numero=5,
            titulo='Toma de muestras en apiarios',
            contenido='Muestreo de abejas adultas.',
            publicado_wa=True,
        )
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='🌱 RETO DE CAMPO\nHoy: revise 10 colmenas.'))]
        )
        mock_client.return_value = fake

        generar_reto_facilitador([m], self.curso.nombre, curso=self.curso, modulo_checkpoint=m)

        mock_agro.assert_called_once()
        _args, kwargs = fake.chat.completions.create.call_args
        user_msg = kwargs['messages'][1]['content']
        self.assertIn('FUENTE AGROSAVIA', user_msg)

    @patch('core.agrosavia_connector.enriquecer_contexto_con_agrosavia')
    @patch('core.tutor_ia_modulo._get_client')
    def test_claudia_no_consulta_agrosavia(self, mock_client, mock_agro):
        m = Modulo.objects.create(
            curso=self.curso,
            numero=6,
            titulo='Finanzas del hogar',
            contenido='Presupuesto.',
            publicado_wa=True,
        )
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='Reto breve.'))]
        )
        mock_client.return_value = fake

        generar_reto_facilitador([m], self.curso.nombre, curso=self.curso, modulo_checkpoint=m)

        mock_agro.assert_not_called()


class TopeWhatsappResumenTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org Tope', activo=True)
        self.curso = Curso.objects.create(nombre='Curso tope', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Uno', contenido='a', publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Dos', contenido='b', publicado_wa=True,
        )
        self.m3 = Modulo.objects.create(
            curso=self.curso, numero=3, titulo='Tres', contenido='c', publicado_wa=False,
        )
        self.m4 = Modulo.objects.create(
            curso=self.curso, numero=4, titulo='Cuatro', contenido='d', publicado_wa=False,
        )

    def test_resumen_hasta_m2_si_m3_pausado(self):
        info = resumen_tope_avance_wa(self.curso)
        self.assertEqual(info['activo_hasta_numero'], 2)
        self.assertIn('M2', info['texto_admin'])
        self.assertGreaterEqual(info['pausados_despues'], 2)

    def test_etiqueta_publicado_wa_es_activo(self):
        field = Modulo._meta.get_field('publicado_wa')
        self.assertEqual(field.verbose_name, 'Activo en WhatsApp')
