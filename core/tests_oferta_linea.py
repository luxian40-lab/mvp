"""La línea de una empresa no muestra cursos ni agentes de otra."""
from django.test import TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, SandboxCanalSesion
from core.planes_linea import PLAN_CURSO_ASESOR
from core.models_extras import GrupoEstudiantes
from core.sandbox_canal import salida_por_phone_id

LINEA = '555666777'


@override_settings(
    WHATSAPP_PHONE_ID='111',
    SANDBOX_WHATSAPP_PHONE_ID='111',
    META_LINEAS='',
)
class OfertaLineaTests(TestCase):
    def setUp(self):
        self.empresa = Cliente.objects.create(
            nombre='Cafeteros del norte',
            contacto_principal='x',
            email='cafe@eki.co',
            telefono='573000000010',
            phone_id_meta=LINEA,
            agentes_linea='coach, ventas',
            activo=True,
        )
        self.ajeno = Curso.objects.create(
            nombre='Curso de otra empresa',
            descripcion='d',
            cliente=None,
            activo=True,
            catalogo_menu=True,
        )
        self.propio = Curso.objects.create(
            nombre='Suelo del cafetal',
            descripcion='d',
            cliente=self.empresa,
            activo=True,
        )

    def test_sin_linea_de_empresa_sigue_el_catalogo_general(self):
        from core.cursos_generales import tarjetas_catalogo

        texto = ' '.join(t['body'] for t in tarjetas_catalogo('573001110077'))
        self.assertIn(self.ajeno.nombre, texto)
        self.assertNotIn(self.propio.nombre, texto)

    def test_en_su_linea_no_sale_el_curso_general(self):
        from core.cursos_generales import inscribir_en_catalogo, tarjetas_catalogo

        self.empresa.plan_linea_meta = PLAN_CURSO_ASESOR
        self.empresa.save(update_fields=['plan_linea_meta'])
        Estudiante.objects.create(
            nombre='A', cedula='OF2', telefono='573001110078', cliente=self.empresa,
            acepto_terminos=True, estado_chat='ACTIVO',
        )
        SandboxCanalSesion.objects.create(telefono='573001110078', habeas_aceptado=True)
        with salida_por_phone_id(LINEA):
            texto = ' '.join(t['body'] for t in tarjetas_catalogo('573001110078'))
            ajeno = inscribir_en_catalogo('573001110078', f'curso_{self.ajeno.id}')
            propio = inscribir_en_catalogo('573001110078', f'curso_{self.propio.id}')
        self.assertIn(self.propio.nombre, texto)
        self.assertNotIn(self.ajeno.nombre, texto)
        self.assertEqual(ajeno['error'], 'otra_empresa')
        self.assertTrue(propio['ok'])

    def test_el_grupo_apaga_un_agente_de_la_empresa(self):
        from core.lineas.oferta import filas_agentes

        est = Estudiante.objects.create(
            nombre='A', cedula='OF1', telefono='573001110077', cliente=self.empresa,
            acepto_terminos=True,
        )
        grupo = GrupoEstudiantes.objects.create(
            nombre='Comercial', cliente=self.empresa, agentes_apagados='coach', activo=True,
        )
        grupo.estudiantes.add(est)
        with salida_por_phone_id(LINEA):
            ids = [fila[0] for fila in filas_agentes(est.telefono)]
        self.assertEqual(ids, ['ventas'])

    def test_la_empresa_elige_generales_y_propios_y_el_grupo_recorta(self):
        from core.cursos_generales import tarjetas_catalogo

        self.empresa.cursos_whatsapp.add(self.ajeno, self.propio)
        est = Estudiante.objects.create(
            nombre='A', cedula='OF3', telefono='573001110079', cliente=self.empresa,
            acepto_terminos=True,
        )
        todos = ' '.join(t['body'] for t in tarjetas_catalogo(est.telefono))
        self.assertIn(self.ajeno.nombre, todos)
        self.assertIn(self.propio.nombre, todos)
        grupo = GrupoEstudiantes.objects.create(
            nombre='Cohorte', cliente=self.empresa, activo=True,
        )
        grupo.cursos.add(self.propio)
        grupo.estudiantes.add(est)
        recorte = ' '.join(t['body'] for t in tarjetas_catalogo(est.telefono))
        self.assertIn(self.propio.nombre, recorte)
        self.assertNotIn(self.ajeno.nombre, recorte)

    def test_mas_de_diez_cursos_salen_en_lista(self):
        from unittest.mock import patch

        from core.sandbox_menu import enviar_catalogo_formacion

        cursos = [
            Curso.objects.create(
                nombre=f'Curso {i:02d} de la finca',
                descripcion='d',
                cliente=self.empresa,
                activo=True,
            )
            for i in range(11)
        ]
        self.empresa.cursos_whatsapp.add(*cursos)
        Estudiante.objects.create(
            nombre='A', cedula='OF4', telefono='573001110080', cliente=self.empresa,
            acepto_terminos=True,
        )
        with patch('core.sandbox_canal.enviar_meta_lista', return_value={'success': True}) as lista, \
                patch('core.sandbox_canal.enviar_meta_carrusel') as carrusel:
            enviar_catalogo_formacion('573001110080', 'whatsapp:+100')
        self.assertEqual(lista.call_count, 2)
        carrusel.assert_not_called()
        primera = [fila[0] for fila in lista.call_args_list[0].args[3]]
        self.assertEqual(len(primera), 10)

    def test_tres_agentes_salen_en_lista(self):
        from unittest.mock import patch

        from core.lineas.oferta import filas_agentes
        from core.sandbox_menu import enviar_menu_agentes

        self.empresa.agentes_linea = 'nat, coach, profe'
        self.empresa.save(update_fields=['agentes_linea'])
        est = Estudiante.objects.create(
            nombre='A', cedula='OF5', telefono='573001110081', cliente=self.empresa,
            acepto_terminos=True,
        )
        self.assertEqual([fila[0] for fila in filas_agentes(est.telefono)], ['nat', 'coach', 'profe'])
        with patch('core.sandbox_canal.enviar_meta_lista', return_value={'success': True}) as lista, \
                patch('core.sandbox_canal.enviar_meta_botones') as botones:
            enviar_menu_agentes(est.telefono, 'whatsapp:+100')
        lista.assert_called_once()
        botones.assert_not_called()
        self.assertEqual(len(lista.call_args.args[3]), 3)
