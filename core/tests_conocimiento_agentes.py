"""Entrenar agentes desde el admin + admin de planes sin 500."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from core.conocimiento_agentes import bloque_conocimiento, capturar_sugerencia
from core.models import Cliente, SandboxCanalSesion
from core.models_agentes import ConocimientoAgente


class ConocimientoAgenteTests(TestCase):
    def setUp(self):
        cache.clear()

    def _crear(self, **kw):
        datos = dict(agente='ventas', titulo='Precio justo', contenido='Calcule costo antes de bajar precio.')
        datos.update(kw)
        return ConocimientoAgente.objects.create(**datos)

    def test_solo_aprobado_y_del_agente_entra_al_prompt(self):
        self._crear()
        self._crear(titulo='Sugerida', contenido='texto de usuario', estado=ConocimientoAgente.ESTADO_SUGERIDO)
        self._crear(agente='coach', titulo='De coach', contenido='solo coach')
        self._crear(agente='todos', tipo='instruccion', titulo='Tono', contenido='Hable de usted.')
        bloque = bloque_conocimiento('ventas')
        self.assertIn('Precio justo', bloque)
        self.assertIn('REGLAS ADICIONALES', bloque)
        self.assertIn('Hable de usted.', bloque)
        self.assertNotIn('Sugerida', bloque)
        self.assertNotIn('solo coach', bloque)

    def test_aprobar_se_ve_sin_esperar_cache(self):
        self.assertEqual(bloque_conocimiento('coach'), '')
        fila = self._crear(agente='coach', estado=ConocimientoAgente.ESTADO_SUGERIDO)
        self.assertEqual(bloque_conocimiento('coach'), '')
        fila.estado = ConocimientoAgente.ESTADO_APROBADO
        fila.save()
        self.assertIn('Precio justo', bloque_conocimiento('coach'))

    def test_prompt_cacheado_no_consulta_db_por_mensaje(self):
        self._crear()
        bloque_conocimiento('ventas')
        with self.assertNumQueries(0):
            bloque_conocimiento('ventas')

    def test_llm_recibe_el_conocimiento_en_el_system_prompt(self):
        self._crear()
        falso = MagicMock()
        falso.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content='ok'))]
        with override_settings(OPENAI_API_KEY='sk-test'), patch('openai.OpenAI', return_value=falso):
            from core.sandbox_agentes import responder_agente_sandbox

            responder_agente_sandbox('ventas', '¿cómo subo el precio?', telefono='573001')
        sistema = falso.chat.completions.create.call_args.kwargs['messages'][0]['content']
        self.assertIn('Precio justo', sistema)

    @override_settings(AGENTES_CAPTURA_PORCENTAJE=100)
    def test_captura_sugerencia_sin_datos_personales_y_sin_duplicar(self):
        pregunta = 'Me llamo Ana, mi cel es 3001234567 y correo ana@finca.co, ¿cómo cobro más por el café?'
        capturar_sugerencia('ventas', pregunta, 'Primero calcule su costo por kilo.')
        capturar_sugerencia('ventas', pregunta, 'Otra respuesta.')
        filas = ConocimientoAgente.objects.filter(origen='conversacion')
        self.assertEqual(filas.count(), 1)
        fila = filas.get()
        self.assertEqual(fila.estado, ConocimientoAgente.ESTADO_SUGERIDO)
        self.assertNotIn('3001234567', fila.pregunta_origen)
        self.assertNotIn('ana@finca.co', fila.pregunta_origen)
        self.assertNotIn('Primero calcule', bloque_conocimiento('ventas'))

    @override_settings(AGENTES_CAPTURA_PORCENTAJE=0)
    def test_captura_apagada(self):
        capturar_sugerencia('ventas', 'x' * 60, 'respuesta')
        self.assertFalse(ConocimientoAgente.objects.exists())

    @override_settings(AGENTES_CAPTURA_PORCENTAJE=100)
    def test_preguntas_cortas_no_se_capturan(self):
        capturar_sugerencia('coach', 'hola', 'Hola, ¿en qué le ayudo?')
        self.assertFalse(ConocimientoAgente.objects.exists())


@override_settings(ALLOWED_HOSTS=['testserver', 'admin.eki.technology'], SECURE_SSL_REDIRECT=False)
class AdminPlanesYAgentesSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('plan_smoke', 'p@eki.test', 'PlanSmoke2026!')
        cls.cliente = Cliente.objects.create(
            nombre='Org Plan', contacto_principal='x', email='o@eki.co', telefono='573', plan_linea_meta='dos_cursos'
        )
        cls.sesion = SandboxCanalSesion.objects.create(telefono='573009990000', plan='asesor_60', racha_actual=4)
        cls.fila = ConocimientoAgente.objects.create(
            agente='coach', titulo='Tema', contenido='c', estado=ConocimientoAgente.ESTADO_SUGERIDO
        )

    def setUp(self):
        self.client = Client(HTTP_HOST='admin.eki.technology')
        self.assertTrue(self.client.login(username='plan_smoke', password='PlanSmoke2026!'))

    def test_paginas_admin_responden(self):
        rutas = [
            '/admin/core/cliente/',
            '/admin/core/cliente/?plan_linea_meta__exact=dos_cursos',
            f'/admin/core/cliente/{self.cliente.pk}/change/',
            '/admin/core/sandboxcanalsesion/',
            f'/admin/core/sandboxcanalsesion/{self.sesion.pk}/change/',
            '/admin/core/conocimientoagente/',
            '/admin/core/conocimientoagente/add/',
            f'/admin/core/conocimientoagente/{self.fila.pk}/change/',
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta, follow=True).status_code, 200)

    def test_ficha_cliente_muestra_plan(self):
        r = self.client.get(f'/admin/core/cliente/{self.cliente.pk}/change/')
        self.assertContains(r, 'plan_linea_meta')

    def test_accion_aprobar(self):
        self.client.post(
            '/admin/core/conocimientoagente/',
            {'action': 'aprobar', '_selected_action': [self.fila.pk]},
        )
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, ConocimientoAgente.ESTADO_APROBADO)
        self.assertEqual(self.fila.revisado_por_id, self.user.pk)
