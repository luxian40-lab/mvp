"""Tests modo diagnóstico Nati — anamnesis clínica y sin bucles."""

from django.test import TestCase

from core.contexto_agro import extraer_campos_desde_mensaje, obtener_o_crear_contexto
from core.models import Cliente, SesionComercial
from core.nat_diagnostico import siguiente_pregunta_diagnostico


class NatDiagnosticoLoopTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Diag',
            contacto_principal='A',
            email='diag@test.co',
            telefono='573009990001',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009990001',
            cliente=self.cliente,
        )
        self.ctx = obtener_o_crear_contexto(self.sesion)
        self.ctx.cultivo = 'tomate'
        self.ctx.region = 'Boyaca'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

    def test_extrae_manchas_y_no_crece(self):
        self.assertIn('mancha', extraer_campos_desde_mensaje('Tiene manchas').get('problema', '').lower())
        prob = extraer_campos_desde_mensaje('No crece hay brote negro').get('problema', '').lower()
        self.assertTrue('no crece' in prob or 'brote' in prob)

    def test_extrae_guateque_desde_depto_municipio(self):
        campos = extraer_campos_desde_mensaje('Boyaca guateque')
        self.assertEqual(campos.get('municipio'), 'Guateque')
        self.assertEqual(campos.get('region'), 'Boyaca')

    def test_no_repite_pregunta_problema_con_texto_libre(self):
        """Regresión prod: usuario responde síntoma pero regex no lo capturaba → bucle."""
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Las plantas están muy débiles y el follaje se cae',
        )
        self.ctx.refresh_from_db()
        self.assertTrue((self.ctx.problema or '').strip())
        self.assertNotEqual(
            pregunta,
            '¿Puede describir con más detalle el problema que observa en las plantas?',
        )
        # Debe avanzar a anamnesis personalizada (extensión), no repetir síntoma
        self.assertIsNotNone(pregunta)
        self.assertIn('tomate', pregunta.lower())

    def test_preguntas_personalizadas_mencionan_cultivo(self):
        self.ctx.problema = 'manchas amarillas'
        self.ctx.municipio = 'Guateque'
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'manchas amarillas')
        self.assertIsNotNone(pregunta)
        low = pregunta.lower()
        self.assertTrue('tomate' in low or 'entendido' in low)
        self.assertIn('parte', low)

    def test_primera_pregunta_no_rotula_zona(self):
        self.ctx.cultivo = 'café'
        self.ctx.region = 'Este'
        self.ctx.municipio = ''
        self.ctx.problema = 'manchas'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'manchas en las hojas')
        self.assertNotIn('(Este)', pregunta)
        self.assertNotIn('En café (Este)', pregunta)
        self.assertTrue(pregunta.startswith('En su café,'))
        self.assertIn('parte de la planta', pregunta.lower())

    def test_flujo_anamnesis_completa_hasta_foto(self):
        self.ctx.problema = 'manchas en hojas'
        self.ctx.municipio = 'Guateque'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

        p1 = siguiente_pregunta_diagnostico(self.ctx, 'manchas en hojas')
        self.assertIn('parte', (p1 or '').lower())

        p2 = siguiente_pregunta_diagnostico(self.ctx, 'En las hojas de abajo, como media parcela')
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('extension_afectada'))
        self.assertTrue(
            'cuánto' in (p2 or '').lower() or 'apareció' in (p2 or '').lower()
        )

        p3 = siguiente_pregunta_diagnostico(self.ctx, 'Hace como 8 días y va empeorando')
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('tiempo_problema'))
        self.assertIn('etapa', (p3 or '').lower())

        p4 = siguiente_pregunta_diagnostico(self.ctx, 'Floración')
        self.ctx.refresh_from_db()
        self.assertTrue((self.ctx.etapa or '').strip())
        self.assertIn('aplicado', (p4 or '').lower())

        p5 = siguiente_pregunta_diagnostico(self.ctx, 'Solo riego, no he fumigado')
        self.ctx.refresh_from_db()
        self.assertTrue(
            self.ctx.metadata.get('manejo_previo')
            or self.ctx.metadata.get('fertilizacion_reciente')
        )
        self.assertIn('foto', (p5 or '').lower())

        p6 = siguiente_pregunta_diagnostico(self.ctx, 'sin foto')
        self.assertIsNone(p6)

    def test_clima_con_ubicacion_salta_diagnostico(self):
        self.ctx.municipio = 'Guateque'
        self.ctx.metadata = {}  # sin anamnesis en curso
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Primero clima, ¿puedo fumigar mañana?',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_omitido'))

    def test_saltar_desactiva_diagnostico(self):
        pregunta = siguiente_pregunta_diagnostico(self.ctx, 'saltar')
        self.ctx.refresh_from_db()
        self.assertIsNone(pregunta)
        self.assertTrue(self.ctx.metadata.get('diagnostico_omitido'))

    def test_ack_sin_eco_de_pedido_largo(self):
        from core.nat_diagnostico import _ack, _sintoma_corto

        self.ctx.problema = (
            'es amarillamiento que podemos hacer en Boyaca. '
            'Con es amarillamiento que podemos hacer en tomate'
        )
        self.ctx.municipio = 'Guateque'
        self.ctx.save()
        corto = _sintoma_corto(self.ctx)
        self.assertNotIn('podemos hacer', corto.lower())
        self.assertIn('amarill', corto.lower())
        msg = _ack(
            self.ctx,
            '¿en qué parte de la planta empezó (hojas, tallo, fruto, raíz) '
            'y aproximadamente qué tanto del lote está afectado?',
        )
        self.assertNotIn('Entendido:', msg)
        self.assertNotIn('podemos hacer', msg.lower())
        self.assertIn('parte de la planta', msg.lower())
        self.assertNotIn('En tomate', msg)
        self.assertNotIn('(Guateque)', msg)
        self.assertTrue(msg.startswith('¿En qué parte'))


class NatGuionOCriterioTests(TestCase):
    """Ambiguo no abre el guion. Daño presente sí. Cómo / desde cero lo pausa."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Guion',
            contacto_principal='A',
            email='guion@test.co',
            telefono='573009990077',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009990077',
            cliente=self.cliente,
        )
        self.ctx = obtener_o_crear_contexto(self.sesion)
        self.ctx.cultivo = 'café'
        self.ctx.region = 'Huila'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

    def test_desde_cero_no_es_diagnostico_y_no_borra_la_charla(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Me gustaría saber cómo cultivar café desde cero y cómo evitar que haya problemas',
        )
        self.ctx.refresh_from_db()
        self.assertIsNone(pregunta)
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))

    def test_evitar_plagas_sin_dano_presente_tampoco_abre_el_guion(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Cómo evitar plagas si empiezo desde cero',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_despues_un_dano_presente_reabre_el_guion(self):
        siguiente_pregunta_diagnostico(
            self.ctx,
            'Quiero saber cómo arrancar café desde cero',
        )
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Ya veo manchas amarillas en las hojas',
        )
        self.ctx.refresh_from_db()
        self.assertIsNotNone(pregunta)
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.assertIn('parte', (pregunta or '').lower())

    def test_ambiguo_sin_consulta_no_abre_el_guion(self):
        self.ctx.metadata = {}
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Quería comentarle algo del lote, a ver qué me dice',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.assertFalse(self.ctx.metadata.get('diagnostico_activo'))

    def test_ambiguo_dentro_de_la_consulta_sigue_el_guion(self):
        self.ctx.problema = 'manchas en hojas'
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Pues quería comentarle algo más del lote',
        )
        self.assertIsNotNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_dano_y_desde_cero_el_dano_presente_manda(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Quiero cultivar café desde cero pero ya veo manchas en las hojas',
        )
        self.assertIsNotNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_seguimiento_durante_la_pausa_no_rellena_el_casillero(self):
        self.ctx.problema = 'manchas'
        self.ctx.metadata = {
            'diagnostico_activo': True,
            '_pregunto_extension_afectada': True,
        }
        self.ctx.save()
        siguiente_pregunta_diagnostico(
            self.ctx,
            'Mejor cuénteme cómo cultivar café desde cero',
        )
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'El suelo es arcilloso y llueve bastante',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))

    def test_entendio_va_arriba_del_mismo_mensaje(self):
        from core.nat_diagnostico import anteponer_entendio

        cuerpo = 'En café: ¿en qué parte de la planta empezó?'
        texto = anteponer_entendio(
            self.ctx,
            'Cómo cultivar café desde cero',
            cuerpo,
        )
        self.assertTrue(texto.startswith('Entendí que quiere saber cómo arrancar café.'))
        self.assertIn(cuerpo, texto)
        self.assertEqual(anteponer_entendio(self.ctx, 'otra vez', texto), texto)


class NatRomperGuionTests(TestCase):
    """Frases para tumbar el guion: saludo, precio, clima, foto y el daño de después."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Romper',
            contacto_principal='A',
            email='romper@test.co',
            telefono='573009990088',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009990088',
            cliente=self.cliente,
        )
        self.ctx = obtener_o_crear_contexto(self.sesion)
        self.ctx.cultivo = 'café'
        self.ctx.region = 'Huila'
        self.ctx.municipio = 'Pitalito'
        self.ctx.problema = 'manchas en hojas'
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()

    def _pausa(self):
        siguiente_pregunta_diagnostico(
            self.ctx,
            'Quiero saber cómo cultivar café desde cero',
        )
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_hola_con_pregunta_no_es_solo_saludo(self):
        from core.nat_diagnostico import mensaje_es_solo_saludo

        self.assertTrue(mensaje_es_solo_saludo('Hola'))
        self.assertTrue(mensaje_es_solo_saludo('Buenos días'))
        self.assertFalse(mensaje_es_solo_saludo(
            'Hola, cómo cultivo café desde cero en clima frío',
        ))
        self.assertFalse(mensaje_es_solo_saludo('Hola, ya veo manchas en el café'))
        self.assertFalse(mensaje_es_solo_saludo('Hola, cuánto vale el abono'))

    def test_precio_en_medio_no_llena_el_casillero(self):
        self.ctx.metadata = {
            'diagnostico_activo': True,
            '_pregunto_extension_afectada': True,
        }
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Y cuánto vale el fungicida para eso?',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))

    def test_clima_en_pausa_no_cierra_la_consulta(self):
        self._pausa()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Va a llover, puedo fumigar mañana?',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))
        otra = siguiente_pregunta_diagnostico(
            self.ctx,
            'Ya veo manchas nuevas en las hojas de abajo',
        )
        self.assertIsNotNone(otra)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_foto_reabre_el_guion(self):
        self._pausa()
        pregunta = siguiente_pregunta_diagnostico(self.ctx, '', tiene_imagen=True)
        self.assertIsNotNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))

    def test_reiniciar_limpia_la_pausa(self):
        self._pausa()
        siguiente_pregunta_diagnostico(self.ctx, 'reiniciar')
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.assertFalse(self.ctx.metadata.get('diagnostico_activo'))

    def test_que_hago_pausa_y_ok_no(self):
        pausa = siguiente_pregunta_diagnostico(self.ctx, 'Qué hago con estas matas')
        self.assertIsNone(pausa)
        self.ctx.refresh_from_db()
        self.assertTrue(self.ctx.metadata.get('diagnostico_en_pausa'))
        self.ctx.metadata = {'diagnostico_activo': True}
        self.ctx.save()
        sigue = siguiente_pregunta_diagnostico(self.ctx, 'ok')
        self.assertIsNotNone(sigue)

    def test_tengo_roya_si_abre_y_solo_evitarla_no(self):
        abre = siguiente_pregunta_diagnostico(
            self.ctx,
            'Tengo roya, cómo la evito',
        )
        self.assertIsNotNone(abre)
        self.ctx.metadata = {'diagnostico_activo': True, 'diagnostico_en_pausa': False}
        self.ctx.save()
        no_abre = siguiente_pregunta_diagnostico(
            self.ctx,
            'Cómo evito la roya si apenas voy a sembrar',
        )
        self.assertIsNone(no_abre)

    def test_sin_problema_desde_cero_no_abre(self):
        self.ctx.metadata = {}
        self.ctx.problema = ''
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Sin ningún problema, cómo cultivo café desde cero',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('diagnostico_omitido'))

    def test_se_estan_muriendo_si_abre(self):
        self.ctx.metadata = {}
        self.ctx.problema = ''
        self.ctx.save()
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Se me están muriendo los palos y no sé qué hago',
        )
        self.assertIsNotNone(pregunta)

    def test_audio_largo_de_como_hacer_no_pregunta_la_parte_enferma(self):
        pregunta = siguiente_pregunta_diagnostico(
            self.ctx,
            'Buenas, mire yo quiero que me explique cómo sembrar el café desde cero '
            'en tierra fría, el sombrío y cada cuánto abonar. No es que tenga una mata enferma.',
        )
        self.assertIsNone(pregunta)
        self.ctx.refresh_from_db()
        self.assertFalse(self.ctx.metadata.get('extension_afectada'))
        from core.nat_diagnostico import anteponer_entendio

        texto = anteponer_entendio(
            self.ctx,
            'cómo sembrar el café desde cero',
            'El cafetal nuevo se establece con sombrío.',
        )
        self.assertTrue(texto.startswith('Entendí que quiere saber cómo arrancar'))
