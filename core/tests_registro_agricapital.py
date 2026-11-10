"""Bienvenida AgriCapital y cohorte OP1 en la línea 3."""
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.lineas.registro_abrir import abrir_registro
from core.lineas.registro_agricapital import (
    BOTON_ID_PREFIJO,
    FRASE_ENLACE,
    NOMBRE_GRUPO_COHORTE,
    TEXTO_BIENVENIDA,
    aplicar_cohorte,
    destino_frase_agri,
    es_boton_registrarme,
    es_cliente_agricapital,
    frase_para_cliente,
)
from core.lineas.registro_guardar import guardar_registro
from core.models import Cliente, Curso, Estudiante, Modulo
from core.models_extras import GrupoEstudiantes
from core.sandbox_canal import salida_por_phone_id

PHONE = '1477762615411333'
WABA = '1560693046090506'
FLOW = '1644555950738838'
PRINCIPAL = '111'
LINEA_2 = '222'
AGRI_ID = 26

AJUSTES = dict(
    EKI_LINEA_REGISTRO_PHONE_ID=PHONE,
    EKI_LINEA_REGISTRO_E164='573019018929',
    EKI_LINEA_REGISTRO_WABA_ID=WABA,
    EKI_LINEA_REGISTRO_FLOW_ID=FLOW,
    SANDBOX_WHATSAPP_PHONE_ID=PRINCIPAL,
    WHATSAPP_PHONE_ID=PRINCIPAL,
    BOT_COMERCIAL_SANDBOX_NUMBER='573000000001',
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    META_LINEAS='',
    EKI_LINEAS_BD_ENABLED=False,
    EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID),
)


@override_settings(**AJUSTES)
class AgriCapitalHelpersTests(SimpleTestCase):
    def test_solo_el_id_configurado_es_agricapital(self):
        self.assertTrue(es_cliente_agricapital(AGRI_ID))
        self.assertFalse(es_cliente_agricapital(12))
        self.assertFalse(es_cliente_agricapital(None))

    def test_hola_agricapital_elige_el_cliente(self):
        self.assertEqual(FRASE_ENLACE, 'Hola, AgriCapital me invitó a un curso gratis')
        self.assertEqual(
            destino_frase_agri('Hola, AgriCapital me invitó a un curso gratis'),
            ('cliente', AGRI_ID),
        )
        self.assertEqual(
            destino_frase_agri('Hola, AgriCapital me invitó a (1) curso gratis'),
            ('cliente', AGRI_ID),
        )
        self.assertEqual(destino_frase_agri('Hola AgriCapital'), ('cliente', AGRI_ID))
        self.assertEqual(destino_frase_agri('Hola eki agri'), ('cliente', AGRI_ID))
        self.assertEqual(frase_para_cliente(AGRI_ID), FRASE_ENLACE)
        self.assertIsNone(frase_para_cliente(12))
        self.assertIsNone(destino_frase_agri('HOLA EKI'))
        self.assertIsNone(destino_frase_agri('EKI C12'))

    def test_el_boton_registrarme_lleva_el_cliente(self):
        self.assertEqual(es_boton_registrarme(f'{BOTON_ID_PREFIJO}{AGRI_ID}'), AGRI_ID)
        self.assertIsNone(es_boton_registrarme('Registrarme'))
        self.assertIsNone(es_boton_registrarme(f'{BOTON_ID_PREFIJO}12'))


@override_settings(**AJUSTES)
class BienvenidaAgriCapitalTests(SimpleTestCase):
    def setUp(self):
        patch('core.lineas.registro_abrir._ficha', return_value=None).start()
        patch('core.lineas.registro_abrir._recordar').start()
        patch('core.lineas.registro_abrir._cliente_guardado', return_value=None).start()
        self.addCleanup(patch.stopall)

    def test_eki_c_agricapital_manda_bienvenida_y_flow(self):
        with salida_por_phone_id(PHONE), patch(
            'core.sandbox_menu.enviar_texto_sandbox',
        ) as texto, patch(
            'core.lineas.envio.enviar_meta_botones',
        ) as botones, patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as flow:
            self.assertEqual(abrir_registro('573001112233', f'EKI C{AGRI_ID}'), 'handled')
        botones.assert_not_called()
        texto.assert_called_once()
        self.assertEqual(texto.call_args.args[2], TEXTO_BIENVENIDA)
        flow.assert_called_once()
        self.assertEqual(flow.call_args.kwargs['flow_token'], f'registro-C{AGRI_ID}')
        self.assertEqual(flow.call_args.kwargs['cta'], 'Registrarme')

    def test_hola_agricapital_manda_bienvenida_y_flow(self):
        with salida_por_phone_id(PHONE), patch(
            'core.sandbox_menu.enviar_texto_sandbox',
        ) as texto, patch(
            'core.lineas.envio.enviar_meta_botones',
        ) as botones, patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as flow:
            self.assertEqual(
                abrir_registro('573001112233', FRASE_ENLACE),
                'handled',
            )
        botones.assert_not_called()
        texto.assert_called_once()
        flow.assert_called_once()

    def test_boton_viejo_registrarme_abre_el_flow(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as flow, patch('core.lineas.envio.enviar_meta_botones') as botones:
            self.assertEqual(
                abrir_registro('573001112233', f'{BOTON_ID_PREFIJO}{AGRI_ID}'),
                'handled',
            )
        botones.assert_not_called()
        flow.assert_called_once()
        self.assertEqual(flow.call_args.kwargs['flow_token'], f'registro-C{AGRI_ID}')
        self.assertEqual(flow.call_args.kwargs['cta'], 'Registrarme')

    def test_otro_cliente_sigue_abriendo_el_flow_al_instante(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as flow, patch('core.lineas.envio.enviar_meta_botones') as botones, patch(
            'core.sandbox_menu.enviar_texto_sandbox',
        ):
            self.assertEqual(abrir_registro('573001112233', 'EKI C12'), 'handled')
        botones.assert_not_called()
        flow.assert_called_once()
        self.assertEqual(flow.call_args.kwargs['flow_token'], 'registro-C12')

    @override_settings(EKI_AGRICAPITAL_CLIENTE_ID='')
    def test_sin_setting_eki_c26_abre_el_flow_como_antes(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as flow, patch('core.lineas.envio.enviar_meta_botones') as botones, patch(
            'core.sandbox_menu.enviar_texto_sandbox',
        ):
            self.assertEqual(abrir_registro('573001112233', f'EKI C{AGRI_ID}'), 'handled')
        botones.assert_not_called()
        flow.assert_called_once()


class CohorteAgriCapitalTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            id=AGRI_ID,
            nombre='Agricapital',
            contacto_principal='Ana',
            email='agri-cohorte@test.com',
            telefono='573001110010',
            activo=True,
            fecha_fin_suscripcion=timezone.localdate() + timedelta(days=30),
        )
        self.grupo = GrupoEstudiantes.objects.create(
            nombre='AgriCapital · cohorte noviembre',
            cliente=self.cliente,
            plan_linea_meta='curso_asesor',
            activo=True,
        )
        self.curso = Curso.objects.create(
            nombre='Curso AgriCapital',
            descripcion='Curso de prueba AgriCapital',
            cliente=self.cliente,
            activo=True,
        )
        Modulo.objects.create(
            curso=self.curso, numero=0, titulo='Intro', descripcion='Intro',
        )

    @override_settings(
        EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID),
        EKI_AGRICAPITAL_GRUPO_ID='',
        EKI_AGRICAPITAL_CURSO_ID='',
    )
    def test_sin_settings_crea_grupo_op1_con_carrusel_sin_inscribir(self):
        self.grupo.delete()
        self.cliente.cursos_whatsapp.add(self.curso)
        datos = {
            'flow_token': f'registro-C{AGRI_ID}',
            'habeas': True,
            'nombre': 'Ana Ruiz',
            'cedula': '1099000777',
            'municipio': 'Andes',
        }
        guardar_registro('573009991077', datos)
        est = Estudiante.objects.get(telefono='573009991077')
        grupo = GrupoEstudiantes.objects.get(
            cliente_id=AGRI_ID, nombre=NOMBRE_GRUPO_COHORTE, activo=True,
        )
        self.assertEqual(est.cliente_id, AGRI_ID)
        self.assertEqual(grupo.plan_linea_meta, 'curso_asesor')
        self.assertIn(est, grupo.estudiantes.all())
        self.assertIn(self.curso, grupo.cursos.all())
        self.assertEqual(est.progresos.count(), 0)

    def test_flow_mete_al_grupo_sin_inscribir_curso(self):
        datos = {
            'flow_token': f'registro-C{self.cliente.pk}',
            'habeas': True,
            'nombre': 'Ana Ruiz',
            'cedula': '1099000888',
            'municipio': 'Andes',
        }
        with self.settings(
            EKI_AGRICAPITAL_CLIENTE_ID=str(self.cliente.pk),
            EKI_AGRICAPITAL_GRUPO_ID=str(self.grupo.pk),
            EKI_AGRICAPITAL_CURSO_ID=str(self.curso.pk),
        ):
            texto = guardar_registro('573009991088', datos)
        est = Estudiante.objects.get(telefono='573009991088')
        self.assertEqual(est.cliente_id, self.cliente.pk)
        self.assertIn(est, self.grupo.estudiantes.all())
        self.assertEqual(est.progresos.count(), 0)
        self.assertIn('Agricapital', texto)

    def test_aplicar_cohorte_no_toca_otro_cliente(self):
        otro = Cliente.objects.create(
            nombre='Otro',
            contacto_principal='Bo',
            email='otro-agri@test.com',
            telefono='573001110011',
            activo=True,
            fecha_fin_suscripcion=timezone.localdate() + timedelta(days=30),
        )
        est = Estudiante.objects.create(
            nombre='Pedro', cedula='1099000999', telefono='573009991099',
            cliente=otro, acepto_terminos=True, estado_chat='ACTIVO',
        )
        with self.settings(
            EKI_AGRICAPITAL_CLIENTE_ID=str(self.cliente.pk),
            EKI_AGRICAPITAL_GRUPO_ID=str(self.grupo.pk),
            EKI_AGRICAPITAL_CURSO_ID=str(self.curso.pk),
        ):
            aplicar_cohorte(est, self.cliente)
        self.assertEqual(est.grupos.count(), 0)
        self.assertEqual(est.progresos.count(), 0)
