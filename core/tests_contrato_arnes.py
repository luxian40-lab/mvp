"""El arnés de contratos de línea: firma, captura en el borde, red cerrada, reloj."""
import time
from datetime import timedelta

import httpx
import requests
from django.db import connection
from django.utils import timezone

from core.meta_inbound import clasificar_mensaje
from core.tests_support.contrato_linea import (
    INSTANTE_BASE,
    LINEA_2,
    LINEA_PRINCIPAL,
    ContratoLineaTestCase,
    mensaje_boton,
    mensaje_boton_plantilla,
    mensaje_lista,
    mensaje_texto,
    payload_meta,
)

TEL = '573001112233'


class ArnesContratoTests(ContratoLineaTestCase):
    def test_corre_sobre_postgresql(self):
        self.assertEqual(connection.vendor, 'postgresql')

    def test_mensaje_firmado_responde_por_la_linea_principal(self):
        envios = self.escribir(TEL, 'hola')
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0].canal, 'meta')
        self.assertEqual(envios[0].phone_id, LINEA_PRINCIPAL.phone_id)
        self.assertEqual(envios[0].destino, TEL)
        self.assertEqual(self.salida.bloqueados, [])

    def test_linea_2_responde_por_su_phone_id(self):
        envios = self.escribir(TEL, 'hola', linea=LINEA_2)
        self.assertTrue(envios)
        self.assertEqual({e.phone_id for e in envios}, {LINEA_2.phone_id})

    def test_firma_invalida_no_entra(self):
        resp = self.publicar(payload_meta(LINEA_PRINCIPAL, TEL, mensaje_texto('hola')), firma='sha256=00')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.salida.envios, [])

    def test_cada_turno_tiene_su_wamid(self):
        primero = self.escribir(TEL, 'hola')
        segundo = self.escribir(TEL, 'hola')
        self.assertTrue(primero)
        self.assertTrue(segundo)

    def test_botones_y_listas_llegan_como_texto_al_motor(self):
        casos = (
            (mensaje_boton('acepto'), 'acepto'),
            (mensaje_lista('curso_3'), 'curso_3'),
            (mensaje_boton_plantilla('Empezar'), 'Empezar'),
        )
        for mensaje, esperado in casos:
            payload = payload_meta(LINEA_PRINCIPAL, TEL, mensaje)
            crudo = payload['entry'][0]['changes'][0]['value']['messages'][0]
            self.assertEqual(clasificar_mensaje(crudo)['texto'], esperado)

    def test_twilio_queda_capturado(self):
        from twilio.rest import Client

        Client('AC' + '0' * 32, 'token-prueba').messages.create(
            to='whatsapp:+573001112233', from_='whatsapp:+14155238886', body='hola aula',
        )
        self.assertEqual(len(self.salida.envios), 1)
        envio = self.salida.envios[0]
        self.assertEqual(envio.canal, 'twilio')
        self.assertEqual(envio.texto, 'hola aula')
        self.assertEqual(envio.destino, 'whatsapp:+573001112233')

    def test_otro_host_por_requests_falla(self):
        with self.assertRaises(requests.ConnectionError):
            requests.get('https://example.com/', timeout=1)
        self.assertEqual(self.salida.bloqueados, ['https://example.com/'])

    def test_httpx_falla(self):
        with self.assertRaises(httpx.ConnectError):
            httpx.post('https://api.openai.com/v1/chat/completions', json={})
        self.assertEqual(self.salida.bloqueados, ['https://api.openai.com/v1/chat/completions'])

    def test_llm_fijo_responde_por_chat_completions(self):
        from openai import OpenAI

        self.salida.llm_responde('TEXTO_FIJO')
        cliente = OpenAI(api_key='sk-x', max_retries=0)
        resp = cliente.chat.completions.create(model='gpt-x', messages=[{'role': 'user', 'content': 'hola'}])
        self.assertEqual(resp.choices[0].message.content, 'TEXTO_FIJO')
        self.assertEqual(self.salida.llamadas_llm[0]['messages'][0]['content'], 'hola')

    def test_clave_openai_falsa_en_el_entorno(self):
        import os

        from core.tests_support.contrato_linea import CLAVE_OPENAI_FALSA

        self.assertEqual(os.environ.get('OPENAI_API_KEY'), CLAVE_OPENAI_FALSA)

    def test_campana_de_inicio_sale_por_la_waba_de_cada_linea(self):
        from core.models import Estudiante

        uno = Estudiante.objects.create(cedula='9001', nombre='Uno', telefono='573001110101')
        dos = Estudiante.objects.create(cedula='9002', nombre='Dos', telefono='573001110102')
        principal = self.lanzar_campana([uno])
        linea_2 = self.lanzar_campana([dos], linea=LINEA_2)
        self.assertEqual([(e.tipo, e.phone_id) for e in principal], [('template', LINEA_PRINCIPAL.phone_id)])
        self.assertEqual([(e.tipo, e.phone_id) for e in linea_2], [('template', LINEA_2.phone_id)])

    def test_reloj_fijo_avanza_sin_empates(self):
        primero = timezone.now()
        segundo = timezone.now()
        self.assertGreater(segundo, primero)
        self.assertLess(segundo - INSTANTE_BASE, timedelta(seconds=1))
        self.reloj.avanzar(hours=25)
        self.assertGreater(timezone.now() - INSTANTE_BASE, timedelta(hours=25))

    def test_pausas_se_anotan_sin_esperar(self):
        inicio = time.monotonic()
        time.sleep(30)
        self.assertLess(time.monotonic() - inicio, 1)
        self.assertEqual(self.pausas.segundos, [30])
