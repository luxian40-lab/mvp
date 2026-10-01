"""Tests menú sandbox: Agentes (submenú) | Cursos Riendas + correlador territorial."""

from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import MagicMock, patch

from core.event_engine import correlacionar_clusters, publicar_evento, registrar_senal_territorial
from core.models import AlertaTerritorial, EventOutbox, SandboxCanalSesion, SenalTerritorial
from core.sandbox_menu import (
    MODO_AGENTES,
    MODO_COACH,
    MODO_CURSOS,
    MODO_IA_CAMPO,
    MODO_MENU,
    MODO_NAT,
    MODO_VENTAS,
    TEXTO_AGENTES,
    TEXTO_MENU,
    dispatch_sandbox_menu,
    es_destino_sandbox,
    memoria_corte_nat,
    resolver_ruta_sandbox,
)


def _habeas(telefono: str) -> None:
    SandboxCanalSesion.objects.update_or_create(
        telefono=telefono,
        defaults={'habeas_aceptado': True},
    )


@override_settings(
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    EKI_DEMO_RIENDAS_CURSO_ID='36',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
)
class SandboxMenuTests(TestCase):
    def test_solo_sandbox_es_destino(self):
        self.assertTrue(es_destino_sandbox({'To': 'whatsapp:+14155238886'}))
        self.assertFalse(es_destino_sandbox({'To': 'whatsapp:+573001111111'}))

    def test_primer_mensaje_muestra_menu(self):
        d = resolver_ruta_sandbox({
            'From': 'whatsapp:+573001234567',
            'To': 'whatsapp:+14155238886',
            'Body': 'hola',
        })
        self.assertEqual(d.action, 'show_menu')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234567').modo,
            MODO_MENU,
        )

    def test_elige_agentes_muestra_submenu(self):
        base = {
            'From': 'whatsapp:+573001234568',
            'To': 'whatsapp:+14155238886',
        }
        d1 = resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        self.assertEqual(d1.action, 'show_agentes')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234568').modo,
            MODO_AGENTES,
        )

    def test_submenu_agronomo_continua_sin_reset(self):
        base = {
            'From': 'whatsapp:+573001234571',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        d = resolver_ruta_sandbox({**base, 'Body': '1'})
        self.assertEqual(d.action, 'nat')
        self.assertFalse(d.reset_nat)
        self.assertTrue(d.saludo_entrada)
        ses = SandboxCanalSesion.objects.get(telefono='573001234571')
        self.assertEqual(ses.modo, MODO_NAT)
        self.assertIsNone(ses.memoria_corte_en)

    def test_reiniciar_corta_memoria_en_agente(self):
        base = {
            'From': 'whatsapp:+573001234580',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        resolver_ruta_sandbox({**base, 'Body': '2'})  # coach
        d = resolver_ruta_sandbox({**base, 'Body': 'reiniciar'})
        self.assertEqual(d.action, MODO_COACH)
        self.assertTrue(d.reset_nat)

    def test_submenu_coach_y_ia_campo(self):
        base = {
            'From': 'whatsapp:+573001234572',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        d2 = resolver_ruta_sandbox({**base, 'Body': '2'})
        self.assertEqual(d2.action, 'coach')
        self.assertTrue(d2.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234572').modo,
            MODO_COACH,
        )
        resolver_ruta_sandbox({**base, 'Body': 'menu'})
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        d3 = resolver_ruta_sandbox({**base, 'Body': '3'})
        self.assertEqual(d3.action, 'ia_campo')
        self.assertTrue(d3.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234572').modo,
            MODO_IA_CAMPO,
        )
        resolver_ruta_sandbox({**base, 'Body': 'menu'})
        resolver_ruta_sandbox({**base, 'Body': 'agentes'})
        d4 = resolver_ruta_sandbox({**base, 'Body': '4'})
        self.assertEqual(d4.action, 'ventas')
        self.assertTrue(d4.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234572').modo,
            MODO_VENTAS,
        )

    def test_atajo_ventas_desde_raiz(self):
        d = resolver_ruta_sandbox({
            'From': 'whatsapp:+573001234583',
            'To': 'whatsapp:+14155238886',
            'Body': 'ventas',
        })
        self.assertEqual(d.action, 'ventas')
        self.assertTrue(d.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234583').modo,
            MODO_VENTAS,
        )

    def test_elige_cursos_sin_inscripcion_no_sticky(self):
        base = {
            'From': 'whatsapp:+573001234569',
            'To': 'whatsapp:+14155238886',
        }
        self.assertEqual(
            resolver_ruta_sandbox({**base, 'Body': 'curso'}).action,
            'cursos_bootstrap',
        )
        _habeas('573001234569')
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': 'curso'})
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234569').modo,
            MODO_MENU,
        )

    def test_inscrito_continuar_su_curso(self):
        from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

        org = Cliente.objects.create(
            nombre='Org inscrita',
            nit='800111224-1',
            activo=True,
            contacto_principal='x',
            email='org@eki.co',
            telefono='57300',
        )
        curso = Curso.objects.create(
            nombre='Impulso rural',
            cliente=org,
            activo=True,
        )
        est = Estudiante.objects.create(
            nombre='Ana',
            cedula='1088004',
            telefono='573001234585',
            cliente=org,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as send:
            out = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234585',
                'To': 'whatsapp:+14155238886',
                'Body': 'curso',
            })
        self.assertEqual(out, 'handled')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234585').modo,
            MODO_CURSOS,
        )
        est.refresh_from_db()
        self.assertEqual((est.contexto_temporal or {}).get('curso_activo_id'), curso.id)
        texto = send.call_args[0][2]
        self.assertIn('Impulso rural', texto)
        self.assertIn('listo', texto.lower())
        self.assertNotIn('riendas', texto.lower())
        self.assertEqual(
            resolver_ruta_sandbox({
                'From': 'whatsapp:+573001234585',
                'To': 'whatsapp:+14155238886',
                'Body': 'listo',
            }).action,
            'cursos',
        )

    def test_b2b_elige_cursos_no_queda_sticky_ni_inscrito(self):
        from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

        otro = Cliente.objects.create(
            nombre='Org B2B menú',
            nit='800111223-1',
            activo=True,
            contacto_principal='x',
            email='b2b@eki.co',
            telefono='57300',
        )
        demo = Cliente.objects.create(
            nombre='eki Demo menú',
            nit='900888778-1',
            activo=True,
            contacto_principal='eki',
            email='demo2@eki.co',
            telefono='57300',
        )
        curso = Curso.objects.create(
            nombre='Demo · Riendas menú',
            cliente=demo,
            activo=True,
        )
        Estudiante.objects.create(
            nombre='Cohorte',
            cedula='1088003',
            telefono='573001234584',
            cliente=otro,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        with override_settings(
            EKI_DEMO_RIENDAS_CURSO_ID=str(curso.id),
            EKI_DEMO_RIENDAS_ORIGEN_ID='999999',
        ):
            with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}), patch(
                'core.catalogo_demo_carousel.sincronizar_demo_riendas_desde_prod',
                return_value={'ok': False},
            ), patch(
                'core.sandbox_canal.enviar_sandbox', return_value={'success': True}
            ):
                out = dispatch_sandbox_menu({
                    'From': 'whatsapp:+573001234584',
                    'To': 'whatsapp:+14155238886',
                    'Body': 'curso',
                })
        self.assertEqual(out, 'handled')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234584').modo,
            MODO_MENU,
        )
        self.assertFalse(
            ProgresoEstudiante.objects.filter(
                estudiante__telefono='573001234584',
                curso=curso,
            ).exists()
        )

    def test_hola_desde_cursos_vuelve_al_menu(self):
        base = {
            'From': 'whatsapp:+573001234581',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': '2'})
        d = resolver_ruta_sandbox({**base, 'Body': 'hola'})
        self.assertEqual(d.action, 'show_menu')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234581').modo,
            MODO_MENU,
        )

    def test_audio_en_coach_usa_transcripcion(self):
        tel_from = 'whatsapp:+573001234582'
        to = 'whatsapp:+14155238886'
        resolver_ruta_sandbox({'From': tel_from, 'To': to, 'Body': 'agentes'})
        resolver_ruta_sandbox({'From': tel_from, 'To': to, 'Body': '2'})
        audio_payload = {
            'From': tel_from,
            'To': to,
            'Body': '',
            'NumMedia': '1',
            'MediaUrl0': 'https://api.twilio.com/audio.ogg',
            'MediaContentType0': 'audio/ogg',
        }
        with patch(
            'core.views._transcribir_audio_twilio',
            return_value='me cuesta organizar el tiempo',
        ):
            d = resolver_ruta_sandbox(audio_payload)
        self.assertEqual(d.action, 'coach')
        self.assertFalse(d.saludo_entrada)

    def test_dispatch_agentes_handled(self):
        _habeas('573001234570')
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            self.assertEqual(
                dispatch_sandbox_menu({
                    'From': 'whatsapp:+573001234570',
                    'To': 'whatsapp:+14155238886',
                    'Body': 'agentes',
                }),
                'handled',
            )

    def test_dispatch_nat_entrada_no_resetea(self):
        base = {
            'From': 'whatsapp:+573001234573',
            'To': 'whatsapp:+14155238886',
        }
        _habeas('573001234573')
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': 'agentes'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as send:
            out = dispatch_sandbox_menu({**base, 'Body': '1'})
        self.assertEqual(out, 'handled')
        self.assertTrue(send.called)
        self.assertIsNone(memoria_corte_nat('573001234573'))

    def test_dispatch_reiniciar_nat_marca_corte(self):
        base = {
            'From': 'whatsapp:+573001234576',
            'To': 'whatsapp:+14155238886',
        }
        _habeas('573001234576')
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': 'agentes'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': '1'})  # entra Nat sin corte
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            out = dispatch_sandbox_menu({**base, 'Body': 'reiniciar'})
        self.assertEqual(out, 'handled')
        self.assertIsNotNone(memoria_corte_nat('573001234576'))

    def test_dispatch_cursos_bootstrap_riendas(self):
        _habeas('573001234574')
        with patch('core.sandbox_menu.bootstrap_cursos_sandbox', return_value=True) as boot:
            out = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234574',
                'To': 'whatsapp:+14155238886',
                'Body': 'curso',
            })
        self.assertEqual(out, 'handled')
        self.assertTrue(boot.called)

    def test_dispatch_coach_handled(self):
        base = {
            'From': 'whatsapp:+573001234575',
            'To': 'whatsapp:+14155238886',
        }
        _habeas('573001234575')
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': 'agentes'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            self.assertEqual(dispatch_sandbox_menu({**base, 'Body': '2'}), 'handled')

    def test_dispatch_ventas_handled(self):
        base = {
            'From': 'whatsapp:+573001234577',
            'To': 'whatsapp:+14155238886',
        }
        _habeas('573001234577')
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': 'agentes'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            self.assertEqual(dispatch_sandbox_menu({**base, 'Body': '4'}), 'handled')

    def test_copy_menu_sin_sandbox_y_cuatro_agentes(self):
        self.assertNotIn('sandbox', TEXTO_MENU.lower())
        self.assertNotIn('riendas', TEXTO_MENU.lower())
        self.assertIn('formación', TEXTO_MENU.lower())
        self.assertIn('30', TEXTO_MENU)
        self.assertNotIn('sandbox', TEXTO_AGENTES.lower())
        self.assertIn('Agrónomo', TEXTO_AGENTES)
        self.assertIn('Coach', TEXTO_AGENTES)
        self.assertIn('Profe IA', TEXTO_AGENTES)
        self.assertIn('Ventas', TEXTO_AGENTES)
        self.assertIn('reiniciar', TEXTO_AGENTES)

    def test_limites_ia_linea_meta(self):
        from core.sandbox_agentes import excedio_cupo_ia_linea, max_tokens_linea_meta

        self.assertLessEqual(max_tokens_linea_meta(), 400)
        self.assertGreaterEqual(max_tokens_linea_meta(), 120)
        self.assertFalse(excedio_cupo_ia_linea('573001239999'))

    def test_menu_formacion_y_asesoria_enrutan(self):
        base = {
            'From': 'whatsapp:+573001234590',
            'To': 'whatsapp:+14155238886',
        }
        d = resolver_ruta_sandbox({**base, 'Body': 'formacion'})
        self.assertEqual(d.action, 'show_formacion')
        d2 = resolver_ruta_sandbox({**base, 'Body': 'quiero vender mejor mi café'})
        self.assertEqual(d2.action, 'cursos_bootstrap')

        base_a = {
            'From': 'whatsapp:+573001234591',
            'To': 'whatsapp:+14155238886',
        }
        d3 = resolver_ruta_sandbox({**base_a, 'Body': 'asesoria'})
        self.assertEqual(d3.action, 'show_asesoria')
        d4 = resolver_ruta_sandbox({**base_a, 'Body': 'cómo subo el precio a mis clientes'})
        self.assertEqual(d4.action, 'ventas')
        self.assertTrue(d4.saludo_entrada)

    def test_habeas_antes_del_menu(self):
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            out = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234592',
                'To': 'whatsapp:+14155238886',
                'Body': 'hola',
            })
        self.assertEqual(out, 'handled')
        self.assertTrue(habeas.called)
        self.assertFalse(
            SandboxCanalSesion.objects.get(telefono='573001234592').habeas_aceptado
        )
        with patch('core.sandbox_menu.enviar_menu_sandbox', return_value={'success': True}) as menu:
            out2 = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234592',
                'To': 'whatsapp:+14155238886',
                'Body': 'acepto',
            })
        self.assertEqual(out2, 'handled')
        self.assertTrue(menu.called)
        self.assertTrue(
            SandboxCanalSesion.objects.get(telefono='573001234592').habeas_aceptado
        )

    def test_cupo_asesor_cuenta_el_mes(self):
        from datetime import timedelta

        from core.models import WhatsappLog
        from core.planes_linea import registrar_pregunta_asesor
        from core.sandbox_agentes import excedio_cupo_ia_linea

        tel = '573009991111'
        _habeas(tel)
        for _ in range(40):
            WhatsappLog.objects.create(
                telefono=tel, tipo='SENT', agente_usado='sandbox_cursos', mensaje='clase'
            )
        self.assertFalse(excedio_cupo_ia_linea(tel))
        for _ in range(30):
            registrar_pregunta_asesor(tel)
        self.assertTrue(excedio_cupo_ia_linea(tel))
        SandboxCanalSesion.objects.filter(telefono=tel).update(
            preguntas_mes_desde=(timezone.localdate().replace(day=1) - timedelta(days=2)).replace(day=1)
        )
        self.assertFalse(excedio_cupo_ia_linea(tel))
        registrar_pregunta_asesor(tel)
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=tel).preguntas_mes, 1)

    def test_prompt_ventas_aplicable_manana(self):
        from core.sandbox_agentes import PROMPT_VENTAS, prompt_para, saludo_agente

        self.assertEqual(prompt_para('ventas'), PROMPT_VENTAS)
        self.assertIn('¿cómo lo aplica mañana', PROMPT_VENTAS.lower())
        self.assertIn('propuesta de valor', PROMPT_VENTAS.lower())
        self.assertIn('WhatsApp', PROMPT_VENTAS)
        self.assertIn('mentor de ventas', saludo_agente('ventas').lower())
        self.assertIn('No cambie de tema', prompt_para('coach'))

    def test_coach_reintenta_si_el_modelo_viene_vacio(self):
        vacio = MagicMock(choices=[MagicMock(message=MagicMock(content=''))])
        bueno = MagicMock(choices=[MagicMock(message=MagicMock(
            content='El miedo a fallar se trabaja con un paso chico y reversible.',
        ))])
        falso = MagicMock()
        falso.chat.completions.create.side_effect = [vacio, bueno]
        with override_settings(OPENAI_API_KEY='sk-test', BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini'), patch(
            'openai.OpenAI', return_value=falso,
        ):
            from core.sandbox_agentes import responder_agente_sandbox

            texto = responder_agente_sandbox('coach', 'Miedo a fallar', telefono='573162395085')
        self.assertIn('miedo', texto.lower())
        self.assertNotIn('ordenar números', texto)
        self.assertEqual(falso.chat.completions.create.call_count, 2)
        primero = falso.chat.completions.create.call_args_list[0].kwargs
        segundo = falso.chat.completions.create.call_args_list[1].kwargs
        self.assertGreaterEqual(primero.get('max_completion_tokens') or 0, 900)
        self.assertEqual(segundo.get('reasoning_effort'), 'minimal')

    def test_coach_sin_texto_no_cambia_de_tema(self):
        vacio = MagicMock(choices=[MagicMock(message=MagicMock(content=''))])
        falso = MagicMock()
        falso.chat.completions.create.return_value = vacio
        with override_settings(OPENAI_API_KEY='sk-test', BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini'), patch(
            'openai.OpenAI', return_value=falso,
        ):
            from core.sandbox_agentes import responder_agente_sandbox

            texto = responder_agente_sandbox('coach', 'Miedo a fallar', telefono='573162395085')
        self.assertIn('miedo a fallar', texto.lower())
        self.assertIn('10 minutos', texto)
        self.assertNotIn('ordenar números', texto)
        self.assertNotIn('repítame', texto.lower())

    def test_coach_reintenta_si_el_primer_intento_falla(self):
        bueno = MagicMock(choices=[MagicMock(message=MagicMock(
            content='El miedo a fallar se trabaja con un paso chico.',
        ))])
        falso = MagicMock()
        falso.chat.completions.create.side_effect = [RuntimeError('timeout'), bueno]
        with override_settings(OPENAI_API_KEY='sk-test', BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini'), patch(
            'openai.OpenAI', return_value=falso,
        ):
            from core.sandbox_agentes import responder_agente_sandbox

            texto = responder_agente_sandbox('coach', 'Miedo a fallar', telefono='573162395085')
        self.assertIn('miedo', texto.lower())
        self.assertEqual(falso.chat.completions.create.call_count, 2)

    def test_ventas_y_profe_contestan_aunque_el_modelo_falle(self):
        vacio = MagicMock(choices=[MagicMock(message=MagicMock(content=''))])
        falso = MagicMock()
        falso.chat.completions.create.return_value = vacio
        with override_settings(OPENAI_API_KEY='sk-test', BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini'), patch(
            'openai.OpenAI', return_value=falso,
        ):
            from core.sandbox_agentes import responder_agente_sandbox

            ventas = responder_agente_sandbox('ventas', 'no me compran el café', telefono='573162395085')
            profe = responder_agente_sandbox('ia_campo', 'cómo uso la ia para un aviso', telefono='573162395085')
        self.assertIn('café', ventas.lower())
        self.assertIn('cliente', ventas.lower())
        self.assertNotIn('repítame', ventas.lower())
        self.assertIn('aviso', profe.lower())
        self.assertIn('ayudante', profe.lower())


@override_settings(DATA_LAKE_ENABLED=False)
class EventEngineClusterTests(TestCase):
    def test_outbox_publicar(self):
        row = publicar_evento(
            event_type='aprendizaje.listo.recibido',
            payload={'ok': True},
            territory_id='05001',
            org_id=1,
        )
        self.assertTrue(EventOutbox.objects.filter(pk=row.pk).exists())
        self.assertIsNone(row.published_at)

    def test_cluster_density_v0(self):
        now = timezone.now()
        for i in range(3):
            registrar_senal_territorial(
                tipo='salud.sintoma.diarrea',
                territory_id='05001',
                confianza=0.8,
                occurred_at=now,
                metadata={'i': i},
            )
        self.assertEqual(
            AlertaTerritorial.objects.filter(territory_id='05001', estado='detectada').count(),
            1,
        )
        registrar_senal_territorial(
            tipo='salud.sintoma.diarrea',
            territory_id='11001',
            confianza=0.8,
            occurred_at=now,
        )
        alertas = correlacionar_clusters(ventana_horas=72, min_k=3)
        self.assertEqual(len(alertas), 1)
        a = alertas[0]
        self.assertEqual(a.territory_id, '05001')
        self.assertEqual(a.conteo, 3)
        self.assertEqual(SenalTerritorial.objects.count(), 4)
        self.assertEqual(AlertaTerritorial.objects.filter(estado='detectada').count(), 1)
