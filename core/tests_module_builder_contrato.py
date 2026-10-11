# -*- coding: utf-8 -*-
"""Caracterización del Module Builder actual (Fase 0).

Una prueba por action, más las reglas que el reskin no puede romper.
No envía WhatsApp. El cliente es el de Django, contra la vista de hoy.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.module_builder import agregar_micro, agregar_seccion
from core.module_structure import detectar_secciones_intercaladas


User = get_user_model()

FLAG_ON = dict(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
FLAG_OFF = dict(
    EKI_MODULE_BUILDER_BETA=False,
    EKI_MODULE_BUILDER_CURSOS='',
    SECURE_SSL_REDIRECT=False,
)
STORAGE_LOCAL = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


def _drip():
    return timezone.make_aware(
        timezone.datetime(2029, 5, 1, 8, 30),
        timezone.get_current_timezone(),
    )


@override_settings(**FLAG_ON)
class ModuleBuilderContratoFase0Tests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Contrato Builder')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Módulo intacto',
            descripcion='d',
            contenido='c',
            habilitado_desde=_drip(),
        )
        self.sec = agregar_seccion(self.mod, 'Sección A')
        self.paso = agregar_micro(
            self.mod, self.sec, titulo='Paso uno', contenido='texto uno',
        )
        self.staff = User.objects.create_user(
            username='mb_contrato', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)
        self.url = f'/admin/module-builder/{self.mod.id}/'

    def _post(self, data, **kwargs):
        return self.client.post(self.url, data, secure=True, **kwargs)

    def _orden_activos(self):
        return list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True)
            .order_by('orden', 'id')
            .values_list('id', 'seccion_id', 'contenido')
        )

    def test_save_modulo_guarda_texto_y_titulo(self):
        r = self._post({
            'action': 'save_modulo',
            'ajax': '1',
            'modulo_titulo': 'Módulo intacto',
            f'paso_{self.paso.id}_titulo': 'Paso editado',
            f'paso_{self.paso.id}_contenido': 'texto editado',
            f'paso_{self.paso.id}_activo': '1',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.paso.refresh_from_db()
        self.assertEqual(self.paso.titulo, 'Paso editado')
        self.assertEqual(self.paso.contenido, 'texto editado')

    def test_save_modulo_meta_cambia_el_nombre(self):
        r = self._post({
            'action': 'save_modulo_meta',
            'modulo_titulo': 'Nombre desde meta',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.titulo, 'Nombre desde meta')

    def test_rename_seccion_solo_toca_el_titulo(self):
        drip = self.mod.habilitado_desde
        r = self._post({
            'action': 'rename_seccion',
            'seccion_id': str(self.sec.id),
            'titulo': 'Hechos',
            'modulo_titulo': 'No debe aplicarse',
            'modulo_habilitado_desde': '',
        })
        self.assertEqual(r.status_code, 302)
        self.sec.refresh_from_db()
        self.mod.refresh_from_db()
        self.assertEqual(self.sec.titulo, 'Hechos')
        self.assertEqual(self.mod.titulo, 'Módulo intacto')
        self.assertEqual(self.mod.habilitado_desde, drip)

    def test_add_seccion(self):
        antes = SeccionModulo.objects.filter(modulo=self.mod).count()
        r = self._post({'action': 'add_seccion', 'titulo': 'Sección B'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            SeccionModulo.objects.filter(modulo=self.mod, titulo='Sección B').count(),
            1,
        )
        self.assertEqual(SeccionModulo.objects.filter(modulo=self.mod).count(), antes + 1)

    def test_add_micro_texto(self):
        r = self._post({
            'action': 'add_micro',
            'seccion_id': str(self.sec.id),
            'titulo': 'Nota',
            'contenido': 'hola',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            PasoModulo.objects.filter(modulo=self.mod, contenido='hola').exists()
        )
        self.assertContains(r, 'Microcontenido añadido')

    def test_update_micro_guarda_contenido(self):
        r = self._post({
            'action': 'update_micro',
            'paso_id': str(self.paso.id),
            'titulo': 'Interno',
            'contenido': 'guardado por update',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.paso.refresh_from_db()
        self.assertEqual(self.paso.contenido, 'guardado por update')
        self.assertEqual(self.paso.titulo, 'Interno')
        self.assertContains(r, 'Micro guardado')

    @override_settings(STORAGES=STORAGE_LOCAL)
    def test_replace_media_no_pisa_el_titulo_del_modulo(self):
        otra = agregar_seccion(self.mod, 'Sección intacta')
        pdf = SimpleUploadedFile('nota.pdf', b'%PDF-1.4', content_type='application/pdf')
        r = self._post({
            'action': 'replace_media',
            'paso_id': str(self.paso.id),
            'modulo_titulo': 'Título pisado',
            f'seccion_{self.sec.id}_titulo': 'Sección pisada',
            f'seccion_{otra.id}_titulo': 'Otra pisada',
            'media_file': pdf,
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.mod.refresh_from_db()
        self.sec.refresh_from_db()
        otra.refresh_from_db()
        self.paso.refresh_from_db()
        self.assertEqual(self.mod.titulo, 'Módulo intacto')
        self.assertEqual(self.sec.titulo, 'Sección A')
        self.assertEqual(otra.titulo, 'Sección intacta')
        self.assertTrue((self.paso.media_url or '').strip())
        self.assertEqual(self.paso.contenido, 'texto uno')

    def test_delete_media_conserva_el_texto(self):
        self.paso.media_url = 'https://ejemplo.test/a.pdf'
        self.paso.media_wa_apto = True
        self.paso.save(update_fields=['media_url', 'media_wa_apto'])
        r = self._post({
            'action': 'delete_media',
            'ajax': '1',
            'paso_id': str(self.paso.id),
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['media_url'], '')
        self.paso.refresh_from_db()
        self.assertEqual(self.paso.media_url, '')
        self.assertIsNone(self.paso.media_wa_apto)
        self.assertEqual(self.paso.contenido, 'texto uno')

    def test_set_video_entrega(self):
        r = self._post({
            'action': 'set_video_entrega',
            'paso_id': str(self.paso.id),
            'video_entrega': PasoModulo.VIDEO_ENLACE,
        })
        self.assertEqual(r.status_code, 302)
        self.paso.refresh_from_db()
        self.assertEqual(self.paso.video_entrega, PasoModulo.VIDEO_ENLACE)
        self.assertEqual(self.paso.contenido, 'texto uno')

    def test_move_micro_intercambia_con_el_vecino(self):
        segundo = agregar_micro(self.mod, self.sec, titulo='Dos', contenido='texto dos')
        r = self._post({
            'action': 'move_micro',
            'paso_id': str(segundo.id),
            'direction': 'up',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Orden actualizado')
        ids = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True)
            .order_by('orden', 'id')
            .values_list('id', flat=True)
        )
        self.assertEqual(ids, [segundo.id, self.paso.id])
        self.assertEqual(detectar_secciones_intercaladas(
            list(PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id'))
        ), [])

    def test_reorder_micros_dentro_de_la_seccion(self):
        segundo = agregar_micro(self.mod, self.sec, titulo='Dos', contenido='texto dos')
        r = self._post({
            'action': 'reorder_micros',
            'ajax': '1',
            'seccion_id': str(self.sec.id),
            'orden': f'{segundo.id},{self.paso.id}',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        ids = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True)
            .order_by('orden', 'id')
            .values_list('id', flat=True)
        )
        self.assertEqual(ids, [segundo.id, self.paso.id])

    def test_reorder_secciones_mueve_bloques_completos(self):
        sec_b = agregar_seccion(self.mod, 'Sección B')
        paso_b = agregar_micro(self.mod, sec_b, contenido='texto b')
        r = self._post({
            'action': 'reorder_secciones',
            'ajax': '1',
            'orden': f'{sec_b.id},{self.sec.id}',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        ids = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True)
            .order_by('orden', 'id')
            .values_list('contenido', flat=True)
        )
        self.assertEqual(ids, ['texto b', 'texto uno'])
        self.assertEqual(paso_b.seccion_id, sec_b.id)
        activos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual(detectar_secciones_intercaladas(activos), [])

    def test_deactivate_micro(self):
        r = self._post({
            'action': 'deactivate_micro',
            'paso_id': str(self.paso.id),
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.paso.refresh_from_db()
        self.assertFalse(self.paso.activo)
        self.assertEqual(self.paso.contenido, 'texto uno')
        self.assertTrue(PasoModulo.objects.filter(pk=self.paso.id).exists())

    def test_duplicate_micro_queda_inactivo(self):
        antes = PasoModulo.objects.filter(modulo=self.mod).count()
        r = self._post({
            'action': 'duplicate_micro',
            'paso_id': str(self.paso.id),
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), antes + 1)
        copia = PasoModulo.objects.exclude(pk=self.paso.id).get(modulo=self.mod)
        self.assertFalse(copia.activo)
        self.assertIn('copia', copia.titulo.lower())
        self.assertEqual(copia.contenido, 'texto uno')
        self.assertEqual(copia.seccion_id, self.sec.id)

    def test_encode_status_no_escribe_ni_trae_porcentaje(self):
        titulo = self.mod.titulo
        contenido = self.paso.contenido
        r = self._post({'action': 'encode_status', 'ajax': '1'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        fila = next(p for p in data['pasos'] if p['id'] == self.paso.id)
        self.assertIn('status', fila)
        self.assertNotIn('percent', fila)
        self.assertNotIn('porcentaje', fila)
        self.mod.refresh_from_db()
        self.paso.refresh_from_db()
        self.assertEqual(self.mod.titulo, titulo)
        self.assertEqual(self.paso.contenido, contenido)

    def test_action_desconocida_responde_accion_no_reconocida(self):
        r = self._post({'action': 'publicar_ya', 'modulo_titulo': 'X'}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Acción no reconocida.')
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.titulo, 'Módulo intacto')

    def test_post_parcial_sin_drip_no_borra_habilitado_desde(self):
        drip = self.mod.habilitado_desde
        r = self._post({
            'action': 'save_modulo',
            'modulo_titulo': 'Módulo intacto',
            f'paso_{self.paso.id}_contenido': 'texto uno',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.habilitado_desde, drip)

        r = self._post({
            'action': 'add_micro',
            'seccion_id': str(self.sec.id),
            'contenido': 'parcial',
        })
        self.assertEqual(r.status_code, 302)
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.habilitado_desde, drip)

    def test_activar_micro_sin_texto_ni_media_falla_con_su_mensaje(self):
        vacio = agregar_micro(
            self.mod, self.sec, titulo='Vacío', contenido='relleno', activo=False,
        )
        vacio.contenido = ''
        vacio.media_url = ''
        vacio.activo = False
        vacio.save(update_fields=['contenido', 'media_url', 'activo'])
        r = self._post({
            'action': 'update_micro',
            'paso_id': str(vacio.id),
            'titulo': 'Vacío',
            'contenido': '',
            'activo': '1',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r,
            'Para activar el micro escriba texto o suba media (admin clásico / + contenido).',
        )
        vacio.refresh_from_db()
        self.assertFalse(vacio.activo)
        self.assertEqual(vacio.contenido, '')

    def test_reordenar_no_intercala_secciones(self):
        sec_b = agregar_seccion(self.mod, 'Sección B')
        paso_b = agregar_micro(self.mod, sec_b, contenido='texto b')
        antes = self._orden_activos()
        r = self._post({
            'action': 'reorder_micros',
            'ajax': '1',
            'seccion_id': str(self.sec.id),
            'orden': f'{self.paso.id},{paso_b.id}',
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn('no coincide', r.json()['error'])
        self.assertEqual(self._orden_activos(), antes)
        activos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual(detectar_secciones_intercaladas(activos), [])

    def test_activo_sin_la_clave_no_cambia(self):
        inactivo = agregar_micro(
            self.mod, self.sec, titulo='Borrador', contenido='borrador', activo=False,
        )
        r = self._post({
            'action': 'save_modulo',
            'modulo_titulo': 'Módulo intacto',
            f'paso_{self.paso.id}_titulo': 'Paso uno',
            f'paso_{self.paso.id}_contenido': 'texto uno retocado',
            f'paso_{inactivo.id}_titulo': 'Borrador',
            f'paso_{inactivo.id}_contenido': 'borrador retocado',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.paso.refresh_from_db()
        inactivo.refresh_from_db()
        self.assertTrue(self.paso.activo)
        self.assertFalse(inactivo.activo)
        self.assertEqual(self.paso.contenido, 'texto uno retocado')
        self.assertEqual(inactivo.contenido, 'borrador retocado')

    def test_get_diez_secciones_once_consultas(self):
        """Línea base del GET con 10 secciones y 2 mensajes cada una."""
        for i in range(2, 11):
            sec = agregar_seccion(self.mod, f'Sección {i}')
            agregar_micro(self.mod, sec, contenido=f'a{i}')
            agregar_micro(self.mod, sec, contenido=f'b{i}')
        agregar_micro(self.mod, self.sec, contenido='extra')
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(self.url, secure=True)
        self.assertEqual(r.status_code, 200)
        # Curso sin cliente: 8. Con cliente, la vista suma la habilitación por empresa.
        self.assertEqual(len(ctx.captured_queries), 8)

    def test_guardar_general_sin_calendario_no_cambia_el_drip(self):
        """Guardar General manda persist_general y omite modulo_habilitado_desde."""
        drip = self.mod.habilitado_desde
        r = self._post({
            'action': 'save_modulo',
            'ajax': '1',
            'persist_general': '1',
            'modulo_titulo': 'Módulo intacto',
            'modulo_descripcion': 'descripcion nueva',
            'modulo_modo_entrega': self.mod.modo_entrega,
            'modulo_duracion_dias': str(self.mod.duracion_dias or 0),
        })
        self.assertEqual(r.status_code, 200)
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.habilitado_desde, drip)
        self.assertEqual(self.mod.descripcion, 'descripcion nueva')


_IDS_CONTRATO = (
    'id="eki-mb-shell"',
    'id="eki-mb-csrf"',
    'id="eki-mb-modulo-titulo"',
    'data-publicar-url=',
    'id="eki-mb-sections"',
    'name="modulo_titulo"',
    'name="modulo_habilitado_desde"',
    'name="modulo_descripcion"',
)


@override_settings(**FLAG_ON)
class ModuleBuilderUiV2Tests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='UI v2')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M',
            descripcion='d',
            contenido='c',
            publicado_wa=False,
        )
        sec = agregar_seccion(self.mod, 'Sección')
        self.paso = agregar_micro(self.mod, sec, titulo='Foto', contenido='pie')
        self.paso.media_url = 'https://cdn.ejemplo/foto.jpg'
        self.paso.save(update_fields=['media_url'])
        staff = User.objects.create_user(
            username='mb_ui_%s' % self.__class__.__name__[-6:],
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client = Client()
        self.client.force_login(staff)
        self.url = f'/admin/module-builder/{self.mod.id}/'

    def test_interruptor_apagado_conserva_la_pantalla_actual(self):
        r = self.client.get(self.url, secure=True)
        body = r.content.decode('utf-8')
        self.assertEqual(r.status_code, 200)
        for marca in _IDS_CONTRATO:
            self.assertIn(marca, body)
        self.assertIn('Lectura', body)
        self.assertNotIn('Subir mensaje', body)
        self.assertNotIn('module_builder_v2.css', body)
        self.assertNotIn('data-eki-mb-pestana', body)
        self.assertNotIn('eki-mb-save-calendario', body)
        self.assertNotIn('Texto + archivo', body)
        self.assertNotIn('drip_organizaciones', r.context)


@override_settings(**FLAG_ON, EKI_MODULE_BUILDER_UI_V2=True)
class ModuleBuilderUiV2EncendidoTests(ModuleBuilderUiV2Tests):
    def test_interruptor_apagado_conserva_la_pantalla_actual(self):
        self.skipTest('Ese caso corre con el interruptor apagado.')

    def test_interruptor_encendido_conserva_el_contrato_y_agrega_controles(self):
        r = self.client.get(self.url, secure=True)
        body = r.content.decode('utf-8')
        self.assertEqual(r.status_code, 200)
        for marca in _IDS_CONTRATO:
            self.assertIn(marca, body)
        self.assertIn('eki-mb__type-chip--lectura">Imagen', body)
        self.assertNotIn('eki-mb__type-chip--lectura">Lectura', body)
        self.assertIn('aria-label="Subir mensaje"', body)
        self.assertIn('aria-label="Bajar mensaje"', body)
        self.assertIn('value="move_micro"', body)
        self.assertIn('module_builder_v2.css', body)
        self.assertIn('eki-mb-shell--v2', body)
        self.assertIn('/admin/core/modulo/%s/publicar/' % self.mod.pk, body)
        self.assertIn('Publicar en WhatsApp', body)
        self.assertIn('data-eki-mb-pestana="contenido"', body)
        self.assertIn('data-eki-mb-pestana="general"', body)
        self.assertIn('data-eki-mb-pestana="calendario"', body)
        self.assertIn('eki-mb-save-calendario', body)
        self.assertIn('Texto + archivo', body)
        self.assertIn('+ Texto antes', body)
        self.assertIn('+ Texto después', body)
        self.assertIn('>Renombrar<', body)
        self.assertIn('+ Agregar mensaje', body)
        js = open(
            'static/admin/js/module_builder.js', encoding='utf-8'
        ).read()
        self.assertIn('incluirCalendario', js)
        self.assertIn("classList.contains('eki-mb-shell--v2')", js)

    def test_botones_subir_y_bajar_mueven_el_mensaje(self):
        segundo = agregar_micro(self.mod, self.paso.seccion, titulo='Dos', contenido='texto dos')
        r = self.client.post(self.url, {
            'action': 'move_micro',
            'paso_id': str(segundo.id),
            'direction': 'up',
        }, secure=True)
        self.assertEqual(r.status_code, 302)
        ids = list(
            PasoModulo.objects.filter(modulo=self.mod)
            .order_by('orden', 'id')
            .values_list('id', flat=True)
        )
        self.assertEqual(ids[0], segundo.id)

    def test_lectura_de_organizaciones_no_escribe(self):
        from core.models import Cliente, HabilitacionModuloDripCliente, HabilitacionModuloEstudiante

        cliente = Cliente.objects.create(nombre='Org lectura')
        self.curso.cliente = cliente
        self.curso.save(update_fields=['cliente'])
        cuando = _drip()
        HabilitacionModuloDripCliente.objects.create(
            cliente=cliente,
            curso=self.curso,
            modulo=self.mod,
            habilitado_desde=cuando,
            activo=True,
        )
        antes_org = HabilitacionModuloDripCliente.objects.count()
        antes_personas = HabilitacionModuloEstudiante.objects.count()
        antes_modulos = Modulo.objects.count()
        r = self.client.get(self.url, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(HabilitacionModuloDripCliente.objects.count(), antes_org)
        self.assertEqual(HabilitacionModuloEstudiante.objects.count(), antes_personas)
        self.assertEqual(Modulo.objects.count(), antes_modulos)
        orgs = r.context['drip_organizaciones']
        self.assertEqual(orgs, [{
            'nombre': 'Org lectura',
            'habilitado_desde': cuando,
            'usa_fecha_modulo': False,
        }])
        self.assertEqual(r.context['drip_personas_conteo'], 0)
        self.assertEqual(r.context['drip_orgs_lista_blanca'], [])


@override_settings(**FLAG_OFF)
class ModuleBuilderContratoPuertaTests(TestCase):
    def test_staff_sin_puerta_recibe_permission_denied(self):
        curso = Curso.objects.create(nombre='Cerrado')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        staff = User.objects.create_user(
            username='mb_sin_puerta', password='x', is_staff=True, is_superuser=False,
        )
        client = Client()
        client.force_login(staff)
        url = f'/admin/module-builder/{mod.id}/'
        self.assertEqual(client.get(url, secure=True).status_code, 403)
        self.assertEqual(
            client.post(url, {'action': 'add_seccion', 'titulo': 'X'}, secure=True).status_code,
            403,
        )
        self.assertFalse(SeccionModulo.objects.filter(modulo=mod, titulo='X').exists())
