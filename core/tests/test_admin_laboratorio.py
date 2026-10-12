"""Laboratorio: mismo camino de respuesta, sin WhatsApp y sin cupo."""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Cliente, ConversacionRAGCandidata, EventoIA, WhatsappLog
from core.models_agentes import ConocimientoAgente, PruebaAgente


@override_settings(SECURE_SSL_REDIRECT=False, ADMIN_AGENTES_V2=False)
class LaboratorioTests(TestCase):
    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.user = get_user_model().objects.create_superuser(
            f'lab_{self.tag}', f'lab-{self.tag}@x.co', 'pass12345',
        )
        self.org = Cliente.objects.create(
            nombre=f'Org {self.tag}',
            contacto_principal='a',
            email=f'lab-{self.tag}@example.com',
            telefono=f'57311{self.tag[:7]}',
        )
        cache.clear()
        self.http = Client()
        self.http.force_login(self.user)
        self.url = reverse('laboratorio_agentes')
        self.http.get(self.url)

    def test_el_personal_la_abre_y_un_visitante_no(self):
        personal = get_user_model().objects.create_user(
            f'staff_{self.tag}', f'staff-{self.tag}@x.co', 'pass12345', is_staff=True,
        )
        sesion = Client()
        sesion.force_login(personal)
        respuesta = sesion.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Laboratorio')
        visitante = Client()
        self.assertEqual(visitante.get(self.url).status_code, 302)

    def test_pregunta_no_envia_whatsapp_ni_usa_memoria(self):
        ConocimientoAgente.objects.create(
            agente='ventas',
            titulo=f'Sombra {self.tag}',
            contenido='El cultivo pide sombra.',
            estado=ConocimientoAgente.ESTADO_APROBADO,
        )
        with patch(
            'core.sandbox_agentes.responder_agente_sandbox',
            return_value='El suelo necesita sombra.',
        ) as llamado:
            respuesta = self.http.post(self.url, {
                'accion': 'preguntar',
                'agente': 'ventas',
                'pregunta': 'Como mejoro el suelo',
                'cliente': str(self.org.pk),
                'plan': '',
            }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El suelo necesita sombra.')
        self.assertContains(respuesta, f'Sombra {self.tag}')
        self.assertContains(respuesta, 'Sin dato')
        llamado.assert_called_once()
        self.assertEqual(llamado.call_args.kwargs['telefono'], '')
        self.assertEqual(llamado.call_args.kwargs['cliente_id'], self.org.pk)
        self.assertEqual(WhatsappLog.objects.count(), 0)
        evento = EventoIA.objects.get()
        self.assertEqual(evento.metadata.get('origen'), 'laboratorio')
        self.assertEqual(evento.canal, EventoIA.CANAL_ADMIN)
        self.assertEqual(evento.cliente_id, self.org.pk)

    def test_estuvo_mal_abre_una_candidata_pendiente(self):
        with patch(
            'core.sandbox_agentes.responder_agente_sandbox',
            return_value='Respuesta de prueba.',
        ):
            self.http.post(self.url, {
                'accion': 'preguntar',
                'agente': 'coach',
                'pregunta': 'Como organizo la cosecha',
                'cliente': '',
                'plan': '',
            })
        respuesta = self.http.post(self.url, {'accion': 'mal'}, follow=False)
        self.assertEqual(respuesta.status_code, 302)
        candidata = ConversacionRAGCandidata.objects.get()
        self.assertEqual(candidata.estado, ConversacionRAGCandidata.ESTADO_PENDIENTE)
        self.assertEqual(candidata.telefono, 'laboratorio')
        self.assertEqual(candidata.pregunta, 'Como organizo la cosecha')
        self.assertIn(str(candidata.pk), respuesta['Location'])

    def test_guardar_y_correr_usa_criterio_de_texto(self):
        self.http.post(self.url, {
            'accion': 'guardar',
            'agente': 'cafe',
            'pregunta': 'Que variedad conviene',
            'cliente': '',
            'plan': '',
            'debe_mencionar': 'sombra',
            'no_debe_mencionar': '',
            'debe_usar_fuente': '',
        })
        self.assertEqual(PruebaAgente.objects.count(), 1)
        with patch(
            'core.sandbox_agentes.responder_agente_sandbox',
            return_value='Conviene cultivar a la sombra.',
        ):
            self.http.post(self.url, {'accion': 'correr'})
        prueba = PruebaAgente.objects.get()
        self.assertEqual(prueba.ultimo_resultado, PruebaAgente.RESULTADO_PASA)
        self.assertEqual(prueba.corridas, 1)
        self.assertIsNotNone(prueba.ultima_corrida)
        self.assertEqual(WhatsappLog.objects.count(), 0)

    @override_settings(LABORATORIO_TOPE_PRUEBAS=1)
    def test_correr_respeta_el_tope(self):
        PruebaAgente.objects.create(agente='cafe', pregunta='Primera', debe_mencionar='sombra')
        PruebaAgente.objects.create(agente='cafe', pregunta='Segunda', debe_mencionar='sombra')
        with patch(
            'core.sandbox_agentes.responder_agente_sandbox',
            return_value='Hay sombra.',
        ) as llamado:
            self.http.post(self.url, {'accion': 'correr'})
        self.assertEqual(llamado.call_count, 1)
        self.assertEqual(PruebaAgente.objects.filter(corridas=1).count(), 1)

    @override_settings(LABORATORIO_TOPE_HORA=1)
    def test_la_segunda_de_la_hora_no_llama_al_modelo(self):
        datos = {
            'accion': 'preguntar',
            'agente': 'finanzas',
            'pregunta': 'Como llevo las cuentas',
            'cliente': '',
            'plan': '',
        }
        with patch(
            'core.sandbox_agentes.responder_agente_sandbox',
            return_value='Lleve un cuaderno.',
        ) as llamado:
            self.http.post(self.url, datos, follow=True)
            segunda = self.http.post(self.url, datos, follow=True)
        self.assertEqual(llamado.call_count, 1)
        self.assertContains(segunda, 'tope de pruebas de esta hora')
