"""Flujo WhatsApp B2B: sin menú 1-2-3; avance con listo y orden por campaña."""
from django.test import TestCase

from core.correccion_datos import construir_menu_principal_texto
from core.flujo_whatsapp_b2b import (
    es_estudiante_b2b,
    mensaje_curso_por_campana,
    salir_seleccion_curso_legacy,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent


class FlujoWhatsappB2BTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Cooperativa Test')
        self.curso = Curso.objects.create(
            nombre='Cultivo Básico',
            cliente=self.cliente,
            activo=True,
            emoji='🌱',
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Intro',
            descripcion='D',
            contenido='Contenido',
        )
        self.est_b2b = Estudiante.objects.create(
            cedula='900100200',
            nombre='Ana B2B',
            telefono='573001002003',
            cliente=self.cliente,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est_b2b,
            curso=self.curso,
            completado=False,
        )
        self.est_sandbox = Estudiante.objects.create(
            cedula='900100201',
            nombre='Luis Sandbox',
            telefono='573001002004',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )

    def test_es_estudiante_b2b(self):
        self.assertTrue(es_estudiante_b2b(self.est_b2b))
        self.assertFalse(es_estudiante_b2b(self.est_sandbox))

    def test_saludo_b2b_sin_menu_numerado(self):
        msg = get_response_for_intent(
            'saludo', self.est_b2b.nombre, estudiante_id=self.est_b2b.id
        )
        self.assertIn('listo', msg.lower())
        self.assertNotIn('1️⃣', msg)
        self.assertNotIn('Escribe el número (1, 2 o 3)', msg)

    def test_saludo_sandbox_conserva_menu(self):
        msg = get_response_for_intent(
            'saludo', self.est_sandbox.nombre, estudiante_id=self.est_sandbox.id
        )
        self.assertIn('1️⃣', msg)
        self.assertIn('2️⃣', msg)

    def test_opcion_2_b2b_un_curso_sin_lista(self):
        msg = get_response_for_intent(
            'opcion_2', self.est_b2b.nombre, estudiante_id=self.est_b2b.id
        )
        self.assertIn('campaña', msg.lower())
        self.assertIn('listo', msg.lower())
        self.assertNotIn('Escribe el *número*', msg)
        self.est_b2b.refresh_from_db()
        self.assertNotEqual(self.est_b2b.estado_onboarding, 'esperando_seleccion_curso')

    def test_opcion_numerica_b2b_un_curso_redirige_a_listo(self):
        msg = get_response_for_intent(
            'opcion_numerica',
            self.est_b2b.nombre,
            estudiante_id=self.est_b2b.id,
            mensaje_original='2',
        )
        self.assertIn('Cultivo Básico', msg)
        self.assertIn('listo', msg.lower())

    def test_b2b_dos_cursos_opcion_2_muestra_menu(self):
        curso2 = Curso.objects.create(
            nombre='Poda Avanzada',
            cliente=self.cliente,
            activo=True,
            emoji='✂️',
        )
        Modulo.objects.create(
            curso=curso2, numero=1, titulo='Intro 2', descripcion='D', contenido='C'
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est_b2b, curso=curso2, completado=False
        )
        msg = get_response_for_intent(
            'opcion_2', self.est_b2b.nombre, estudiante_id=self.est_b2b.id
        )
        self.assertIn('Cultivo Básico', msg)
        self.assertIn('Poda Avanzada', msg)
        self.assertIn('número', msg.lower())
        self.est_b2b.refresh_from_db()
        self.assertEqual(self.est_b2b.estado_onboarding, 'esperando_seleccion_curso')

    def test_construir_menu_b2b_usa_comandos(self):
        msg = construir_menu_principal_texto(self.est_b2b)
        self.assertIn('*listo*', msg)
        self.assertNotIn('1️⃣', msg)

    def test_salir_seleccion_curso_legacy(self):
        self.est_b2b.estado_onboarding = 'esperando_seleccion_curso'
        self.est_b2b.contexto_temporal = {'tipo': 'seleccion_curso'}
        self.est_b2b.save()
        salir_seleccion_curso_legacy(self.est_b2b)
        self.est_b2b.refresh_from_db()
        self.assertEqual(self.est_b2b.estado_onboarding, 'completado')
        self.assertIsNone(self.est_b2b.contexto_temporal)

    def test_mensaje_curso_por_campana(self):
        msg = mensaje_curso_por_campana(self.est_b2b)
        self.assertIn('Cultivo Básico', msg)
        self.assertIn('listo', msg.lower())
