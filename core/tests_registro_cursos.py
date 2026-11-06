"""El carrusel de la línea 3 es el del enlace, no el de la línea principal."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.lineas.registro_abrir import abrir_registro
from core.lineas.registro_cursos import atender_cursos, modo_de_oferta
from core.sandbox_canal import salida_por_phone_id

class _Ficha:
    def __init__(self):
        self.id = 3
        self.nombre = 'Ana'
        self.contexto_temporal = {}

    def save(self, update_fields=None):
        self.guardado = update_fields


PHONE = '1477762615411333'
PRINCIPAL = '111'

AJUSTES = dict(
    EKI_LINEA_REGISTRO_PHONE_ID=PHONE,
    EKI_LINEA_REGISTRO_E164='573019018929',
    EKI_LINEA_REGISTRO_WABA_ID='1560693046090506',
    EKI_LINEA_REGISTRO_FLOW_ID='1644555950738838',
    SANDBOX_WHATSAPP_PHONE_ID=PRINCIPAL,
    WHATSAPP_PHONE_ID=PRINCIPAL,
    BOT_COMERCIAL_SANDBOX_NUMBER='573000000001',
    WHATSAPP_PHONE_NUMBER_ID_2='222',
    WHATSAPP_NUMERO_2_E164='573009536193',
    META_LINEAS='',
    EKI_LINEAS_BD_ENABLED=False,
)


class ModoOfertaTests(SimpleTestCase):
    def test_un_curso_no_es_carrusel(self):
        self.assertEqual(modo_de_oferta(0, True), 'vacio')
        self.assertEqual(modo_de_oferta(1, True), 'boton')
        self.assertEqual(modo_de_oferta(2, True), 'carrusel')
        self.assertEqual(modo_de_oferta(2, False), 'lista')
        self.assertEqual(modo_de_oferta(11, True), 'lista')


@override_settings(**AJUSTES)
class YaRegistradoTests(SimpleTestCase):
    def test_con_ficha_no_abre_el_formulario(self):
        ficha = SimpleNamespace(cliente_id=7, acepto_terminos=True, nombre='Ana', cedula='1')
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.lineas.registro_abrir._cliente_guardado', return_value=7,
        ), patch(
            'core.lineas.registro_abrir._recordar',
        ), patch(
            'core.lineas.registro_cursos.atender_cursos',
        ) as cursos, patch(
            'core.lineas.envio.enviar_meta_flow',
        ) as flow:
            self.assertEqual(abrir_registro('573001112233', 'hola'), 'handled')
        flow.assert_not_called()
        cursos.assert_called_once_with('573001112233', 'hola', 7)

    def test_la_ficha_no_cambia_de_organizacion_por_otro_enlace(self):
        ficha = SimpleNamespace(cliente_id=7, acepto_terminos=True, nombre='Ana', cedula='1')
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.lineas.registro_abrir._cliente_guardado', return_value=None,
        ), patch(
            'core.lineas.registro_abrir._recordar',
        ), patch(
            'core.lineas.registro_cursos.atender_cursos',
        ) as cursos:
            abrir_registro('573001112233', 'EKI C12')
        cursos.assert_called_once_with('573001112233', 'EKI C12', 7)

    def test_la_principal_sigue_sin_entrar(self):
        with salida_por_phone_id(PRINCIPAL), patch(
            'core.lineas.registro_cursos.atender_cursos',
        ) as cursos, patch('core.lineas.envio.enviar_meta_flow') as flow:
            self.assertIsNone(abrir_registro('573001112233', 'hola'))
        cursos.assert_not_called()
        flow.assert_not_called()


class AtenderCursosTests(SimpleTestCase):
    def test_dos_cursos_con_foto_van_al_carrusel(self):
        cursos = [
            SimpleNamespace(id=1, nombre='Uno', descripcion='a'),
            SimpleNamespace(id=2, nombre='Dos', descripcion='b'),
        ]
        tarjetas = [
            {'imagen': 'https://eki.example/1.jpg', 'body': 'Uno', 'botones': []},
            {'imagen': 'https://eki.example/2.jpg', 'body': 'Dos', 'botones': []},
        ]
        with patch(
            'core.lineas.registro_cursos._oferta_recien_enviada', return_value=False,
        ), patch(
            'core.lineas.registro_cursos.cursos_del_cliente', return_value=cursos,
        ), patch(
            'core.lineas.registro_cursos._tarjeta', side_effect=tarjetas,
        ), patch(
            'core.lineas.envio.enviar_meta_carrusel', return_value={'success': True},
        ) as carrusel, patch(
            'core.lineas.envio.enviar_meta_botones',
        ) as boton:
            atender_cursos('573001112233', 'hola', 7)
        carrusel.assert_called_once()
        boton.assert_not_called()
        self.assertEqual(len(carrusel.call_args.args[2]), 2)

    def test_no_repite_el_carrusel_si_acaba_de_salir(self):
        with patch(
            'core.lineas.registro_cursos._oferta_recien_enviada', return_value=True,
        ), patch(
            'core.lineas.envio.enviar_meta_carrusel',
        ) as carrusel:
            atender_cursos('573001112233', 'hola', 7)
        carrusel.assert_not_called()

    def test_ver_curso_inscribe_y_abre_la_clase(self):
        curso = SimpleNamespace(id=5, nombre='Suelos', descripcion='')
        ficha = _Ficha()
        progreso = SimpleNamespace(modulo_actual=SimpleNamespace(numero=1), curso_id=5)
        with patch(
            'core.lineas.registro_cursos.cursos_del_cliente', return_value=[curso],
        ), patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.curso.inscripcion_curso.inscribir_estudiante_en_curso',
            return_value=(progreso, True),
        ) as alta, patch(
            'core.curso.inicio_curso.curso_sin_empezar', return_value=True,
        ), patch(
            'core.curso.inicio_curso.mensaje_primera_entrega', return_value='CLASE',
        ) as primera, patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso:
            atender_cursos('573001112233', 'ver_curso_5', 7)
        alta.assert_called_once_with(ficha, curso)
        textos = [llamada.args[1] for llamada in aviso.call_args_list]
        self.assertEqual(textos, ['Quedó en Suelos.', 'CLASE'])
        self.assertEqual(ficha.contexto_temporal['curso_activo_id'], 5)
        primera.assert_called_once_with(ficha, progreso, progreso.modulo_actual)

    def test_ver_curso_ya_empezado_no_repite_el_saludo(self):
        curso = SimpleNamespace(id=5, nombre='Suelos', descripcion='')
        ficha = _Ficha()
        progreso = SimpleNamespace(modulo_actual=SimpleNamespace(numero=1), curso_id=5)
        with patch(
            'core.lineas.registro_cursos.cursos_del_cliente', return_value=[curso],
        ), patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.curso.inscripcion_curso.inscribir_estudiante_en_curso',
            return_value=(progreso, False),
        ), patch(
            'core.curso.inicio_curso.curso_sin_empezar', return_value=False,
        ), patch(
            'core.curso.inicio_curso.mensaje_primera_entrega',
        ) as primera, patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso:
            atender_cursos('573001112233', 'ver_curso_5', 7)
        primera.assert_not_called()
        self.assertEqual(aviso.call_args.args[1], 'Quedó en Suelos.')

    def test_listo_avanza_y_no_abre_el_carrusel(self):
        ficha = _Ficha()
        with patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.conversacion.intents.continuar_leccion.responder',
            return_value='SIGUIENTE',
        ) as avanzar, patch(
            'core.conversacion.response_templates.soltar_turno_entrega_actual',
        ) as soltar, patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso, patch(
            'core.lineas.envio.enviar_meta_carrusel',
        ) as carrusel:
            atender_cursos('573001112233', 'listo', 7)
        avanzar.assert_called_once_with(
            'continuar_leccion', 'Ana',
            {'estudiante_id': 3, 'mensaje_original': 'listo'},
        )
        aviso.assert_called_once_with('573001112233', 'SIGUIENTE')
        soltar.assert_called_once()
        carrusel.assert_not_called()

    def test_listo_mientras_sale_la_clase_no_manda_el_aviso_interno(self):
        from core.conversacion.response_templates import LECCION_EN_CURSO

        with patch(
            'core.lineas.registro_abrir._ficha', return_value=_Ficha(),
        ), patch(
            'core.conversacion.intents.continuar_leccion.responder',
            return_value=LECCION_EN_CURSO,
        ), patch(
            'core.conversacion.response_templates.soltar_turno_entrega_actual',
        ), patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso:
            atender_cursos('573001112233', 'continuemos', 7)
        aviso.assert_not_called()

    def test_ver_curso_de_otra_organizacion_no_inscribe(self):
        with patch(
            'core.lineas.registro_cursos.cursos_del_cliente', return_value=[],
        ), patch(
            'core.lineas.registro_abrir._ficha', return_value=SimpleNamespace(id=3),
        ), patch(
            'core.curso.inscripcion_curso.inscribir_estudiante_en_curso',
        ) as alta, patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso:
            atender_cursos('573001112233', 'ver_curso_9', 7)
        alta.assert_not_called()
        self.assertIn('no está', aviso.call_args.args[1])
