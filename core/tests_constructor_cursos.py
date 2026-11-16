"""Bloque 5 — constructor oficial. Slice 5.1: texto. Flag off: sin escrituras."""
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from core.cursos.constructor.contrato import (
    BUILDER_LEGADO_SIN_FEATURES_NUEVAS,
    CONTINUEMOS_ENTREGA_UN_BLOQUE,
    CURSO_MODULO_BLOQUE_MENSAJE,
    GUARDAR_NO_PUBLICA,
)
from core.cursos.constructor.servicio import (
    actualizar_mensaje_texto,
    adjuntar_media_mensaje,
    constructor_activo,
    crear_bloque,
    crear_mensaje_evaluacion,
    crear_mensaje_texto,
    crear_modulo,
    estructura_curso,
    mover_bloque,
    mover_mensaje,
    mover_modulo,
    preview_ensamblado,
    publicar_desde_constructor,
)


class ContratoConstructorTests(SimpleTestCase):
    def test_contrato_fija_reglas_del_bloque_5(self):
        self.assertTrue(CURSO_MODULO_BLOQUE_MENSAJE)
        self.assertTrue(GUARDAR_NO_PUBLICA)
        self.assertTrue(CONTINUEMOS_ENTREGA_UN_BLOQUE)
        self.assertTrue(BUILDER_LEGADO_SIN_FEATURES_NUEVAS)

    def test_flag_default_apagado(self):
        self.assertFalse(settings.EKI_CONSTRUCTOR_CURSOS)
        self.assertFalse(constructor_activo())


class ConstructorTextoTests(TestCase):
    def test_flag_off_crear_modulo_no_escribe(self):
        from core.models import Curso, Modulo

        curso = Curso.objects.create(nombre='Ctor off', descripcion='x')
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            self.assertIsNone(crear_modulo(curso, titulo='M1'))
        self.assertEqual(Modulo.objects.filter(curso=curso).count(), 0)

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_crear_modulo_bloque_y_mensaje_texto(self):
        from core.models import Curso, Modulo, PasoModulo, SeccionModulo

        curso = Curso.objects.create(nombre='Ctor on', descripcion='d')
        mod = crear_modulo(curso, titulo='Introducción', descripcion='idea')
        self.assertIsNotNone(mod)
        self.assertEqual(mod.numero, 1)
        self.assertEqual(mod.titulo, 'Introducción')
        self.assertEqual(mod.modo_entrega, Modulo.MODO_ENTREGA_PASOS)
        self.assertEqual(SeccionModulo.objects.filter(modulo=mod).count(), 1)

        bloque = SeccionModulo.objects.get(modulo=mod)
        self.assertEqual(bloque.titulo, 'Bloque 1')

        segundo = crear_bloque(mod, titulo='Cierre')
        self.assertEqual(segundo.orden, 2)
        self.assertEqual(segundo.titulo, 'Cierre')

        msg = crear_mensaje_texto(
            bloque, contenido='Hola por WhatsApp', titulo='Saludo', activo=True,
        )
        self.assertEqual(msg.tipo, PasoModulo.TIPO_CONTENIDO)
        self.assertEqual(msg.contenido, 'Hola por WhatsApp')
        self.assertTrue(msg.activo)
        self.assertEqual(msg.seccion_id, bloque.id)
        self.assertFalse(msg.media_url)

        actualizar_mensaje_texto(msg, contenido='Texto editado', activo=False)
        msg.refresh_from_db()
        self.assertEqual(msg.contenido, 'Texto editado')
        self.assertFalse(msg.activo)

        arbol = estructura_curso(curso)
        self.assertEqual(arbol['curso_id'], curso.id)
        self.assertEqual(len(arbol['modulos']), 1)
        self.assertEqual(len(arbol['modulos'][0]['bloques']), 2)
        self.assertEqual(arbol['modulos'][0]['bloques'][0]['mensajes'][0]['contenido'], 'Texto editado')

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_guardar_mensaje_no_publica_modulo(self):
        from core.models import Curso

        curso = Curso.objects.create(nombre='Ctor no pub', descripcion='d')
        mod = crear_modulo(curso, titulo='M1')
        bloque = mod.secciones.get()
        crear_mensaje_texto(bloque, contenido='solo borrador', activo=True)
        mod.refresh_from_db()
        self.assertFalse(mod.publicado_wa)

    def test_estructura_se_lee_con_flag_off(self):
        from core.models import Curso, Modulo, PasoModulo, SeccionModulo

        curso = Curso.objects.create(nombre='Ctor lectura', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='', contenido='',
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='B1')
        PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1,
            tipo=PasoModulo.TIPO_CONTENIDO, contenido='vivo', activo=True,
        )
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            arbol = estructura_curso(curso)
        self.assertEqual(arbol['modulos'][0]['bloques'][0]['mensajes'][0]['contenido'], 'vivo')


class ConstructorOrdenPreviewTests(TestCase):
    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_mover_y_preview_usan_ensamblador(self):
        from core.cursos.autoria.ensamblado import congelar_ensamblado
        from core.models import Curso

        curso = Curso.objects.create(nombre='Ctor orden', descripcion='d')
        m1 = crear_modulo(curso, titulo='Primero')
        m2 = crear_modulo(curso, titulo='Segundo')
        self.assertTrue(mover_modulo(m2, 'up'))
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertEqual(m2.numero, 1)
        self.assertEqual(m1.numero, 2)

        b1 = m2.secciones.get()
        b2 = crear_bloque(m2, titulo='Extra')
        self.assertTrue(mover_bloque(b2, 'up'))
        b1.refresh_from_db()
        b2.refresh_from_db()
        self.assertEqual(b2.orden, 1)
        self.assertEqual(b1.orden, 2)

        msg1 = crear_mensaje_texto(b2, contenido='uno')
        msg2 = crear_mensaje_texto(b2, contenido='dos')
        self.assertTrue(mover_mensaje(msg2, 'up'))
        msg1.refresh_from_db()
        msg2.refresh_from_db()
        self.assertEqual(msg2.orden, 1)
        self.assertEqual(msg1.orden, 2)

        snap = preview_ensamblado(curso)
        self.assertEqual(snap, congelar_ensamblado(curso))
        self.assertEqual(snap['modulos'][0]['titulo'], 'Segundo')

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_mover_mensaje_no_cruza_bloque(self):
        from core.models import Curso

        curso = Curso.objects.create(nombre='Ctor no cruza', descripcion='d')
        mod = crear_modulo(curso, titulo='M')
        b1 = mod.secciones.get()
        b2 = crear_bloque(mod, titulo='Dos')
        primero = crear_mensaje_texto(b1, contenido='bloque uno')
        segundo = crear_mensaje_texto(b2, contenido='bloque dos')
        self.assertFalse(mover_mensaje(segundo, 'up'))
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.orden, 1)
        self.assertEqual(segundo.orden, 2)
        self.assertEqual(primero.seccion_id, b1.id)
        self.assertEqual(segundo.seccion_id, b2.id)

    def test_mover_flag_off_no_cambia(self):
        from core.models import Curso, Modulo, SeccionModulo

        curso = Curso.objects.create(nombre='Ctor orden off', descripcion='d')
        a = Modulo.objects.create(
            curso=curso, numero=1, titulo='A', descripcion='', contenido='',
        )
        b = Modulo.objects.create(
            curso=curso, numero=2, titulo='B', descripcion='', contenido='',
        )
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            self.assertFalse(mover_modulo(b, 'up'))
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.numero, 1)
        self.assertEqual(b.numero, 2)
        sec = SeccionModulo.objects.create(modulo=a, orden=1, titulo='S')
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            self.assertFalse(mover_bloque(sec, 'down'))


class ConstructorPublicarTests(TestCase):
    @override_settings(EKI_CONSTRUCTOR_CURSOS=True, EKI_CURSO_VERSIONES=True)
    def test_publicar_desde_constructor_congela_sin_mover(self):
        from core.models import Curso, CursoVersion, Estudiante, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Ctor pub', descripcion='d')
        mod = crear_modulo(curso, titulo='M1')
        crear_mensaje_texto(mod.secciones.get(), contenido='hola', activo=True)
        est = Estudiante.objects.create(
            nombre='QA Ctor', telefono='573009990055', cedula='CC990055', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)

        v = publicar_desde_constructor(curso, nota='desde ctor')
        self.assertIsNotNone(v)
        self.assertEqual(v.numero, 1)
        self.assertEqual(v.nota, 'desde ctor')
        self.assertTrue(v.ensamblado.get('modulos'))
        curso.refresh_from_db()
        self.assertEqual(curso.version_publicada_id, v.id)
        prog.refresh_from_db()
        self.assertIsNone(prog.curso_version_id)
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 1)

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True, EKI_CURSO_VERSIONES=False)
    def test_publicar_sin_flag_versiones_no_escribe(self):
        from core.models import Curso, CursoVersion

        curso = Curso.objects.create(nombre='Ctor pub off', descripcion='d')
        crear_modulo(curso, titulo='M1')
        self.assertIsNone(publicar_desde_constructor(curso, nota='x'))
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)

    def test_publicar_sin_flag_constructor_no_escribe(self):
        from core.models import Curso, CursoVersion

        curso = Curso.objects.create(nombre='Ctor flag off pub', descripcion='d')
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False, EKI_CURSO_VERSIONES=True):
            self.assertIsNone(publicar_desde_constructor(curso, nota='x'))
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)


class ConstructorMediaEvalTests(TestCase):
    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_adjuntar_media_https_y_eval_ad(self):
        from core.models import Curso, PasoModulo

        curso = Curso.objects.create(nombre='Ctor media', descripcion='d')
        mod = crear_modulo(curso, titulo='M1')
        bloque = mod.secciones.get()
        msg = crear_mensaje_texto(bloque, contenido='con imagen')
        adjuntar_media_mensaje(msg, media_url='https://eki-produccion.s3.amazonaws.com/x.jpg')
        msg.refresh_from_db()
        self.assertTrue(msg.media_url.startswith('https://'))

        with self.assertRaises(ValueError):
            adjuntar_media_mensaje(msg, media_url='http://inseguro.example/x.jpg')

        ev = crear_mensaje_evaluacion(
            bloque,
            pregunta='¿Cuántas semillas?',
            opcion_a='1',
            opcion_b='2',
            opcion_c='3',
            opcion_d='4',
            correcta='B',
            activo=True,
        )
        self.assertEqual(ev.tipo, PasoModulo.TIPO_EVAL_OPC)
        self.assertEqual(ev.respuesta_correcta, 'B')
        self.assertEqual(ev.eval_opcion_b, '2')
        mod.refresh_from_db()
        self.assertFalse(mod.publicado_wa)

        with self.assertRaises(ValueError):
            crear_mensaje_evaluacion(
                bloque,
                pregunta='¿C vacía?',
                opcion_a='a',
                opcion_b='b',
                correcta='C',
            )

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True, EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629'], WHATSAPP_PHONE_ID='phone-1')
    def test_editar_subir_drip_calendario_y_prueba_interna(self):
        from datetime import datetime
        from unittest.mock import patch

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone

        from core.cursos.constructor.servicio import (
            actualizar_calendario_modulo,
            actualizar_drip,
            editar_mensaje,
            probar_mensaje_interno,
            resumen_certificado,
            subir_archivo_mensaje,
        )
        from core.models import Curso

        curso = Curso.objects.create(nombre='Ctor prod', descripcion='d')
        mod = crear_modulo(curso, titulo='M1')
        msg = crear_mensaje_texto(mod.secciones.get(), contenido='original', activo=False)
        editar_mensaje(msg, contenido='editado', titulo='T', activo=True)
        msg.refresh_from_db()
        self.assertEqual(msg.contenido, 'editado')
        self.assertTrue(msg.activo)

        archivo = SimpleUploadedFile('nota.txt', b'hola', content_type='text/plain')
        with patch(
            'core.admin._common.guardar_upload_admin_media_resultado',
            return_value={'url': 'https://eki.example/nota.txt', 'media_wa_apto': True},
        ):
            subir_archivo_mensaje(msg, archivo)
        msg.refresh_from_db()
        self.assertEqual(msg.media_url, 'https://eki.example/nota.txt')
        self.assertTrue(msg.media_wa_apto)

        actualizar_drip(curso, 3)
        curso.refresh_from_db()
        self.assertEqual(curso.dias_espera_entre_modulos, 3)
        cuando = timezone.make_aware(datetime(2026, 12, 1, 8, 0))
        actualizar_calendario_modulo(mod, habilitado_desde=cuando, duracion_dias=10)
        mod.refresh_from_db()
        self.assertEqual(mod.duracion_dias, 10)
        self.assertIsNotNone(mod.habilitado_desde)
        self.assertFalse(resumen_certificado(curso)['listo'])

        with self.assertRaises(ValueError):
            probar_mensaje_interno(msg, '573009990000')
        with patch('core.lineas.sender.sender_de_linea') as fabrica:
            fabrica.return_value.texto.return_value = {'success': True}
            ok = probar_mensaje_interno(msg, '573026480629')
        self.assertTrue(ok.get('success', True))
        fabrica.return_value.texto.assert_called_once()
        self.assertEqual(fabrica.return_value.texto.call_args.args[0], '573026480629')

    def test_media_eval_flag_off(self):
        from core.models import Curso, Modulo, PasoModulo, SeccionModulo

        curso = Curso.objects.create(nombre='Ctor media off', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='', contenido='',
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='B')
        paso = PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1,
            tipo=PasoModulo.TIPO_CONTENIDO, contenido='x',
        )
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            self.assertIsNone(
                adjuntar_media_mensaje(paso, media_url='https://example.com/a.jpg')
            )
            self.assertIsNone(
                crear_mensaje_evaluacion(
                    sec, pregunta='¿?', opcion_a='a', opcion_b='b', correcta='A',
                )
            )


class ConstructorAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='qa_ctor',
            email='qa_ctor@example.com',
            password='test-pass-ctor',
        )
        self.client.force_login(self.user)

    def test_admin_flag_off_redirige_sin_escribir(self):
        from django.urls import reverse

        from core.models import Curso, Modulo

        curso = Curso.objects.create(nombre='Admin ctor off', descripcion='d')
        url = reverse('admin:core_curso_constructor', args=[curso.pk])
        with override_settings(EKI_CONSTRUCTOR_CURSOS=False):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Modulo.objects.filter(curso=curso).count(), 0)

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True)
    def test_admin_crea_modulo_y_mensaje_texto(self):
        from django.urls import reverse

        from core.models import Curso, Modulo, PasoModulo

        curso = Curso.objects.create(nombre='Admin ctor on', descripcion='d')
        url = reverse('admin:core_curso_constructor', args=[curso.pk])
        get = self.client.get(url)
        self.assertEqual(get.status_code, 200)
        self.assertContains(get, 'Constructor')

        post_mod = self.client.post(url, {
            'accion': 'crear_modulo',
            'titulo': 'Desde admin',
            'descripcion': '',
        })
        self.assertEqual(post_mod.status_code, 200)
        mod = Modulo.objects.get(curso=curso)
        self.assertEqual(mod.titulo, 'Desde admin')
        self.assertFalse(mod.publicado_wa)
        bloque = mod.secciones.get()

        post_msg = self.client.post(url, {
            'accion': 'crear_mensaje',
            'bloque_id': str(bloque.pk),
            'contenido': 'Mensaje WA de prueba',
            'titulo': 'M1',
            'activo': '1',
        })
        self.assertEqual(post_msg.status_code, 200)
        paso = PasoModulo.objects.get(modulo=mod)
        self.assertEqual(paso.contenido, 'Mensaje WA de prueba')
        self.assertTrue(paso.activo)
        mod.refresh_from_db()
        self.assertFalse(mod.publicado_wa)

    @override_settings(EKI_CONSTRUCTOR_CURSOS=True, EKI_CURSO_VERSIONES=True)
    def test_admin_publicar_pide_confirmacion(self):
        from django.urls import reverse

        from core.models import Curso, CursoVersion

        curso = Curso.objects.create(nombre='Admin confirm', descripcion='d')
        url = reverse('admin:core_curso_constructor', args=[curso.pk])
        self.client.post(url, {'accion': 'crear_modulo', 'titulo': 'M', 'descripcion': ''})
        primero = self.client.post(url, {'accion': 'publicar_version', 'nota': 'piloto'})
        self.assertEqual(primero.status_code, 200)
        self.assertContains(primero, 'Sí, publicar versión')
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)

        hecho = self.client.post(url, {
            'accion': 'publicar_version',
            'post': 'yes',
            'nota': 'piloto',
        })
        self.assertEqual(hecho.status_code, 200)
        v = CursoVersion.objects.get(curso=curso)
        self.assertEqual(v.nota, 'piloto')
        self.assertContains(hecho, 'v1')
