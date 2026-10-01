"""WhatsApp Flow de Preserva, armado desde los pasos, con el chat como respaldo."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, Modulo
from core.sandbox_canal import canal_sandbox_meta, inbound_desde_meta_message
from formulario.agent import iniciar_sesion_formulario, manejar_mensaje_formulario
from formulario.flow_gei import MARCA_FLOW, aplicar_respuestas_flow, flow_json
from formulario.models import FichaGEI, FlujoPregunta, SesionFormulario, TipoFormulario


def _paso(**kwargs):
    base = {
        'orden': 1,
        'campo_destino': 'nombre_finca',
        'pregunta_texto': '¿Cómo se llama su finca?',
        'tipo_dato': 'text',
        'es_opcional': False,
    }
    base.update(kwargs)
    return FlujoPregunta(**base)


class FlowJsonTests(TestCase):
    def test_arma_controles_de_texto_numero_si_no_y_lista(self):
        doc = flow_json([
            _paso(orden=1, campo_destino='nombre_finca', tipo_dato='text', pregunta_texto='Nombre de la finca'),
            _paso(orden=2, campo_destino='area_ha', tipo_dato='float', pregunta_texto='¿Cuántas hectáreas tiene?'),
            _paso(orden=3, campo_destino='alta_mecanizacion', tipo_dato='bool', pregunta_texto='¿Usa maquinaria?'),
            _paso(
                orden=4, campo_destino='tipo_combustible', tipo_dato='choice',
                opciones_choice='diesel|gasolina', pregunta_texto='¿Qué combustible usa?',
            ),
        ])
        self.assertIsNotNone(doc)
        self.assertEqual(len(doc['screens']), 2)
        primera = doc['screens'][0]['layout']['children'][0]['children']
        tipos = [h['type'] for h in primera]
        self.assertIn('TextInput', tipos)
        self.assertIn('RadioButtonsGroup', tipos)
        self.assertEqual(primera[-1]['on-click-action']['name'], 'navigate')
        ultima = doc['screens'][1]['layout']['children'][0]['children']
        self.assertEqual(ultima[-1]['on-click-action']['name'], 'complete')
        self.assertIn('tipo_combustible', ultima[-1]['on-click-action']['payload'])
        self.assertIn('nombre_finca', ultima[-1]['on-click-action']['payload'])

    def test_siete_pasos_salen_en_tres_pantallas(self):
        pasos = [
            _paso(orden=i, campo_destino=f'campo_{i}', pregunta_texto=f'Pregunta {i}')
            for i in range(1, 8)
        ]
        doc = flow_json(pasos)
        self.assertEqual([s['id'] for s in doc['screens']], ['S1', 'S2', 'S3'])
        self.assertEqual(doc['screens'][0]['layout']['children'][0]['children'][-1]['on-click-action']['next']['name'], 'S2')

    def test_campo_invalido_no_arma_el_flow(self):
        self.assertIsNone(flow_json([_paso(campo_destino='1malo')]))


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    WHATSAPP_TOKEN='test-token',
    WHATSAPP_PHONE_ID='111',
    WHATSAPP_BUSINESS_ACCOUNT_ID='',
    SECURE_SSL_REDIRECT=False,
)
class FlowSesionTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Preserva', contacto_principal='A', email='p@eki.co', telefono='573001112200',
        )
        self.curso = Curso.objects.create(nombre='GEI', descripcion='d', cliente=self.org, activo=True)
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=4, titulo='Ficha', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            nombre='Ana', cedula='P900', telefono='573001112244', cliente=self.org, activo=True,
        )
        self.tipo = TipoFormulario.objects.create(
            nombre='Finca', curso=self.curso, modulo=self.mod, cliente=self.org, activo=True,
        )
        FlujoPregunta.objects.create(
            formulario=self.tipo, orden=1, campo_destino='nombre_finca',
            pregunta_texto='¿Cómo se llama su finca?', tipo_dato='text',
        )
        FlujoPregunta.objects.create(
            formulario=self.tipo, orden=2, campo_destino='area_ha',
            pregunta_texto='¿Cuántas hectáreas?', tipo_dato='float',
        )
        FlujoPregunta.objects.create(
            formulario=self.tipo, orden=3, campo_destino='notas_extra',
            pregunta_texto='Algo más', tipo_dato='text', es_opcional=True,
        )

    def _sesion(self):
        ficha = FichaGEI.objects.create(estudiante=self.est, cliente=self.org, curso=self.curso)
        return SesionFormulario.objects.create(
            estudiante=self.est, formulario=self.tipo, ficha=ficha, paso_actual=0,
        )

    def test_el_flow_llena_la_ficha_y_cierra(self):
        sesion = self._sesion()
        texto = aplicar_respuestas_flow(sesion, {
            'nombre_finca': 'La Esperanza',
            'area_ha': '2.5',
        })
        sesion.refresh_from_db()
        sesion.ficha.refresh_from_db()
        self.assertTrue(sesion.completado)
        self.assertEqual(sesion.ficha.nombre_finca, 'La Esperanza')
        self.assertEqual(sesion.ficha.area_ha, 2.5)
        self.assertIn('concluimos', texto)

    def test_si_falta_un_obligatorio_sigue_en_el_chat(self):
        sesion = self._sesion()
        texto = aplicar_respuestas_flow(sesion, {'nombre_finca': 'La Esperanza'})
        sesion.refresh_from_db()
        self.assertFalse(sesion.completado)
        self.assertEqual(sesion.paso_actual, 1)
        self.assertIn('Pregunta 2 de 3', texto)
        self.assertEqual(sesion.ficha.nombre_finca, 'La Esperanza')

    def test_el_chat_de_una_en_una_sigue_andando(self):
        sesion = self._sesion()
        texto = manejar_mensaje_formulario(self.est, 'La Esperanza')
        sesion.refresh_from_db()
        self.assertFalse(sesion.completado)
        self.assertEqual(sesion.paso_actual, 1)
        self.assertIn('Pregunta 2 de 3', texto)

    def test_respuesta_del_flow_entra_por_el_mismo_chat(self):
        self._sesion()
        cuerpo = MARCA_FLOW + '{"nombre_finca":"El Roble","area_ha":"4"}'
        texto = manejar_mensaje_formulario(self.est, cuerpo)
        ficha = FichaGEI.objects.get(estudiante=self.est)
        self.assertEqual(ficha.nombre_finca, 'El Roble')
        self.assertEqual(ficha.area_ha, 4)
        self.assertIn('concluimos', texto)

    def test_sin_flow_publicado_la_primera_pregunta_sale_en_el_chat(self):
        with canal_sandbox_meta():
            msg = iniciar_sesion_formulario(self.est, self.tipo)
        self.assertIn('Pregunta 1 de 3', msg)
        self.assertNotIn('Si el formulario no abre', msg)

    def test_con_flow_publicado_manda_el_formulario_y_deja_el_chat(self):
        self.tipo.meta_flow_id = '999'
        self.tipo.save(update_fields=['meta_flow_id'])
        with canal_sandbox_meta(), patch(
            'core.sandbox_canal._post_graph',
            return_value={'success': True, 'mensaje_id': 'wamid.flow'},
        ) as post:
            msg = iniciar_sesion_formulario(self.est, self.tipo)
        self.assertIn('Si el formulario no abre', msg)
        self.assertIn('Pregunta 1 de 3', msg)
        payload = post.call_args.args[0]
        self.assertEqual(payload['interactive']['type'], 'flow')
        self.assertEqual(payload['interactive']['action']['parameters']['flow_id'], '999')
        self.assertEqual(payload['interactive']['action']['parameters']['flow_cta'], 'Llenar ficha')

    def test_webhook_meta_reconoce_el_formulario(self):
        inbound = inbound_desde_meta_message(
            {
                'from': '573001112244',
                'id': 'wamid.1',
                'type': 'interactive',
                'interactive': {
                    'type': 'nfm_reply',
                    'nfm_reply': {'response_json': '{"nombre_finca":"La Esperanza"}'},
                },
            },
            {'metadata': {'display_phone_number': '14155238886', 'phone_number_id': '111'}},
        )
        self.assertTrue(inbound['Body'].startswith(MARCA_FLOW))
        self.assertIn('La Esperanza', inbound['Body'])
