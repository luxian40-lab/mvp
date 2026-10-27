"""Aviso automático de módulo disponible: solo a quien espera ese módulo, una vez."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    AvisoModuloDisponible,
    AvisoModuloEnviado,
    Cliente,
    Curso,
    Estudiante,
    HabilitacionModuloDripCliente,
    HabilitacionModuloEstudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
)
from core.models_campana_meta import PlantillaMeta
from core.models_extras import GrupoEstudiantes

PHONE = '495439026995771'
LINEA_2 = '894379507087782'
WABA = '111222333'
WABA_2 = '999888777'

AJUSTES = dict(
    EKI_AVISO_MODULO_DISPONIBLE_ENABLED=True,
    EKI_AVISO_MODULO_VENTANA_HORAS=24,
    EKI_AVISO_MODULO_PAUSA_SEG=0,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_PHONE_ID=PHONE,
    SANDBOX_WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_BUSINESS_ACCOUNT_ID_2=WABA_2,
    META_LINEAS='',
)


def _sender_ok():
    sender = MagicMock()
    sender.plantilla.return_value = {'success': True, 'mensaje_id': 'wamid.X', 'response': '{}'}
    return sender


@override_settings(**AJUSTES)
class AvisoModuloTests(TestCase):
    def setUp(self):
        self.ahora = timezone.now()
        self.cliente = Cliente.objects.create(
            nombre='Alitic', contacto_principal='A', email='a@test.com', telefono='573001110000', activo=True,
        )
        self.curso = Curso.objects.create(nombre='Crea y Vende', descripcion='d', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(curso=self.curso, numero=1, titulo='Su idea', descripcion='d', contenido='c')
        self.m2 = Modulo.objects.create(curso=self.curso, numero=2, titulo='Su cliente', descripcion='d', contenido='c')
        self.plantilla = PlantillaMeta.objects.create(
            nombre_interno='Módulo disponible',
            meta_name='modulo_disponible',
            idioma='es',
            categoria='UTILITY',
            tipo='TEXTO',
            cuerpo='Hola {{1}}, ya está disponible el módulo *{{2}}* de su curso *{{3}}*',
            estado='APPROVED',
            activa=True,
            waba_id=WABA_2,
        )
        self.aviso = AvisoModuloDisponible.objects.create(
            cliente=self.cliente, curso=self.curso, plantilla=self.plantilla, phone_number_id=LINEA_2,
        )
        self.habilitacion = HabilitacionModuloDripCliente.objects.create(
            cliente=self.cliente,
            curso=self.curso,
            modulo=self.m2,
            habilitado_desde=self.ahora - timedelta(minutes=5),
            activo=True,
        )

    def _estudiante(self, telefono, *, termino_m1=True, **extra):
        estudiante = Estudiante.objects.create(
            cedula=f'CC{telefono[-6:]}', nombre='Ana', telefono=telefono, cliente=self.cliente, activo=True, **extra,
        )
        progreso = ProgresoEstudiante.objects.create(
            estudiante=estudiante, curso=self.curso, modulo_actual=self.m1,
        )
        if termino_m1:
            ModuloCompletado.objects.create(progreso=progreso, modulo=self.m1)
        return estudiante

    def _ejecutar(self, sender=None):
        from core.aviso_modulo import ejecutar

        sender = sender or _sender_ok()
        with patch('core.meta_token.token_invalido', return_value=False), \
                patch('core.lineas.sender.sender_de_linea', return_value=sender) as fabrica:
            resultado = ejecutar(self.ahora)
        return resultado, sender, fabrica

    def test_avisa_a_quien_termino_el_modulo_anterior(self):
        ana = self._estudiante('573001110001')
        resultado, sender, fabrica = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)
        fabrica.assert_called_with(LINEA_2)
        args = sender.plantilla.call_args
        self.assertEqual(args.args[0], ana.telefono)
        self.assertEqual(args.args[1], 'modulo_disponible')
        self.assertEqual(args.args[2], {'1': 'Ana', '2': 'Su cliente', '3': 'Crea y Vende'})
        envio = AvisoModuloEnviado.objects.get(estudiante=ana, modulo=self.m2)
        self.assertEqual(envio.estado, 'ENVIADO')
        self.assertEqual(envio.wamid, 'wamid.X')

    def test_no_repite_el_aviso(self):
        self._estudiante('573001110002')
        self._ejecutar()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)
        sender.plantilla.assert_not_called()

    def test_no_avisa_a_quien_no_termino_el_anterior(self):
        self._estudiante('573001110003', termino_m1=False)
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)
        sender.plantilla.assert_not_called()

    def test_no_avisa_si_el_modulo_aun_no_abre(self):
        self._estudiante('573001110004')
        self.habilitacion.habilitado_desde = self.ahora + timedelta(hours=1)
        self.habilitacion.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)

    def test_no_avisa_si_abrio_hace_mas_de_la_ventana(self):
        self._estudiante('573001110005')
        self.habilitacion.habilitado_desde = self.ahora - timedelta(hours=30)
        self.habilitacion.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)

    def test_respeta_la_fecha_propia_del_estudiante(self):
        ana = self._estudiante('573001110006')
        HabilitacionModuloEstudiante.objects.create(
            estudiante=ana, curso=self.curso, modulo=self.m2,
            habilitado_desde=self.ahora + timedelta(days=2), activo=True,
        )
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)

    def test_excluye_baja_e_inactivos(self):
        self._estudiante('573001110007', wa_optout_fecha=self.ahora)
        inactivo = self._estudiante('573001110008')
        inactivo.activo = False
        inactivo.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)

    def test_con_grupo_solo_avisa_al_grupo(self):
        dentro = self._estudiante('573001110009')
        self._estudiante('573001110010')
        grupo = GrupoEstudiantes.objects.create(nombre='Alitic nuevos', cliente=self.cliente)
        grupo.estudiantes.add(dentro)
        self.aviso.grupo = grupo
        self.aviso.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)
        self.assertEqual(sender.plantilla.call_args.args[0], dentro.telefono)

    def test_flag_apagado_no_envia(self):
        self._estudiante('573001110011')
        with self.settings(EKI_AVISO_MODULO_DISPONIBLE_ENABLED=False):
            resultado, sender, _ = self._ejecutar()
        self.assertFalse(resultado['habilitado'])
        sender.plantilla.assert_not_called()

    def test_aviso_inactivo_no_envia(self):
        self._estudiante('573001110012')
        self.aviso.activo = False
        self.aviso.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)

    def test_plantilla_de_otra_cuenta_no_sale(self):
        self._estudiante('573001110013')
        self.plantilla.waba_id = WABA
        self.plantilla.save()
        resultado, sender, _ = self._ejecutar()
        self.assertEqual(resultado['enviados'], 0)
        self.assertEqual(resultado['avisos_invalidos'], 1)
        sender.plantilla.assert_not_called()

    def test_token_invalido_no_envia(self):
        from core.aviso_modulo import ejecutar

        self._estudiante('573001110014')
        sender = _sender_ok()
        with patch('core.meta_token.token_invalido', return_value=True), \
                patch('core.lineas.sender.sender_de_linea', return_value=sender):
            resultado = ejecutar(self.ahora)
        self.assertEqual(resultado['enviados'], 0)
        self.assertTrue(resultado['omitido_token'])
        sender.plantilla.assert_not_called()

    def test_fallo_queda_anotado_y_no_se_reintenta(self):
        ana = self._estudiante('573001110015')
        sender = MagicMock()
        sender.plantilla.return_value = {'success': False, 'mensaje_id': None, 'response': 'error 131026'}
        resultado, _, _ = self._ejecutar(sender)
        self.assertEqual(resultado['fallidos'], 1)
        envio = AvisoModuloEnviado.objects.get(estudiante=ana, modulo=self.m2)
        self.assertEqual(envio.estado, 'FALLIDO')
        self.assertIn('131026', envio.respuesta)
        resultado, sender_2, _ = self._ejecutar()
        sender_2.plantilla.assert_not_called()

    def test_vista_previa_cuenta_sin_enviar(self):
        from core.aviso_modulo import vista_previa

        self._estudiante('573001110016')
        self._estudiante('573001110017', termino_m1=False)
        with patch('core.lineas.sender.sender_de_linea') as fabrica:
            filas = vista_previa(self.aviso, self.ahora)
        fabrica.assert_not_called()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['modulo'], self.m2)
        self.assertEqual(filas[0]['personas'], 1)

    def test_prueba_al_numero_interno(self):
        from core.aviso_modulo import enviar_prueba

        sender = _sender_ok()
        with patch('core.lineas.sender.sender_de_linea', return_value=sender):
            resultado = enviar_prueba(self.aviso, '573026480629')
        self.assertTrue(resultado['success'])
        args = sender.plantilla.call_args
        self.assertEqual(args.args[0], '573026480629')
        self.assertEqual(args.args[2]['3'], 'Crea y Vende')
        self.assertFalse(AvisoModuloEnviado.objects.exists())

    def test_motivo_plantilla_con_variables_de_mas(self):
        from core.aviso_modulo import motivo_plantilla

        self.plantilla.cuerpo = 'Hola {{1}} {{2}} {{3}} {{4}}'
        self.plantilla.save()
        self.assertIn('variables', motivo_plantilla(self.aviso.plantilla, LINEA_2))
