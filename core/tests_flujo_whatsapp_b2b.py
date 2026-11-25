"""Flujo WhatsApp B2B: sin menú 1-2-3; avance con listo y orden por campaña."""
from unittest.mock import patch

from django.test import TestCase

from core.conversacion.correccion_datos import construir_menu_principal_texto
from core.conversacion.flujo_whatsapp_b2b import (
    es_estudiante_b2b,
    mensaje_curso_por_campana,
    respuesta_tras_keyword_menu,
    salir_seleccion_curso_legacy,
)
from core.lineas.meta import LineaMeta
from core.lineas.perfil import (
    PERFIL_COMPLETA,
    PERFIL_SOLO_CURSOS,
    USO_COMPLETA,
    USO_SOLO_CURSOS,
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
        self.assertIn('[send_button:continuemos]', msg.lower())
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
        self.assertIn('[send_button:continuemos]', msg.lower())
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
        self.assertIn('[send_button:continuemos]', msg.lower())

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
        self.assertIn('*Continuemos*', msg)
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
        self.assertIn('[send_button:continuemos]', msg.lower())

    def test_menu_b2b_con_activo_sigue_continuar_leccion(self):
        with patch('core.lineas.variante.perfil_de', return_value=PERFIL_COMPLETA):
            msg = respuesta_tras_keyword_menu(self.est_b2b, self.est_b2b.nombre, 'menu')
        self.assertIn('Cultivo Básico', msg)
        self.assertNotIn('Ya completaste', msg)
        self.assertNotIn('línea principal', msg.lower())
        self.assertNotIn('1️⃣', msg)

    def test_menu_b2b_sin_activos_en_principal_abre_menu_plataforma(self):
        ProgresoEstudiante.objects.filter(estudiante=self.est_b2b).update(completado=True)
        with patch('core.lineas.variante.perfil_de', return_value=PERFIL_COMPLETA):
            msg = respuesta_tras_keyword_menu(self.est_b2b, self.est_b2b.nombre, 'menu')
        self.assertNotIn('Ya completaste', msg)
        self.assertIn('1️⃣', msg)
        self.assertIn('Explorar cursos', msg)

    def test_menu_b2b_sin_activos_linea2_handoff_sin_asesores(self):
        ProgresoEstudiante.objects.filter(estudiante=self.est_b2b).update(completado=True)
        principal = LineaMeta('pid-1', '573001111111', 'Principal', uso=USO_COMPLETA)
        linea2 = LineaMeta('pid-2', '573009536193', 'Línea 2', uso=USO_SOLO_CURSOS)
        with patch('core.lineas.variante.perfil_de', return_value=PERFIL_SOLO_CURSOS), patch(
            'core.lineas.variante.lineas_producto', return_value=(principal, linea2),
        ):
            msg = respuesta_tras_keyword_menu(self.est_b2b, self.est_b2b.nombre, 'Menú')
        self.assertNotIn('Ya completaste', msg)
        self.assertIn('573001111111', msg)
        self.assertIn('*ayuda*', msg)
        self.assertIn('línea principal', msg.lower())
        self.assertNotIn('1️⃣', msg)
        self.assertNotIn('[SEND_BUTTON:continuemos]', msg)
