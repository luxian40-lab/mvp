"""El carrusel de la línea 3 es el del enlace, no el de la línea principal."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.lineas.registro_abrir import abrir_registro
from core.lineas.registro_cursos import atender_cursos, modo_de_oferta
from core.sandbox_canal import salida_por_phone_id

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

    def test_ver_curso_inscribe_solo_si_es_del_enlace(self):
        curso = SimpleNamespace(id=5, nombre='Suelos', descripcion='')
        ficha = SimpleNamespace(id=3)
        with patch(
            'core.lineas.registro_cursos.cursos_del_cliente', return_value=[curso],
        ), patch(
            'core.lineas.registro_abrir._ficha', return_value=ficha,
        ), patch(
            'core.curso.inscripcion_curso.inscribir_estudiante_en_curso',
        ) as alta, patch(
            'core.lineas.registro_abrir._avisar',
        ) as aviso:
            atender_cursos('573001112233', 'ver_curso_5', 7)
        alta.assert_called_once_with(ficha, curso)
        self.assertIn('Suelos', aviso.call_args.args[1])

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
