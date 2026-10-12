"""Listado y ficha de Campañas Meta. No llama a Graph salvo que el test lo simule."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.campana_audiencia import marcar_programadas_sin_aprobacion, resumir_audiencia
from core.meta_waba import ejecutar_campana_meta
from core.models import Estudiante
from core.models_campana_meta import CampanaMeta, EnvioCampanaMeta, PlantillaMeta
from core.models_extras import GrupoEstudiantes

PHONE = '495439026995771'
CEDULA = 'ZZNOMOSTRAR-88421'


def _plantilla(**kwargs):
    datos = {
        'nombre_interno': 'Aviso',
        'meta_name': 'aviso_campana',
        'idioma': 'es',
        'categoria': 'UTILITY',
        'tipo': 'TEXTO',
        'cuerpo': 'Hola {{1}}, su organización es {{2}}.',
        'ejemplos_cuerpo': 'Ana|Cooperativa',
        'estado': 'APPROVED',
        'activa': True,
        'waba_id': '111',
    }
    datos.update(kwargs)
    return PlantillaMeta.objects.create(**datos)


def _persona(nombre, telefono, cedula, **kwargs):
    return Estudiante.objects.create(
        nombre=nombre,
        telefono=telefono,
        cedula=cedula,
        activo=True,
        **kwargs,
    )


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_BUSINESS_ACCOUNT_ID='111',
    WHATSAPP_API_VERSION='v21.0',
    EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629'],
)
class CampanasAdminTests(TestCase):
    def setUp(self):
        User.objects.create_superuser('cm_admin', 'cm@t.com', 'pass12345')
        self.client.login(username='cm_admin', password='pass12345')
        self.plantilla = _plantilla()

    def _campana(self, **kwargs):
        datos = {'nombre': 'Lanzamiento', 'plantilla': self.plantilla}
        datos.update(kwargs)
        return CampanaMeta.objects.create(**datos)

    def test_pestanas_y_embudo_del_listado(self):
        borrador = self._campana(nombre='Borrador uno')
        programada = self._campana(
            nombre='Sale luego',
            fecha_programada=timezone.now() + timedelta(days=2),
        )
        programada.destinatarios.add(_persona('Ana', '573001110001', 'c-ana'))
        enviada = self._campana(nombre='Ya salio', ejecutada=True, total_enviados=2)
        persona = _persona('Luis', '573001110002', 'c-luis')
        EnvioCampanaMeta.objects.create(
            campana=enviada, estudiante=persona, estado='ENVIADO', estado_entrega='read',
        )
        EnvioCampanaMeta.objects.create(
            campana=enviada,
            estudiante=_persona('Mara', '573001110003', 'c-mara'),
            estado='ENVIADO',
            estado_entrega='delivered',
        )
        with_error = self._campana(nombre='Con fallo', ejecutada=True)
        EnvioCampanaMeta.objects.create(
            campana=with_error,
            estudiante=_persona('Paz', '573001110004', 'c-paz'),
            estado='FALLIDO',
            error_codigo='131026',
            respuesta='undeliverable',
        )
        pagina = self.client.get(reverse('admin:core_campanameta_changelist'))
        self.assertContains(pagina, 'Todas · 4')
        self.assertContains(pagina, 'Borradores · 1')
        self.assertContains(pagina, 'Programadas · 1')
        self.assertContains(pagina, 'Enviadas · 1')
        self.assertContains(pagina, 'Con errores · 1')
        self.assertContains(pagina, 'Enviados 2')
        self.assertContains(pagina, 'Entregados 2')
        self.assertContains(pagina, 'Leídos 1')
        self.assertContains(pagina, 'Respondieron Sin dato')
        self.assertContains(pagina, 'Nueva campaña')
        self.assertContains(pagina, 'Ejecutar campañas Meta (envío Cloud API)')
        self.assertContains(pagina, 'Buscar')
        self.assertContains(pagina, 'Filtros')
        self.assertNotContains(pagina, 'Type to search')
        self.assertNotContains(pagina, 'Filters')
        self.assertNotContains(pagina, 'Estado plantilla')
        self.assertContains(pagina, reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]))
        borradores = self.client.get(reverse('admin:core_campanameta_changelist'), {'eki_cm': 'borradores'})
        self.assertContains(borradores, borrador.nombre)
        self.assertNotContains(borradores, 'Ya salio')

    def test_la_accion_masiva_encola_la_campana_aprobada(self):
        persona = _persona('Masiva', '573001110099', 'c-masiva')
        campana = self._campana(nombre='Masiva')
        campana.destinatarios.add(persona)
        with patch('core.meta_waba.encolar_campana_meta', return_value='sync') as encolar:
            self.client.post(reverse('admin:core_campanameta_changelist'), {
                'action': 'ejecutar_campanas',
                '_selected_action': [str(campana.pk)],
            })
        encolar.assert_called_once_with(campana.id)

    def test_la_accion_masiva_no_encola_si_falta_aprobacion(self):
        borrador = _plantilla(nombre_interno='Sin aprobar', meta_name='sin_aprobar_masiva', estado='BORRADOR')
        persona = _persona('Otra', '573001110098', 'c-otra-masiva')
        campana = self._campana(nombre='Bloqueada masiva', plantilla=borrador)
        campana.destinatarios.add(persona)
        with patch('core.meta_waba.encolar_campana_meta') as encolar:
            self.client.post(reverse('admin:core_campanameta_changelist'), {
                'action': 'ejecutar_campanas',
                '_selected_action': [str(campana.pk)],
            })
        encolar.assert_not_called()

    def test_audiencia_une_grupos_y_personas_sin_repetir(self):
        ana = _persona('Ana', '573001110011', 'c-ana2')
        leo = _persona('Leo', '573001110012', 'c-leo')
        g1 = GrupoEstudiantes.objects.create(nombre='Norte')
        g2 = GrupoEstudiantes.objects.create(nombre='Sur')
        g1.estudiantes.add(ana, leo)
        g2.estudiantes.add(ana)
        campana = self._campana()
        campana.grupos.add(g1, g2)
        campana.destinatarios.add(ana)
        from core.campana_audiencia import aplicar_mapeo

        campana.reglas_variables = {
            '1': {'origen': 'nombre', 'si_falta': 'respaldo', 'respaldo': '', 'texto': ''},
            '2': {'origen': 'organizacion', 'si_falta': 'respaldo', 'respaldo': 'eki', 'texto': ''},
        }
        aplicar_mapeo(campana)
        campana.save()
        resumen = resumir_audiencia(campana)
        self.assertEqual(resumen['suma'], 4)
        self.assertEqual(resumen['repetidas'], 2)
        self.assertEqual(resumen['reciben'], 2)
        with patch('core.meta_waba.time.sleep'), \
                patch('core.meta_waba.requests.get') as get, \
                patch('core.meta_waba.requests.post') as post:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {'data': [{'id': PHONE}]}
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'wamid.x'}]}
            ejecutar_campana_meta(campana)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            EnvioCampanaMeta.objects.filter(campana=campana, estado='ENVIADO').count(),
            2,
        )

    def test_exclusiones_de_optout_reciente_y_telefono(self):
        buena = _persona('Buena', '573001110021', 'c-buena')
        optout = _persona('Opt', '573001110022', 'c-opt')
        optout.wa_optout_fecha = timezone.now()
        optout.save(update_fields=['wa_optout_fecha'])
        reciente = _persona('Reciente', '573001110023', 'c-rec')
        invalida = _persona('Corta', '123', 'c-corta')
        previa = self._campana(nombre='Previa')
        EnvioCampanaMeta.objects.create(campana=previa, estudiante=reciente, estado='ENVIADO')
        campana = self._campana(nombre='Nueva')
        campana.destinatarios.add(buena, optout, reciente, invalida)
        resumen = resumir_audiencia(campana)
        self.assertEqual(resumen['optout'], 1)
        self.assertEqual(resumen['recientes'], 1)
        self.assertEqual(resumen['sin_whatsapp'], 1)
        self.assertEqual(resumen['reciben_ids'], [buena.pk])

    def test_ninguna_pantalla_muestra_la_cedula(self):
        persona = _persona('Nubia', '573001110031', CEDULA)
        persona.refresh_from_db()
        campana = self._campana()
        campana.destinatarios.add(persona)
        ficha = self.client.get(reverse('admin:core_campanameta_change', args=[campana.pk]))
        self.assertNotContains(ficha, persona.cedula)
        self.assertContains(ficha, 'Nubia')
        lista = self.client.get(reverse('admin:core_campanameta_lista', args=[campana.pk]))
        self.assertNotContains(lista, persona.cedula)
        self.assertContains(lista, 'Nubia')
        busqueda = self.client.get(reverse('admin:core_campanameta_buscar_personas'), {'q': 'Nubia'})
        self.assertNotContains(busqueda, persona.cedula)
        self.assertContains(busqueda, 'Nubia')
        from pathlib import Path

        js = Path('static/admin/js/campana_meta_admin.js').read_text(encoding='utf-8')
        cabeza = js.split('function iniciar')[0]
        self.assertNotIn("getElementById('eki-cm')", cabeza)
        self.assertIn('DOMContentLoaded', js)

    def test_plantilla_no_aprobada_no_se_elige_ni_envia(self):
        borrador = _plantilla(nombre_interno='No lista', meta_name='no_lista', estado='BORRADOR')
        ficha = self.client.get(reverse('admin:core_campanameta_add'))
        self.assertContains(ficha, self.plantilla.nombre_interno)
        self.assertNotContains(ficha, 'No lista')
        self.assertNotContains(ficha, '(APPROVED)')
        campana = self._campana(plantilla=borrador, nombre='Bloqueada')
        pagina = self.client.get(reverse('admin:core_campanameta_change', args=[campana.pk]))
        self.assertContains(pagina, 'Meta todavía no aprobó esta plantilla.')
        self.assertNotContains(pagina, 'Enviar a ')
        with patch('core.meta_waba.encolar_campana_meta') as encolar:
            self.client.post(reverse('admin:core_campanameta_enviar', args=[campana.pk]))
        encolar.assert_not_called()
        campana.refresh_from_db()
        self.assertEqual(campana.pausa_motivo, 'plantilla_no_aprobada')

    def test_ejecutar_dos_veces_no_duplica(self):
        persona = _persona('Una', '573001110041', 'c-una')
        campana = self._campana()
        campana.destinatarios.add(persona)
        from core.campana_audiencia import aplicar_mapeo

        campana.reglas_variables = {
            '1': {'origen': 'nombre', 'si_falta': 'respaldo', 'respaldo': '', 'texto': ''},
            '2': {'origen': 'fijo', 'si_falta': 'respaldo', 'respaldo': '', 'texto': 'eki'},
        }
        aplicar_mapeo(campana)
        campana.save()
        with patch('core.meta_waba.time.sleep'), \
                patch('core.meta_waba.requests.get') as get, \
                patch('core.meta_waba.requests.post') as post:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {'data': [{'id': PHONE}]}
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'wamid.1'}]}
            ejecutar_campana_meta(campana)
            ejecutar_campana_meta(campana)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(EnvioCampanaMeta.objects.filter(campana=campana, estado='ENVIADO').count(), 1)

    def test_programada_sin_aprobacion_queda_en_error_y_no_envia(self):
        campana = self._campana(fecha_programada=timezone.now() - timedelta(minutes=5))
        campana.destinatarios.add(_persona('Sol', '573001110051', 'c-sol'))
        self.plantilla.estado = 'PAUSED'
        self.plantilla.save(update_fields=['estado'])
        with patch('core.meta_waba.encolar_campana_meta') as encolar:
            from core.tasks import enviar_campanas_meta_programadas

            enviar_campanas_meta_programadas()
        encolar.assert_not_called()
        campana.refresh_from_db()
        self.assertTrue(campana.pausada)
        self.assertEqual(campana.pausa_motivo, 'plantilla_no_aprobada')
        self.assertEqual(EnvioCampanaMeta.objects.filter(campana=campana).count(), 0)
        self.assertEqual(marcar_programadas_sin_aprobacion(), 0)
        pagina = self.client.get(reverse('admin:core_campanameta_changelist'), {'eki_cm': 'errores'})
        self.assertContains(pagina, campana.nombre)

    def test_si_falta_cambia_el_conteo(self):
        con_org = _persona('Con', '573001110061', 'c-con')
        from core.models import Cliente

        org = Cliente.objects.create(
            nombre='Cooperativa',
            contacto_principal='Ada',
            email='coop@example.com',
        )
        con_org.cliente = org
        con_org.save(update_fields=['cliente'])
        sin_org = _persona('Sin', '573001110062', 'c-sin')
        campana = self._campana()
        campana.destinatarios.add(con_org, sin_org)
        campana.reglas_variables = {
            '1': {'origen': 'nombre', 'si_falta': 'respaldo', 'respaldo': '', 'texto': ''},
            '2': {'origen': 'organizacion', 'si_falta': 'excluir', 'respaldo': '', 'texto': ''},
        }
        campana.save(update_fields=['reglas_variables'])
        self.assertEqual(resumir_audiencia(campana)['reciben'], 1)
        campana.reglas_variables['2']['si_falta'] = 'respaldo'
        campana.reglas_variables['2']['respaldo'] = 'su organización'
        campana.save(update_fields=['reglas_variables'])
        self.assertEqual(resumir_audiencia(campana)['reciben'], 2)

    def test_cambiar_plantilla_conserva_la_audiencia(self):
        persona = _persona('Conserva', '573001110071', 'c-cons')
        campana = self._campana()
        campana.destinatarios.add(persona)
        otra = _plantilla(
            nombre_interno='Corta',
            meta_name='corta_campana',
            cuerpo='Hola {{1}}, le escribimos hoy.',
            ejemplos_cuerpo='Ana',
        )
        ficha = self.client.get(reverse('admin:core_campanameta_change', args=[campana.pk]))
        datos = {
            'nombre': campana.nombre,
            'plantilla': str(otra.pk),
            'phone_number_id': PHONE,
            'dias_repeticion': '14',
            'personas_ids': str(persona.pk),
            'grupos_ids': '',
            'reglas_json': '{}',
            '_continue': '1',
        }
        datos.update({k: v for k, v in {}})
        token = ficha.cookies.get('csrftoken')
        if token:
            datos['csrfmiddlewaretoken'] = token.value
        else:
            import re
            hallado = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', ficha.content.decode())
            datos['csrfmiddlewaretoken'] = hallado.group(1)
        resp = self.client.post(reverse('admin:core_campanameta_change', args=[campana.pk]), datos)
        self.assertEqual(resp.status_code, 302)
        campana.refresh_from_db()
        self.assertEqual(campana.plantilla_id, otra.pk)
        self.assertEqual(list(campana.destinatarios.values_list('pk', flat=True)), [persona.pk])
        self.assertIn('1', campana.reglas_variables)
        self.assertNotIn('2', campana.reglas_variables)

    def test_pestana_de_plantilla_lista_solo_sus_campanas(self):
        propia = self._campana(nombre='Solo esta')
        otra_plantilla = _plantilla(nombre_interno='Otra', meta_name='otra_campana', cuerpo='Texto sin variables hoy.')
        CampanaMeta.objects.create(nombre='De otra', plantilla=otra_plantilla)
        pagina = self.client.get(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]))
        self.assertContains(pagina, 'Campañas')
        self.assertContains(pagina, propia.nombre)
        self.assertNotContains(pagina, 'De otra')

    def test_prueba_rechaza_un_numero_de_cliente(self):
        campana = self._campana()
        resp = self.client.post(
            reverse('admin:core_campanameta_enviar_prueba', args=[campana.pk]),
            {'telefono': '573009998877'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(EnvioCampanaMeta.objects.count(), 0)
