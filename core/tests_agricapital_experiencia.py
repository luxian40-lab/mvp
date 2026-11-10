"""S1/S2 AgriCapital: dudas sin nota y media sin «No entendí». Solo ese cliente."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.lineas.agricapital_experiencia import (
    es_duda_media_agricapital,
    es_mensaje_no_calificable_reto,
    estudiante_es_agricapital,
)
from core.media_recuperacion import intentar_reenvio_media_curso

AGRI_ID = 26
OTRO_ID = 99


class DetectoresAgriCapitalTests(SimpleTestCase):
    def test_no_calificable_cubre_ayuda_no_entendi_y_media(self):
        for frase in (
            'No entendí',
            'ayuda',
            'No descarga',
            'No puedo ver la imagen',
            'no veo el video',
        ):
            self.assertTrue(es_mensaje_no_calificable_reto(frase), frase)

    def test_respuesta_real_al_reto_si_califica(self):
        self.assertFalse(
            es_mensaje_no_calificable_reto(
                'Primero revisaría el cultivo y anotaría qué plaga veo esta semana.'
            )
        )

    def test_duda_media_detecta_descarga_e_imagen(self):
        self.assertTrue(es_duda_media_agricapital('No descarga'))
        self.assertTrue(es_duda_media_agricapital('No puedo ver la imagen'))
        self.assertFalse(es_duda_media_agricapital('quiero seguir el curso'))

    @override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID))
    def test_solo_cliente_agricapital(self):
        self.assertTrue(estudiante_es_agricapital(SimpleNamespace(cliente_id=AGRI_ID)))
        self.assertFalse(estudiante_es_agricapital(SimpleNamespace(cliente_id=OTRO_ID)))

    @override_settings(EKI_AGRICAPITAL_CLIENTE_ID='')
    def test_sin_setting_nadie_es_agricapital(self):
        self.assertFalse(estudiante_es_agricapital(SimpleNamespace(cliente_id=AGRI_ID)))


@override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID))
class RetoAgriCapitalNoCalificaTests(SimpleTestCase):
    def test_no_entendi_en_reto_agri_no_llama_evaluador(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import reto as reto_mod

        estudiante = SimpleNamespace(
            cliente_id=AGRI_ID,
            contexto_temporal={
                'modulos_reto_ids': [],
                'reto_texto': 'Cuéntanos tu plan',
                'progreso_id': None,
            },
            nombre='Ana',
            id=1,
        )
        contexto = Contexto(
            estudiante=estudiante,
            msg_body='No entendí',
            msg_from='573001112233',
            telefono_limpio='573001112233',
            msg_sid='wamid.x',
            texto_respuesta='',
        )
        with patch.object(reto_mod, 'evaluar_reto_facilitador', create=True) as mock_eval:
            with patch('core.tutor_ia_modulo.evaluar_reto_facilitador') as mock_eval2:
                resp = reto_mod.manejar(contexto)
        mock_eval2.assert_not_called()
        self.assertIn('no cuenta como respuesta', (resp.texto or '').lower())
        self.assertNotIn('/10', resp.texto or '')


@override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID))
class MediaAgriCapitalTests(SimpleTestCase):
    def test_otro_cliente_no_descarga_no_activa_tip_agri(self):
        est = SimpleNamespace(cliente_id=OTRO_ID, telefono='573001112233')
        with patch(
            'core.pqrs_acciones.texto_reenviar_modulo',
            return_value=None,
        ):
            self.assertIsNone(intentar_reenvio_media_curso(est, 'No descarga'))

    def test_agri_no_descarga_da_tip_si_no_hay_media(self):
        est = SimpleNamespace(cliente_id=AGRI_ID, telefono='573001112233')
        with patch(
            'core.pqrs_acciones.texto_reenviar_modulo',
            return_value=None,
        ):
            out = intentar_reenvio_media_curso(est, 'No descarga')
        self.assertIsNotNone(out)
        self.assertIn('no descarga', (out or '').lower())

    def test_agri_no_puedo_ver_imagen_intenta_reenvio(self):
        est = SimpleNamespace(cliente_id=AGRI_ID, telefono='573001112233')
        with patch(
            'core.pqrs_acciones.texto_reenviar_modulo',
            return_value='[MEDIA:https://ejemplo.test/a.jpg]',
        ), patch(
            'core.media_entrega.marcar_paquete_recuperado_por_telefono',
        ):
            out = intentar_reenvio_media_curso(est, 'No puedo ver la imagen')
        self.assertIn('[MEDIA:', out or '')


@override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID))
class InventarioAgriCapitalTests(TestCase):
    def test_sin_cursos_lista_vacia(self):
        from core.lineas.agricapital_inventario import inventariar_media_agricapital
        from core.models import Cliente

        Cliente.objects.create(id=AGRI_ID, nombre='AgriCapital', activo=True)
        resumenes = inventariar_media_agricapital(head_urls=False)
        self.assertEqual(resumenes, [])

    def test_curso_con_paso_media_aparece_en_inventario(self):
        from core.lineas.agricapital_inventario import inventariar_media_agricapital
        from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo

        cliente = Cliente.objects.create(id=AGRI_ID, nombre='AgriCapital', activo=True)
        curso = Curso.objects.create(
            nombre='Curso AgriCapital 1',
            descripcion='Prueba',
            cliente=cliente,
            activo=True,
        )
        cliente.cursos_whatsapp.add(curso)
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='M1',
        )
        seccion = SeccionModulo.objects.create(modulo=mod, titulo='S1', orden=1)
        PasoModulo.objects.create(
            modulo=mod,
            seccion=seccion,
            orden=1,
            titulo='Video',
            contenido='mira',
            media_url='https://ejemplo.test/demo.mp4',
        )
        resumenes = inventariar_media_agricapital(head_urls=False)
        self.assertEqual(len(resumenes), 1)
        self.assertEqual(resumenes[0].archivos, 1)
        self.assertEqual(resumenes[0].sin_tamano, 1)


@override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(AGRI_ID))
class CopyVocesRitmoAgriCapitalTests(SimpleTestCase):
    """S3 tú + S4 Formador/Compañero + S6 pausas. Solo AgriCapital."""

    def test_presentacion_agri_usa_tu_y_solo_formador_companero(self):
        from core.lineas.agricapital_experiencia import presentacion_inicio_agricapital

        fac, comp = presentacion_inicio_agricapital('Finanzas', 'Ana')
        texto = f'{fac}\n{comp}'.lower()
        self.assertIn('formador', texto)
        self.assertIn('compañero', texto)
        self.assertIn('tu formador', texto)
        self.assertIn('de ti', texto)
        self.assertNotIn('usted', texto)
        self.assertNotIn('copiloto', texto)
        self.assertNotIn('asesor', texto)

    def test_presentacion_curso_agri_via_generar_agentes(self):
        from core.tutor_ia_modulo import generar_presentacion_agentes

        curso = SimpleNamespace(cliente_id=AGRI_ID, nombre='Finanzas')
        fac, comp = generar_presentacion_agentes(
            'Finanzas', 'Ana', curso=curso,
        )
        self.assertIn('Formador', fac)
        self.assertIn('Compañero', comp)
        self.assertIn('te plantearé', fac.lower())

    def test_presentacion_otro_cliente_sigue_usted(self):
        from core.tutor_ia_modulo import generar_presentacion_agentes

        curso = SimpleNamespace(cliente_id=OTRO_ID, nombre='Otro')
        with patch(
            'core.tutor_ia_modulo.es_perfil_tecnicoagro',
            return_value=False,
        ):
            fac, comp = generar_presentacion_agentes('Otro', 'Ana', curso=curso)
        self.assertIn('su formador', fac.lower())
        self.assertIn('usted', comp.lower())

    def test_pausas_entre_burbujas_inserta_delay(self):
        from core.conversacion.multimsg import DELAY, MULTI_MSG, SEP
        from core.lineas.agricapital_experiencia import con_pausas_entre_burbujas

        bruto = MULTI_MSG + SEP.join(['uno', 'dos', 'tres'])
        out = con_pausas_entre_burbujas(bruto, segundos=1)
        self.assertIn(f'{DELAY}1]', out)
        partes = out.replace(MULTI_MSG, '', 1).split(SEP)
        self.assertEqual(partes[0], 'uno')
        self.assertEqual(partes[1], f'{DELAY}1]')
        self.assertEqual(partes[2], 'dos')

    def test_preparar_salida_solo_agri(self):
        from core.conversacion.multimsg import DELAY, MULTI_MSG, SEP
        from core.lineas.agricapital_experiencia import preparar_salida_agricapital

        bruto = MULTI_MSG + SEP.join(['a', 'b'])
        agri = SimpleNamespace(cliente_id=AGRI_ID)
        otro = SimpleNamespace(cliente_id=OTRO_ID)
        self.assertIn(f'{DELAY}1]', preparar_salida_agricapital(agri, bruto))
        self.assertEqual(preparar_salida_agricapital(otro, bruto), bruto)

    def test_no_entendi_agri_en_tu(self):
        from core.lineas.agricapital_experiencia import texto_no_entendi_agricapital

        t = texto_no_entendi_agricapital().lower()
        self.assertIn('si quieres avanzar', t)
        self.assertNotIn('si quiere avanzar', t)

    def test_drip_agri_en_tu(self):
        from core.lineas.agricapital_experiencia import texto_bloqueo_drip_agricapital

        t = texto_bloqueo_drip_agricapital('10/11/2026').lower()
        self.assertIn('tu siguiente sesión', t)
        self.assertIn('tu próxima lección', t)
        self.assertNotIn('su siguiente', t)

    def test_carrusel_registro_sigue_usted(self):
        """L3 registro no importa copy en tú: el menú/carrusel quedan en usted."""
        from core.lineas import registro_cursos

        self.assertIn('Elija', registro_cursos.CUERPO_OFERTA)
        self.assertIn('Su registro', registro_cursos.TEXTO_SIN_CURSOS)
