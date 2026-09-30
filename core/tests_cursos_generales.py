"""Cursos sin cliente y carrusel de Formación."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.cursos_generales import (
    NOMBRE_INNOVACION,
    NOMBRE_RIENDAS,
    NOMBRE_TIEMPO,
    URL_TIEMPO,
    asegurar_cursos_generales,
)
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    PasoModulo,
    ProgresoEstudiante,
    SandboxCanalSesion,
    SeccionModulo,
)
from core.models_extras import ArchivoModulo
from core.sandbox_menu import MODO_CURSOS, dispatch_sandbox_menu, resolver_ruta_sandbox


def _org(nombre, nit, tel):
    return Cliente.objects.create(
        nombre=nombre,
        nit=nit,
        activo=True,
        contacto_principal='x',
        email=f'{nit}@eki.co',
        telefono=tel,
    )


def _curso_origen(cliente, nombre, media):
    curso = Curso.objects.create(
        nombre=nombre,
        descripcion='origen',
        cliente=cliente,
        activo=True,
        usar_agentes_ia=False,
    )
    modulo = Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo='Semana',
        descripcion='d',
        contenido='Anote la plata.',
        publicado_wa=True,
    )
    seccion = SeccionModulo.objects.create(modulo=modulo, orden=1, titulo='A')
    PasoModulo.objects.create(
        modulo=modulo,
        seccion=seccion,
        orden=1,
        titulo='Video',
        contenido='Mira',
        media_url=media,
        video_entrega=PasoModulo.VIDEO_WHATSAPP,
    )
    ArchivoModulo.objects.bulk_create([
        ArchivoModulo(
            modulo=modulo,
            tipo='video',
            titulo='Clip',
            descripcion='',
            url_externa=media,
            orden=1,
            activo=True,
        )
    ])
    return curso


@override_settings(SECURE_SSL_REDIRECT=False)
class CursosGeneralesTests(TestCase):
    def test_copia_sin_soltar_el_origen_y_crea_tiempo(self):
        org = _org('Finca', '900111', '573001000001')
        origen_r = _curso_origen(org, NOMBRE_RIENDAS, 'https://cdn.example.com/riendas.mp4')
        origen_i = _curso_origen(org, NOMBRE_INNOVACION, 'https://cdn.example.com/ia.mp4')
        primero = asegurar_cursos_generales()
        self.assertTrue(primero['riendas']['ok'])
        self.assertTrue(primero['innovacion']['ok'])
        self.assertTrue(primero['tiempo']['ok'])
        self.assertEqual(primero['riendas']['origen_id'], origen_r.id)
        origen_r.refresh_from_db()
        self.assertEqual(origen_r.cliente_id, org.id)
        copia = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        self.assertIsNone(copia.cliente_id)
        self.assertNotEqual(copia.id, origen_r.id)
        paso = PasoModulo.objects.get(modulo__curso=copia)
        self.assertEqual(paso.media_url, 'https://cdn.example.com/riendas.mp4')
        self.assertEqual(ArchivoModulo.objects.filter(modulo__curso=copia).count(), 1)
        tiempo = Curso.objects.get(nombre=NOMBRE_TIEMPO, catalogo_menu=True)
        self.assertIsNone(tiempo.cliente_id)
        self.assertEqual(tiempo.modulos.count(), 5)
        self.assertEqual(
            list(tiempo.modulos.order_by('numero').values_list('titulo', flat=True)),
            [
                'Bienvenida e importancia del tiempo',
                'Herramientas y técnicas',
                'Productividad y ladrones de tiempo',
                'Organización del espacio',
                'Hábitos y disciplina',
            ],
        )
        segundo = asegurar_cursos_generales()
        self.assertTrue(segundo['riendas']['ya_tenia_modulos'])
        self.assertEqual(Curso.objects.filter(nombre=NOMBRE_INNOVACION, catalogo_menu=True).count(), 1)
        self.assertEqual(tiempo.modulos.count(), 5)
        self.assertEqual(origen_i.modulos.count(), 1)

    def test_sin_origen_no_inventa_modulos(self):
        fila = asegurar_cursos_generales()['riendas']
        self.assertFalse(fila['ok'])
        self.assertEqual(fila['error'], 'sin_origen')
        curso = Curso.objects.get(pk=fila['destino_id'])
        self.assertEqual(curso.modulos.count(), 0)


@override_settings(
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    SECURE_SSL_REDIRECT=False,
)
class CatalogoFormacionTests(TestCase):
    def setUp(self):
        org = _org('Otra', '900222', '573001000002')
        _curso_origen(org, NOMBRE_RIENDAS, 'https://cdn.example.com/r.mp4')
        _curso_origen(org, NOMBRE_INNOVACION, 'https://cdn.example.com/i.mp4')
        asegurar_cursos_generales()
        self.tel = '573001112233'
        SandboxCanalSesion.objects.update_or_create(
            telefono=self.tel,
            defaults={'habeas_aceptado': True},
        )
        self.base = {
            'From': 'whatsapp:+573001112233',
            'To': 'whatsapp:+14155238886',
        }

    def test_formacion_envia_carrusel_con_foto_y_enlace(self):
        with patch(
            'core.sandbox_canal.enviar_meta_carrusel', return_value={'success': True}
        ) as carrusel:
            out = dispatch_sandbox_menu({**self.base, 'Body': 'formacion'})
        self.assertEqual(out, 'handled')
        self.assertEqual(carrusel.call_count, 1)
        tarjetas = carrusel.call_args.args[2]
        self.assertEqual(len(tarjetas), 3)
        self.assertEqual(tarjetas[2]['url'], URL_TIEMPO)
        self.assertEqual(
            tarjetas[0]['botones'],
            [('ver_riendas', 'Ver curso'), ('info_riendas', 'Más información')],
        )
        self.assertEqual(
            tarjetas[2]['botones'],
            [('ver_tiempo', 'Ver curso'), ('info_tiempo', 'Más información')],
        )
        self.assertTrue(tarjetas[0]['imagen'].startswith('https://'))
        self.assertIn('carrusel_riendas', tarjetas[0]['imagen'])

    def test_carrusel_dos_botones_de_respuesta(self):
        from core.sandbox_canal import enviar_meta_carrusel

        with patch('core.sandbox_canal._post_graph', return_value={'success': True, 'mensaje_id': '1'}) as post:
            out = enviar_meta_carrusel(
                '573001112233',
                'Deslice los cursos.',
                [{
                    'body': '*Riendas*\nLa plata de la semana.',
                    'imagen': 'https://admin.eki.technology/static/carrusel/carrusel_riendas.jpg',
                    'botones': [('ver_riendas', 'Ver curso'), ('info_riendas', 'Más información')],
                }, {
                    'body': '*Tiempo*\nPrioridades en el campo.',
                    'imagen': 'https://admin.eki.technology/static/carrusel/carrusel_tiempo.jpg',
                    'botones': [('ver_tiempo', 'Ver curso'), ('info_tiempo', 'Más información')],
                }],
            )
        self.assertTrue(out['success'])
        payload = post.call_args.args[0]
        self.assertEqual(payload['interactive']['type'], 'carousel')
        cards = payload['interactive']['action']['cards']
        self.assertEqual(len(cards), 2)
        for card in cards:
            botones = card['action']['buttons']
            self.assertEqual(len(botones), 2)
            self.assertTrue(all(b['type'] == 'quick_reply' for b in botones))
            self.assertNotIn('cta_url', card['action'])
        self.assertEqual(cards[0]['type'], 'cta_url')
        self.assertNotIn('name', cards[0]['action'])
        self.assertEqual(cards[0]['action']['buttons'][0]['quick_reply']['id'], 'ver_riendas')
        self.assertEqual(cards[0]['action']['buttons'][1]['quick_reply']['title'], 'Más información')
        self.assertEqual(cards[1]['action']['buttons'][0]['quick_reply']['id'], 'ver_tiempo')

    def test_mas_informacion_manda_la_ficha(self):
        resolver_ruta_sandbox({**self.base, 'Body': 'formacion'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto:
            out = dispatch_sandbox_menu({**self.base, 'Body': 'info_tiempo'})
        self.assertEqual(out, 'handled')
        cuerpo = texto.call_args.args[2]
        self.assertIn(NOMBRE_TIEMPO, cuerpo)
        self.assertIn(URL_TIEMPO, cuerpo)

    def test_ver_curso_no_borra_otro_progreso(self):
        org = Cliente.objects.get(nit='900222')
        propio = Curso.objects.create(nombre='Curso de la finca', descripcion='d', cliente=org, activo=True)
        est = Estudiante.objects.create(
            nombre='Ana',
            cedula='1088991',
            telefono=self.tel,
            cliente=org,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        otro = ProgresoEstudiante.objects.create(estudiante=est, curso=propio, completado=False)
        resolver_ruta_sandbox({**self.base, 'Body': 'formacion'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto:
            out = dispatch_sandbox_menu({**self.base, 'Body': 'ver_tiempo'})
        self.assertEqual(out, 'handled')
        self.assertTrue(ProgresoEstudiante.objects.filter(pk=otro.pk).exists())
        general = Curso.objects.get(nombre=NOMBRE_TIEMPO, catalogo_menu=True)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=general).exists()
        )
        est.refresh_from_db()
        self.assertEqual(est.cliente_id, org.id)
        self.assertEqual((est.contexto_temporal or {}).get('curso_activo_id'), general.id)
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, MODO_CURSOS)
        self.assertIn('listo', texto.call_args.args[2].lower())
        self.assertEqual(
            resolver_ruta_sandbox({**self.base, 'Body': 'listo'}).action,
            'cursos',
        )

    def test_un_curso_general_por_mes(self):
        from datetime import timedelta

        from django.utils import timezone

        resolver_ruta_sandbox({**self.base, 'Body': 'formacion'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            dispatch_sandbox_menu({**self.base, 'Body': 'ver_riendas'})
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        tiempo = Curso.objects.get(nombre=NOMBRE_TIEMPO, catalogo_menu=True)
        est = Estudiante.objects.get(telefono=self.tel)
        self.assertTrue(ProgresoEstudiante.objects.filter(estudiante=est, curso=riendas).exists())
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto:
            out = dispatch_sandbox_menu({**self.base, 'Body': 'ver_tiempo'})
        self.assertEqual(out, 'handled')
        self.assertIn('uno por mes', texto.call_args.args[2].lower())
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=est, curso=tiempo).exists())
        progreso = ProgresoEstudiante.objects.get(estudiante=est, curso=riendas)
        progreso.fecha_inicio = timezone.now() - timedelta(days=40)
        progreso.save(update_fields=['fecha_inicio'])
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto:
            dispatch_sandbox_menu({**self.base, 'Body': 'ver_tiempo'})
        self.assertTrue(ProgresoEstudiante.objects.filter(estudiante=est, curso=tiempo).exists())
        self.assertIn('listo', texto.call_args.args[2].lower())
