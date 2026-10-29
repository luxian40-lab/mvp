"""Cursos sin cliente y carrusel de Formación."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.cursos_generales import (
    NOMBRE_INNOVACION,
    NOMBRE_RIENDAS,
    NOMBRE_TIEMPO,
    URL_INNOVACION,
    URL_RIENDAS,
    URL_TIEMPO,
    asegurar_cursos_generales,
    inscribir_en_catalogo,
    item_catalogo,
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
from core.sandbox_menu import (
    MODO_ASESORIA,
    MODO_CURSOS,
    MODO_MENU,
    dispatch_sandbox_menu,
    resolver_ruta_sandbox,
)


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
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
    WHATSAPP_API_VERSION='v19.0',
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
        tarjetas = {t['clave']: t for t in carrusel.call_args.args[2]}
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, cliente__isnull=True)
        tiempo = Curso.objects.get(nombre=NOMBRE_TIEMPO, cliente__isnull=True)
        self.assertEqual(len(tarjetas), 3)
        self.assertEqual(tarjetas[f'curso_{tiempo.id}']['url'], URL_TIEMPO)
        self.assertIn(URL_TIEMPO, tarjetas[f'curso_{tiempo.id}']['body'])
        self.assertEqual(
            tarjetas[f'curso_{riendas.id}']['botones'],
            [(f'ver_curso_{riendas.id}', 'Ver curso'), (f'info_curso_{riendas.id}', 'Más información')],
        )
        self.assertTrue(tarjetas[f'curso_{riendas.id}']['imagen'].startswith('https://'))
        self.assertIn('carrusel_riendas', tarjetas[f'curso_{riendas.id}']['imagen'])

    def test_formacion_muestra_el_carrusel_aunque_ya_tenga_curso(self):
        from core.models import Estudiante, ProgresoEstudiante

        curso = Curso.objects.filter(catalogo_menu=True).first()
        est = Estudiante.objects.create(
            nombre='Ya', cedula='CF1', telefono=self.tel, acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        with patch(
            'core.sandbox_canal.enviar_meta_carrusel', return_value={'success': True}
        ) as carrusel:
            dispatch_sandbox_menu({**self.base, 'Body': 'formacion'})
        self.assertEqual(carrusel.call_count, 1)

    def test_menu_con_un_curso_muestra_el_menu(self):
        from core.models import Estudiante, ProgresoEstudiante

        curso = Curso.objects.filter(catalogo_menu=True).first()
        Estudiante.objects.create(
            nombre='Ya', cedula='CF2', telefono=self.tel, acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=Estudiante.objects.get(telefono=self.tel), curso=curso
        )
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo=MODO_CURSOS)
        with patch('core.sandbox_canal.enviar_meta_carrusel') as carrusel, patch(
            'core.sandbox_canal.enviar_meta_botones', return_value={'success': True}
        ) as botones, patch(
            'core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}
        ) as texto:
            dispatch_sandbox_menu({**self.base, 'Body': 'Menú'})
        carrusel.assert_not_called()
        texto.assert_not_called()
        ids = [boton[0] for boton in botones.call_args.args[2]]
        self.assertEqual(ids, ['formacion', 'asesoria'])
        self.assertNotIn('Seguimos', botones.call_args.args[1])
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, MODO_MENU)

    def test_menu_luego_asesoria_abre_el_asesor(self):
        from core.models import Estudiante, ProgresoEstudiante

        curso = Curso.objects.filter(catalogo_menu=True).first()
        Estudiante.objects.create(
            nombre='Ya', cedula='CF2b', telefono=self.tel, acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=Estudiante.objects.get(telefono=self.tel), curso=curso
        )
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo=MODO_CURSOS)
        with patch(
            'core.sandbox_canal.enviar_meta_botones', return_value={'success': True}
        ), patch(
            'core.sandbox_canal.enviar_meta_lista', return_value={'success': True}
        ) as lista, patch(
            'core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}
        ) as texto:
            dispatch_sandbox_menu({**self.base, 'Body': 'menu'})
            dispatch_sandbox_menu({**self.base, 'Body': 'asesoria'})
        texto.assert_not_called()
        self.assertEqual(lista.call_count, 1)
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, MODO_ASESORIA)

    def test_dos_cursos_abiertos_formacion_sigue_mostrando_el_carrusel(self):
        from core.models import Estudiante, ProgresoEstudiante

        cursos = list(Curso.objects.filter(catalogo_menu=True).order_by('id')[:2])
        est = Estudiante.objects.create(
            nombre='Dos', cedula='CF3', telefono=self.tel, acepto_terminos=True,
        )
        for curso in cursos:
            ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        with patch(
            'core.sandbox_canal.enviar_meta_carrusel', return_value={'success': True}
        ) as carrusel:
            dispatch_sandbox_menu({**self.base, 'Body': 'formacion'})
        self.assertEqual(carrusel.call_count, 1)

    def test_curso_nuevo_marcado_en_el_menu_entra_al_carrusel_y_se_inscribe(self):
        from core.cursos_generales import inscribir_en_catalogo, tarjetas_catalogo

        nuevo = Curso.objects.create(
            nombre='Café de altura',
            descripcion='Cosecha y precio en la finca.',
            cliente=None,
            activo=True,
            catalogo_menu=True,
        )
        Modulo.objects.create(
            curso=nuevo,
            numero=1,
            titulo='Cosecha',
            descripcion='d',
            contenido='c',
            imagen_portada_url='https://cdn.example.com/cafe.jpg',
        )
        tarjeta = next(t for t in tarjetas_catalogo() if t['clave'] == f'curso_{nuevo.id}')
        self.assertEqual(tarjeta['imagen'], 'https://cdn.example.com/cafe.jpg')
        self.assertEqual(tarjeta['botones'][0][0], f'ver_curso_{nuevo.id}')
        resultado = inscribir_en_catalogo('573009991111', f'curso_{nuevo.id}')
        self.assertTrue(resultado['ok'])
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante__telefono='573009991111', curso=nuevo).exists()
        )

    def test_curso_general_nuevo_entra_al_menu_sin_marcarlo(self):
        from core.cursos_generales import tarjetas_catalogo

        nuevo = Curso.objects.create(
            nombre='Cacao fino', descripcion='Fermentación en cajón.', cliente=None, activo=True
        )
        self.assertTrue(nuevo.catalogo_menu)
        self.assertIn(f'curso_{nuevo.id}', [t['clave'] for t in tarjetas_catalogo()])

    def test_mas_de_diez_cursos_van_en_dos_listas(self):
        from core.cursos_generales import paginas_carrusel, tarjetas_catalogo

        for i in range(9):
            Curso.objects.create(
                nombre=f'General {i:02d}', descripcion='d', cliente=None, activo=True
            )
        paginas = paginas_carrusel(tarjetas_catalogo())
        self.assertEqual([len(p) for p in paginas], [10, 2])
        with patch(
            'core.sandbox_canal.enviar_meta_lista', return_value={'success': True}
        ) as lista, patch(
            'core.sandbox_canal.enviar_meta_carrusel', return_value={'success': True}
        ) as carrusel:
            dispatch_sandbox_menu({**self.base, 'Body': 'formacion'})
        carrusel.assert_not_called()
        self.assertEqual(lista.call_count, 2)
        self.assertEqual(len(lista.call_args_list[0].args[3]), 10)
        self.assertEqual(len(lista.call_args_list[1].args[3]), 2)

    def test_carrusel_dos_botones_de_respuesta(self):
        from core.sandbox_canal import enviar_meta_carrusel

        with patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': '1'}) as post:
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

    def test_mas_informacion_abre_la_pagina_en_el_carrusel(self):
        from core.sandbox_canal import enviar_meta_carrusel

        with patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': '1'}) as post:
            out = enviar_meta_carrusel(
                '573001112233',
                'Deslice los cursos.',
                [{
                    'body': f'*Tiempo*\n{URL_TIEMPO}',
                    'imagen': 'https://admin.eki.technology/static/carrusel/carrusel_tiempo.jpg',
                    'url': URL_TIEMPO,
                    'botones': [('ver_tiempo', 'Ver curso'), ('info_tiempo', 'Más información')],
                }, {
                    'body': f'*Innovación*\n{URL_INNOVACION}',
                    'imagen': 'https://admin.eki.technology/static/carrusel/carrusel_innovacion.jpg',
                    'url': URL_INNOVACION,
                    'botones': [('ver_innovacion', 'Ver curso'), ('info_innovacion', 'Más información')],
                }],
            )
        self.assertTrue(out['success'])
        self.assertEqual(post.call_count, 1)
        cards = post.call_args.args[0]['interactive']['action']['cards']
        self.assertIn(URL_TIEMPO, cards[0]['body']['text'])
        self.assertIn(URL_INNOVACION, cards[1]['body']['text'])
        self.assertEqual(cards[0]['action']['buttons'][1]['quick_reply']['id'], 'info_tiempo')
        self.assertTrue(all(
            b['type'] == 'quick_reply'
            for card in cards
            for b in card['action']['buttons']
        ))

    def test_nombre_corto_de_tiempo_sigue_teniendo_la_pagina(self):
        from core.cursos_generales import _url_de_curso, tarjetas_catalogo

        corto = 'Gestión de tiempo y productividad personal'
        self.assertEqual(_url_de_curso(corto), URL_TIEMPO)
        Curso.objects.filter(nombre=NOMBRE_TIEMPO, cliente__isnull=True).update(nombre=corto)
        tiempo = Curso.objects.get(nombre=corto, catalogo_menu=True)
        tarjetas = {t['clave']: t for t in tarjetas_catalogo()}
        self.assertEqual(tarjetas[f'curso_{tiempo.id}']['url'], URL_TIEMPO)
        self.assertIn(URL_TIEMPO, tarjetas[f'curso_{tiempo.id}']['body'])
        resolver_ruta_sandbox({**self.base, 'Body': 'formacion'})
        with patch(
            'core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': '1'},
        ) as post:
            out = dispatch_sandbox_menu({**self.base, 'Body': f'info_curso_{tiempo.id}'})
        self.assertEqual(out, 'handled')
        payload = post.call_args.args[0]
        self.assertEqual(payload['interactive']['type'], 'cta_url')
        self.assertEqual(payload['interactive']['action']['parameters']['url'], URL_TIEMPO)
        self.assertEqual(
            payload['interactive']['action']['parameters']['display_text'], 'Más información',
        )

    def test_mas_informacion_abre_la_pagina_del_programa(self):
        self.assertEqual(URL_TIEMPO, 'https://www.eki.com.co/programas/comercializacion-ventas')
        self.assertEqual(
            URL_INNOVACION, 'https://www.eki.com.co/programas/emprendimiento-agro-rural',
        )
        self.assertEqual(URL_RIENDAS, 'https://www.eki.com.co/programas/tome-las-riendas')
        resolver_ruta_sandbox({**self.base, 'Body': 'formacion'})
        tiempo = Curso.objects.get(nombre=NOMBRE_TIEMPO, catalogo_menu=True)
        innovacion = Curso.objects.get(nombre=NOMBRE_INNOVACION, catalogo_menu=True)
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        self.assertEqual(item_catalogo(f'curso_{tiempo.id}')['url'], URL_TIEMPO)
        self.assertEqual(item_catalogo(f'curso_{innovacion.id}')['url'], URL_INNOVACION)
        self.assertEqual(item_catalogo(f'curso_{riendas.id}')['url'], URL_RIENDAS)
        with patch(
            'core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': '1'},
        ) as post:
            out = dispatch_sandbox_menu({**self.base, 'Body': f'info_curso_{tiempo.id}'})
        self.assertEqual(out, 'handled')
        payload = post.call_args.args[0]
        self.assertEqual(payload['interactive']['type'], 'cta_url')
        self.assertEqual(payload['interactive']['action']['parameters']['url'], URL_TIEMPO)
        self.assertEqual(
            payload['interactive']['action']['parameters']['display_text'], 'Más información',
        )
        self.assertEqual(payload['interactive']['body']['text'], NOMBRE_TIEMPO)
        self.assertNotIn('menu para volver', payload['interactive']['body']['text'])

    def test_mas_informacion_de_los_programas_nuevos(self):
        from core.cursos_generales import _url_de_curso, tarjetas_catalogo

        esperadas = {
            'Comercialización y ventas': 'https://eki.com.co/programas/comercializacion-y-ventas',
            'Gestión de costos agropecuarios': 'https://eki.com.co/programas/gestion-costos-agropecuarios',
            'Maquinaria y Herramientas para el Agro':
                'https://www.eki.com.co/programas/maquinaria-herramientas-agro',
            'Introducción a un modelo de negocios Rural Sostenible':
                'https://eki.com.co/programas/modelo-negocio-rural-sostenible',
        }
        for nombre, url in esperadas.items():
            self.assertEqual(_url_de_curso(nombre), url)
            Curso.objects.create(
                nombre=nombre, descripcion='d', cliente=None, activo=True, catalogo_menu=True,
            )
        tarjetas = {t['titulo']: t for t in tarjetas_catalogo()}
        for nombre, url in esperadas.items():
            self.assertEqual(tarjetas[nombre]['url'], url)
            self.assertIn(url, tarjetas[nombre]['body'])
            self.assertLessEqual(len(tarjetas[nombre]['body']), 160)
        self.assertEqual(_url_de_curso('Gestión de tiempo y productividad personal'), URL_TIEMPO)

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
        from datetime import timedelta

        from django.utils import timezone

        ProgresoEstudiante.objects.filter(pk=otro.pk).update(fecha_inicio=timezone.now() - timedelta(days=40))
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
        self.assertIn('[send_button:continuemos]', texto.call_args.args[2].lower())
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
        self.assertIn('[send_button:continuemos]', texto.call_args.args[2].lower())

    def test_ver_curso_con_sesion_habeas_alinea_la_ficha_y_continuemos_entra(self):
        est = Estudiante.objects.create(
            nombre='Julian',
            cedula='GEN0629',
            telefono=self.tel,
            acepto_terminos=False,
            estado_chat='ESPERANDO_HABEAS_DATA',
            estado_onboarding='nuevo',
        )
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            out = dispatch_sandbox_menu({**self.base, 'Body': f'ver_curso_{riendas.id}'})
        self.assertEqual(out, 'handled')
        habeas.assert_called_once()
        est.refresh_from_db()
        self.assertFalse(est.acepto_terminos)
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=est, curso=riendas).exists())
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            ruta = dispatch_sandbox_menu({**self.base, 'Body': 'continuemos'})
        self.assertEqual(ruta, 'handled')
        habeas.assert_called_once()

    def test_flujo_ver_curso_inscribe_y_asesoria_abre_agente(self):
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        with patch(
            'core.sandbox_canal.enviar_meta_carrusel', return_value={'success': True},
        ) as carrusel:
            self.assertEqual(
                dispatch_sandbox_menu({**self.base, 'Body': 'formacion'}), 'handled',
            )
        self.assertEqual(carrusel.call_count, 1)
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            self.assertEqual(
                dispatch_sandbox_menu({**self.base, 'Body': f'ver_curso_{riendas.id}'}),
                'handled',
            )
        est = Estudiante.objects.get(telefono=self.tel)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=riendas).exists()
        )
        with patch('core.sandbox_canal.enviar_sandbox_habeas') as habeas:
            self.assertEqual(
                dispatch_sandbox_menu({**self.base, 'Body': 'continuemos'}), 'cursos',
            )
            habeas.assert_not_called()
        with patch(
            'core.sandbox_canal.enviar_meta_botones', return_value={'success': True},
        ):
            self.assertEqual(dispatch_sandbox_menu({**self.base, 'Body': 'menu'}), 'handled')
        with patch(
            'core.sandbox_canal.enviar_meta_lista', return_value={'success': True},
        ) as lista:
            self.assertEqual(
                dispatch_sandbox_menu({**self.base, 'Body': 'asesoria'}), 'handled',
            )
        self.assertEqual(lista.call_count, 1)
        with patch(
            'core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True},
        ), patch('core.sandbox_canal.enviar_sandbox_habeas') as habeas:
            self.assertEqual(
                dispatch_sandbox_menu({**self.base, 'Body': 'ventas'}), 'handled',
            )
            habeas.assert_not_called()
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'ventas')
        with patch(
            'core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True},
        ):
            self.assertEqual(dispatch_sandbox_menu({**self.base, 'Body': 'menu'}), 'handled')
            self.assertEqual(dispatch_sandbox_menu({**self.base, 'Body': 'nat'}), 'handled')
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'nat')

    def test_inscribir_sin_sesion_habeas_no_marca_terminos(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(habeas_aceptado=False)
        est = Estudiante.objects.create(
            nombre='Julian',
            cedula='GEN0630',
            telefono=self.tel,
            acepto_terminos=False,
            estado_chat='ESPERANDO_HABEAS_DATA',
            estado_onboarding='nuevo',
        )
        riendas = Curso.objects.get(nombre=NOMBRE_RIENDAS, catalogo_menu=True)
        inscribir_en_catalogo(self.tel, f'curso_{riendas.id}')
        est.refresh_from_db()
        self.assertFalse(est.acepto_terminos)
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertTrue(ProgresoEstudiante.objects.filter(estudiante=est, curso=riendas).exists())
