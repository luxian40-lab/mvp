"""Tests envío certificados (campaña + diploma)."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.certificado_presencial_service import (
    enviar_certificados_seleccion,
    enviar_plantilla_inicial_certificado,
    filas_estudiantes_certificado,
    resolver_twilio_content_sid,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, Plantilla, ProgresoEstudiante
from core.models_certificados import Certificado


class EnvioCertificadosServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Envio',
            contacto_principal='A',
            email='env@test.com',
            telefono='573001111111',
            activo=True,
        )
        self.curso_pres = Curso.objects.create(
            nombre='Taller Pres', cliente=self.cliente, activo=True,
        )
        self.curso_digital = Curso.objects.create(
            nombre='Digital', cliente=self.cliente, activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso_digital, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='env1', nombre='Carlos Envio', telefono='573001111112',
            cliente=self.cliente, activo=True, estado_chat='ACTIVO',
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso_digital, modulo_actual=self.m1,
        )

    @patch('core.certificado_presencial_service.enviar_certificado_whatsapp', return_value=True)
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    @patch('core.certificado_presencial_service.enviar_previo_whatsapp')
    def test_mensaje_previo_marca_pendiente_sin_imagen_inmediata(self, mock_previo, _mock_gen, mock_cert_wa):
        mock_previo.return_value = {'success': True}
        resumen = enviar_certificados_seleccion(
            {self.est.id},
            self.curso_pres,
            mensaje_previo='Hola {nombre}',
            emitir_certificado=True,
            enviar_whatsapp_certificado=True,
        )
        self.assertEqual(resumen['mensajes_previos'], 1)
        self.assertEqual(resumen['pendientes_respuesta'], 1)
        self.assertEqual(resumen['certificados_enviados'], 0)
        mock_cert_wa.assert_not_called()
        self.est.refresh_from_db()
        self.assertIsNotNone((self.est.contexto_temporal or {}).get('cert_envio_pendiente'))

    @patch('core.certificado_presencial_service.enviar_certificado_whatsapp', return_value=True)
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    @patch('core.certificado_presencial_service.enviar_previo_whatsapp')
    def test_usa_plantilla_twilio_previo_marca_pendiente(self, mock_previo, _mock_gen, mock_cert_wa):
        pl = Plantilla.objects.create(
            nombre_interno='Cert aviso',
            cuerpo_mensaje='Hola {{1}}',
            activa=True,
            aprobada_twilio=True,
            twilio_template_sid='HXprevio123',
        )
        mock_previo.return_value = {'success': True}
        resumen = enviar_certificados_seleccion(
            {self.est.id},
            self.curso_pres,
            twilio_content_sid_previo=resolver_twilio_content_sid(plantilla_id=pl.id),
            emitir_certificado=True,
            enviar_whatsapp_certificado=True,
        )
        self.assertEqual(resumen['mensajes_previos'], 1)
        self.assertEqual(resumen['pendientes_respuesta'], 1)
        mock_previo.assert_called_once()
        mock_cert_wa.assert_not_called()

    @patch('core.certificado_service._intentar_enviar_imagen_diploma', return_value=({'success': True}, 'imagen'))
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_imagen_diploma_tras_plantilla_previo(self, _mock_gen, mock_intento):
        from core.certificado_service import enviar_certificado_whatsapp
        from django.utils import timezone

        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso_pres,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            archivo_imagen='certificados/generados/test.png',
        )
        ok = enviar_certificado_whatsapp(cert, tras_plantilla_previo=True)
        self.assertTrue(ok)
        mock_intento.assert_called_once()
        _, kwargs = mock_intento.call_args
        self.assertTrue(kwargs.get('pausa_inicial') >= 0)

    @patch('core.certificado_service._enviar_plantilla_media_twilio', return_value={'success': True, 'mensaje_id': 'MMmedia'})
    def test_plantilla_media_entrega_imagen_en_un_mensaje(self, mock_tpl):
        from core.certificado_service import enviar_certificado_whatsapp
        from core.models_certificados import Certificado
        from django.utils import timezone

        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso_pres,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            archivo_imagen='certificados/generados/test.png',
        )
        ok = enviar_certificado_whatsapp(
            cert,
            twilio_content_sid_media='HXmedia123',
            media_var_index='1',
        )
        self.assertTrue(ok)
        mock_tpl.assert_called_once()
        args, _ = mock_tpl.call_args
        self.assertEqual(args[1], 'HXmedia123')
        variables = args[2]
        self.assertIn('amazonaws.com', variables['1'])
        cert.refresh_from_db()
        self.assertTrue(cert.enviado_whatsapp)

    @patch('core.certificado_presencial_service._enviar_plantilla_twilio_cert', return_value={'success': True})
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_plantilla_inicial_marca_pendiente(self, _mock_gen, mock_tpl):
        resumen = enviar_plantilla_inicial_certificado(
            {self.est.id},
            self.curso_pres,
            twilio_content_sid_inicial='HXinicial',
            emitir_certificado=True,
        )
        self.assertEqual(resumen['plantillas_enviadas'], 1)
        self.assertEqual(resumen['pendientes'], 1)
        mock_tpl.assert_called_once()
        self.est.refresh_from_db()
        pend = (self.est.contexto_temporal or {}).get('cert_envio_pendiente')
        self.assertIsNotNone(pend)
        cert = Certificado.objects.get(estudiante=self.est, curso=self.curso_pres)
        self.assertEqual(pend['certificado_id'], cert.id)

    def test_ack_certificado_acepta_ok_y_rechaza_listo(self):
        from core.views import _es_ack_certificado

        for val in ('ok', 'OK', 'Ok!', 'sí', 'dale', '1', '25', 'ok gracias', 'hola', 'gracias'):
            self.assertTrue(_es_ack_certificado(val), val)
        for val in ('listo', 'continuar', 'menú', '', 'listo✅'):
            self.assertFalse(_es_ack_certificado(val), val)

    @patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True)
    def test_webhook_libera_certificado_con_cualquier_respuesta(self, mock_envia):
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso_pres,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/x.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {'certificado_id': cert.id, 'curso_id': self.curso_pres.id},
        }
        self.est.save(update_fields=['contexto_temporal'])

        self.assertTrue(
            _intentar_responder_envio_certificado(self.est, 'gracias', self.est.telefono, self.est.telefono),
        )
        mock_envia.assert_called_once()

    @patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True)
    def test_webhook_libera_certificado_con_ok_en_habeas(self, mock_envia):
        """OK con cert pendiente no debe confundirse con Habeas (estado_chat nuevo)."""
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        self.est.estado_chat = 'ESPERANDO_HABEAS_DATA'
        self.est.acepto_terminos = False
        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso_pres,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/x.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {'certificado_id': cert.id, 'curso_id': self.curso_pres.id},
        }
        self.est.save()

        self.assertTrue(
            _intentar_responder_envio_certificado(self.est, 'Ok', self.est.telefono, self.est.telefono),
        )
        mock_envia.assert_called_once()

    @patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True)
    def test_webhook_libera_certificado_con_ok(self, mock_envia):
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso_pres,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/x.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {'certificado_id': cert.id, 'curso_id': self.curso_pres.id},
        }
        self.est.save(update_fields=['contexto_temporal'])

        self.assertFalse(
            _intentar_responder_envio_certificado(self.est, 'listo', self.est.telefono, self.est.telefono),
        )
        mock_envia.assert_not_called()

        self.assertTrue(
            _intentar_responder_envio_certificado(self.est, 'OK', self.est.telefono, self.est.telefono),
        )
        mock_envia.assert_called_once()
        self.est.refresh_from_db()
        self.assertNotIn('cert_envio_pendiente', (self.est.contexto_temporal or {}))


class CerrarCursoAlDiplomaTests(TestCase):
    """Regla escalable: penúltimo o último módulo + diploma = curso finalizado."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Cierre', contacto_principal='A', email='cierre@test.com',
            telefono='573003333331', activo=True,
        )
        self.curso = Curso.objects.create(nombre='Crea Cierre', cliente=self.cliente, activo=True)
        self.m7 = Modulo.objects.create(curso=self.curso, numero=7, titulo='M7', descripcion='d', contenido='c')
        self.m8 = Modulo.objects.create(curso=self.curso, numero=8, titulo='Proyecto', descripcion='d', contenido='c')
        self.m9 = Modulo.objects.create(curso=self.curso, numero=9, titulo='Felicitaciones', descripcion='d', contenido='c')
        self.est = Estudiante.objects.create(
            cedula='cierre1', nombre='Lina Cierre', telefono='573003333332',
            cliente=self.cliente, activo=True, estado_chat='ACTIVO',
        )

    def _progreso(self, modulo):
        return ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=modulo, completado=False,
        )

    def test_penultimo_cierra_al_llegar_diploma(self):
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        self._progreso(self.m8)
        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/cierre.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {
                'certificado_id': cert.id,
                'curso_id': self.curso.id,
                'cerrar_avance': True,
            },
        }
        self.est.save(update_fields=['contexto_temporal'])

        with patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True):
            self.assertTrue(
                _intentar_responder_envio_certificado(self.est, 'OK', self.est.telefono, self.est.telefono),
            )

        prog = ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)
        self.assertTrue(prog.completado)
        self.assertEqual(prog.modulo_actual_id, self.m9.id)
        nums = set(
            ModuloCompletado.objects.filter(progreso=prog).values_list('modulo__numero', flat=True)
        )
        self.assertEqual(nums, {8, 9})
        self.assertFalse(ModuloCompletado.objects.filter(progreso=prog, modulo=self.m7).exists())

    def test_modulo_intermedio_no_cierra(self):
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        self._progreso(self.m7)
        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/cierre.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {
                'certificado_id': cert.id,
                'curso_id': self.curso.id,
                'cerrar_avance': True,
            },
        }
        self.est.save(update_fields=['contexto_temporal'])

        with patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True):
            _intentar_responder_envio_certificado(self.est, 'OK', self.est.telefono, self.est.telefono)

        prog = ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)
        self.assertFalse(prog.completado)
        self.assertEqual(prog.modulo_actual_id, self.m7.id)

    def test_sin_flag_no_cierra(self):
        from django.utils import timezone

        from core.views import _intentar_responder_envio_certificado

        self._progreso(self.m8)
        hoy = timezone.now().date()
        cert = Certificado.objects.create(
            estudiante=self.est, curso=self.curso,
            calificacion_final=100, fecha_inicio=hoy, fecha_completado=hoy,
            emitido=True, archivo_imagen='certificados/generados/cierre.png',
        )
        self.est.contexto_temporal = {
            'cert_envio_pendiente': {'certificado_id': cert.id, 'curso_id': self.curso.id},
        }
        self.est.save(update_fields=['contexto_temporal'])

        with patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True):
            _intentar_responder_envio_certificado(self.est, 'OK', self.est.telefono, self.est.telefono)

        prog = ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)
        self.assertFalse(prog.completado)

    @patch('core.certificado_presencial_service.enviar_certificado_whatsapp', return_value=True)
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_envio_directo_cierra_ultimo_modulo(self, _gen, _wa):
        from core.certificado_presencial_service import enviar_certificados_seleccion

        self._progreso(self.m9)
        resumen = enviar_certificados_seleccion(
            {self.est.id},
            self.curso,
            emitir_certificado=True,
            enviar_whatsapp_certificado=True,
            cerrar_avance=True,
        )
        self.assertEqual(resumen['cursos_cerrados'], 1)
        prog = ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)
        self.assertTrue(prog.completado)


class EnvioCertificadosAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_env', 'env@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Admin Env', contacto_principal='B', email='aenv@test.com',
            telefono='573002222221', activo=True,
        )
        self.curso = Curso.objects.create(nombre='CP Env', cliente=self.cliente, activo=True)
        self.est = Estudiante.objects.create(
            cedula='a1', nombre='Ana Env', telefono='573002222222', cliente=self.cliente, activo=True,
        )
        self.http = Client()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_carga(self):
        self.http.login(username='admin_env', password='pass')
        r = self.http.get(
            f'/admin/envio-certificados/?cliente={self.cliente.id}&curso={self.curso.id}'
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Envío certificados')
        self.assertContains(r, 'Enviar a seleccionados')
        self.assertContains(r, 'Plantilla Twilio')
        self.assertContains(r, 'Reenviar solo WhatsApp')
        self.assertContains(r, 'Ana Env')

    def test_extra_mantiene_estudiante_en_busqueda(self):
        otro = Estudiante.objects.create(
            cedula='a2', nombre='Bruno Extra', telefono='573002222223', cliente=self.cliente, activo=True,
        )
        filas = filas_estudiantes_certificado(
            self.cliente,
            self.curso,
            busqueda_global='Bruno',
            extra_estudiante_ids={self.est.id},
        )
        nombres = {f['estudiante'].nombre for f in filas}
        self.assertIn('Bruno Extra', nombres)
        self.assertIn('Ana Env', nombres)

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_incluye_seleccion_acumulada(self):
        self.http.login(username='admin_env', password='pass')
        r = self.http.get(
            f'/admin/envio-certificados/?cliente={self.cliente.id}&curso={self.curso.id}&extra={self.est.id}'
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Selección acumulada')
        self.assertContains(r, 'ec-extra-ids')

    def test_legacy_presenciales_redirige(self):
        self.http.login(username='admin_env', password='pass')
        r = self.http.get(f'/admin/certificados-presenciales/?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/envio-certificados/', r['Location'])
