"""Inicio del admin: datos, filas de acción, líneas y cache."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core.admin.home_data import (
    construir_inicio,
    estado_una_linea,
    home_para,
    invalidar_home,
)
from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante, WhatsappLog
from core.models_campana_meta import PlantillaMeta
from core.models_certificados import Certificado
from core.models_meta_webhook import MetaWebhookEvento


def _cliente():
    from core.models import Cliente

    return Cliente.objects.create(
        nombre='Org inicio',
        contacto_principal='A',
        email='inicio@test.com',
        telefono='573001110080',
        activo=True,
        fecha_fin_suscripcion='2099-12-31',
    )


@override_settings(
    WHATSAPP_PHONE_ID='111',
    WHATSAPP_PHONE_NUMBER_ID_2='',
    WHATSAPP_TOKEN='',
)
class AdminHomeDatosTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='home_admin',
            email='home@eki.test',
            password='HomeAdmin2026!',
            first_name='Ana',
        )
        self.cliente = _cliente()

    def test_vacio_no_revienta(self):
        data = construir_inicio(self.user)
        self.assertIn('Ana', data['saludo'])
        self.assertEqual(len(data['cifras']), 4)
        self.assertTrue(all(int(a['conteo']) > 0 for a in data['acciones']))
        self.assertIn('Celery', data['cifras'][3]['tooltip'])
        self.assertIn('Sin dato', data['cifras'][3]['tooltip'])

    def test_filas_cuentan_y_filtran(self):
        base = construir_inicio(self.user)
        base_acc = {a['clave']: a['conteo'] for a in base['acciones']}
        est_sin = Estudiante.objects.create(
            cedula='home1',
            nombre='Sin curso',
            telefono='573001110081',
            cliente=self.cliente,
            activo=True,
        )
        est_ok = Estudiante.objects.create(
            cedula='home2',
            nombre='Con curso',
            telefono='573001110082',
            cliente=self.cliente,
            activo=True,
        )
        curso = Curso.objects.create(nombre='Curso inicio', cliente=self.cliente, activo=True)
        publicado = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='Publicado',
            descripcion='d',
            publicado_wa=True,
        )
        Modulo.objects.create(
            curso=curso,
            numero=2,
            titulo='Borrador',
            descripcion='d',
            publicado_wa=False,
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est_ok,
            curso=curso,
            completado=False,
        )
        ProgresoEstudiante.objects.filter(pk=prog.pk).update(
            completado=True,
            fecha_completado=timezone.now(),
        )
        from core.models import ModuloCompletado

        ModuloCompletado.objects.create(progreso=prog, modulo=publicado)
        hoy = timezone.now().date()
        Certificado.objects.create(
            estudiante=est_ok,
            curso=curso,
            calificacion_final=80,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            enviado_whatsapp=False,
        )
        Certificado.objects.create(
            estudiante=est_sin,
            curso=curso,
            calificacion_final=80,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            enviado_whatsapp=True,
        )
        PlantillaMeta.objects.create(
            nombre_interno='Pendiente inicio',
            cuerpo='Hola {{1}}',
            estado='PENDING',
        )
        PlantillaMeta.objects.create(
            nombre_interno='Aprobada inicio',
            cuerpo='Hola {{1}}',
            estado='APPROVED',
        )
        viejo = timezone.now() - timedelta(minutes=10)
        ev = MetaWebhookEvento.objects.create(
            wamid='wamid-recibido',
            telefono='573001110099',
            resultado='recibido',
        )
        MetaWebhookEvento.objects.filter(pk=ev.pk).update(recibido_en=viejo)
        err = MetaWebhookEvento.objects.create(
            wamid='wamid-error',
            telefono='573009998877',
            resultado='error',
            error='timeout de graph',
        )
        WhatsappLog.objects.create(
            telefono='573001110082',
            tipo='SENT',
            canal='meta',
            estado='failed',
            error_codigo='131026',
        )

        data = construir_inicio(self.user)
        por_clave = {a['clave']: a for a in data['acciones']}

        def delta(clave):
            return por_clave[clave]['conteo'] - base_acc.get(clave, 0)

        self.assertEqual(delta('certs'), 1)
        self.assertEqual(por_clave['certs']['url'], '/admin/envio-certificados/')
        self.assertEqual(delta('sin_progreso'), 1)
        self.assertIn('eki_progreso=sin', por_clave['sin_progreso']['url'])
        self.assertEqual(delta('sin_respuesta'), 1)
        self.assertIn('resultado__exact=recibido', por_clave['sin_respuesta']['url'])
        self.assertEqual(delta('plantillas'), 1)
        self.assertIn('estado__exact=PENDING', por_clave['plantillas']['url'])
        self.assertEqual(delta('borradores'), 1)
        self.assertIn('publicado_wa__exact=0', por_clave['borradores']['url'])
        self.assertEqual(int(data['cifras'][0]['valor']) - int(base['cifras'][0]['valor']), 2)
        self.assertTrue(data['cifras'][1]['valor'].endswith('%'))
        self.assertEqual(int(data['cifras'][2]['valor']) - int(base['cifras'][2]['valor']), 1)
        self.assertEqual(int(data['cifras'][3]['valor']) - int(base['cifras'][3]['valor']), 2)
        propio = next(e for e in data['errores'] if e['sufijo'] == '8877')
        self.assertEqual(propio['linea'], 'Sin dato')
        self.assertIn('timeout', propio['que'])
        self.assertEqual(err.resultado, 'error')
        self.assertEqual(len(data['lineas']), 1)
        self.assertEqual(
            data['lineas'][0]['mensajes_hoy'] - (base['lineas'][0]['mensajes_hoy'] or 0),
            1,
        )

    def test_conteo_cero_no_entra(self):
        User = get_user_model()
        solo_plantillas = User.objects.create_user(
            username='home_plantillas',
            password='x',
            is_staff=True,
        )
        perm = Permission.objects.get(
            codename='view_plantillameta',
            content_type__app_label='core',
        )
        solo_plantillas.user_permissions.add(perm)
        data = construir_inicio(solo_plantillas)
        for fila in data['acciones']:
            self.assertGreater(fila['conteo'], 0)
        if not PlantillaMeta.objects.filter(estado='PENDING').exists():
            self.assertEqual(data['acciones'], [])

    def test_sin_permiso_oculta_la_fila(self):
        User = get_user_model()
        limitado = User.objects.create_user(
            username='home_limit',
            password='x',
            is_staff=True,
        )
        perm = Permission.objects.get(codename='view_estudiante', content_type__app_label='core')
        limitado.user_permissions.add(perm)
        Estudiante.objects.create(
            cedula='home3',
            nombre='Solo est',
            telefono='573001110083',
            cliente=self.cliente,
            activo=True,
        )
        curso = Curso.objects.create(nombre='Otro', cliente=self.cliente, activo=True)
        Modulo.objects.create(
            curso=curso, numero=1, titulo='B', descripcion='d', publicado_wa=False,
        )
        data = construir_inicio(limitado)
        claves = [a['clave'] for a in data['acciones']]
        self.assertEqual(claves, ['sin_progreso'])
        self.assertEqual(data['badges']['modulos'], 0)

    def test_cache_60s_y_actualizar(self):
        with patch('core.twilio_balance.twilio_balance_badge', return_value=('Twilio $1 este mes', 'info')):
            primero = home_para(self.user, force=True)
        Estudiante.objects.create(
            cedula='home4',
            nombre='Despues',
            telefono='573001110084',
            cliente=self.cliente,
            activo=True,
        )
        with patch('core.twilio_balance.twilio_balance_badge', return_value=('Twilio $1 este mes', 'info')):
            segundo = home_para(self.user)
        self.assertEqual(primero['cifras'][0]['valor'], segundo['cifras'][0]['valor'])
        invalidar_home(self.user)
        with patch('core.twilio_balance.twilio_balance_badge', return_value=('Twilio $1 este mes', 'info')):
            tercero = home_para(self.user)
        self.assertEqual(int(tercero['cifras'][0]['valor']), int(primero['cifras'][0]['valor']) + 1)
        self.assertEqual(tercero['twilio_mes'], '$1')

    def test_consultas_acotadas(self):
        with self.assertNumQueries(12):
            construir_inicio(self.user)


@override_settings(WHATSAPP_PHONE_ID='111', WHATSAPP_PHONE_NUMBER_ID_2='', WHATSAPP_TOKEN='tok')
class AdminHomeLineasTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_meta_falla_y_queda_sin_dato(self):
        with patch('requests.get', side_effect=TimeoutError('meta')):
            fila = estado_una_linea('111', 'Línea principal')
        self.assertEqual(fila['estado'], 'Sin dato')
        self.assertEqual(fila['calidad'], 'Sin dato')
        self.assertEqual(fila['numero'], 'Sin dato')

    def test_una_sola_linea(self):
        from core.admin.home_data import _lineas_locales

        filas = _lineas_locales(
            mensajes_hoy=3,
            sin_respuesta_24=1,
            puede_log=True,
            puede_wh=True,
        )
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['nombre'], 'Línea principal')
        self.assertEqual(filas[0]['mensajes_hoy'], 3)

    @override_settings(WHATSAPP_PHONE_ID='111', WHATSAPP_PHONE_NUMBER_ID_2='222')
    def test_dos_lineas_no_parten_el_historial(self):
        from core.admin.home_data import _lineas_locales

        filas = _lineas_locales(
            mensajes_hoy=9,
            sin_respuesta_24=4,
            puede_log=True,
            puede_wh=True,
        )
        self.assertEqual(len(filas), 2)
        self.assertIsNone(filas[0]['mensajes_hoy'])
        self.assertIsNone(filas[1]['sin_respuesta_24h'])
        self.assertTrue(filas[0]['aproximado'])


@override_settings(
    WHATSAPP_PHONE_ID='111',
    WHATSAPP_PHONE_NUMBER_ID_2='',
    WHATSAPP_TOKEN='tok',
    SECURE_SSL_REDIRECT=False,
)
class AdminHomePaginaTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='home_pagina',
            email='pagina@eki.test',
            password='HomePagina2026!',
            first_name='Ana',
        )
        self.client.force_login(self.user)

    def test_pagina_carga(self):
        r = self.client.get('/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Personas activas')
        self.assertContains(r, 'Requiere acción hoy')
        self.assertContains(r, 'Mensajes, últimos 14 días')
        self.assertContains(r, 'Línea principal')
        self.assertNotContains(r, 'Línea 2')
        self.assertNotContains(r, 'Ecosistema eki')

    def test_todo_al_dia_si_no_hay_filas(self):
        User = get_user_model()
        limitado = User.objects.create_user('home_vacio', password='x', is_staff=True)
        perm = Permission.objects.get(
            codename='view_plantillameta',
            content_type__app_label='core',
        )
        limitado.user_permissions.add(perm)
        self.client.force_login(limitado)
        if PlantillaMeta.objects.filter(estado='PENDING').exists():
            self.skipTest('hay plantillas pendientes de semilla')
        r = self.client.get('/admin/')
        self.assertContains(r, 'Todo al día.')

    def test_meta_no_rompe_la_pagina(self):
        with patch('requests.get', side_effect=TimeoutError('meta')):
            pagina = self.client.get('/admin/')
            lineas = self.client.get('/admin/inicio/lineas.json')
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(lineas.status_code, 200)
        self.assertEqual(lineas.json()['lineas'][0]['estado'], 'Sin dato')

    def test_actualizar_invalida_el_cache(self):
        with patch('core.twilio_balance.twilio_balance_badge', return_value=('Twilio $2 este mes', 'info')):
            self.client.get('/admin/')
        from core.models import Cliente

        cliente = Cliente.objects.create(
            nombre='Org actualizar',
            contacto_principal='A',
            email='act@test.com',
            telefono='573001110090',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        Estudiante.objects.create(
            cedula='homeact',
            nombre='Nueva',
            telefono='573001110091',
            cliente=cliente,
            activo=True,
        )
        with patch('core.twilio_balance.twilio_balance_badge', return_value=('Twilio $2 este mes', 'info')):
            r = self.client.post('/admin/inicio/actualizar/', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Personas activas')
        self.assertContains(r, 'Twilio demo')
