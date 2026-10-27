"""Recordatorio a quien tiene contenido disponible y no avanza."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    AvisoModuloDisponible,
    AvisoModuloEnviado,
    Cliente,
    Curso,
    Estudiante,
    HabilitacionModuloDripCliente,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    RecordatorioCurso,
    RecordatorioCursoEnviado,
    WhatsappLog,
)
from core.models_campana_meta import PlantillaMeta
from core.models_extras import GrupoEstudiantes
from core.tests_aviso_modulo import AJUSTES, LINEA_2, WABA_2, _sender_ok


@override_settings(**AJUSTES, EKI_RECORDATORIO_CURSO_ENABLED=True)
class RecordatorioCursoTests(TestCase):
    def setUp(self):
        self.ahora = timezone.localtime().replace(hour=9, minute=5, second=0, microsecond=0)
        self.cliente = Cliente.objects.create(
            nombre='Alitic', contacto_principal='A', email='a@test.com', telefono='573001120000', activo=True,
        )
        self.curso = Curso.objects.create(nombre='Crea y Vende', descripcion='d', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(curso=self.curso, numero=1, titulo='Su idea', descripcion='d', contenido='c')
        self.m2 = Modulo.objects.create(curso=self.curso, numero=2, titulo='Su cliente', descripcion='d', contenido='c')
        self.plantilla = PlantillaMeta.objects.create(
            nombre_interno='Recordatorio de curso',
            meta_name='recordatorio_curso',
            idioma='es',
            categoria='UTILITY',
            tipo='TEXTO',
            cuerpo='Hola {{1}}, recuerde que inició el curso *{{2}}* en eki',
            estado='APPROVED',
            activa=True,
            waba_id=WABA_2,
        )
        self.recordatorio = RecordatorioCurso.objects.create(
            cliente=self.cliente, curso=self.curso, plantilla=self.plantilla, phone_number_id=LINEA_2,
        )

    def _estudiante(self, telefono, *, escribio_hace=3, termino_m1=False, **extra):
        datos = dict(acepto_terminos=True)
        datos.update(extra)
        estudiante = Estudiante.objects.create(
            cedula=f'CC{telefono[-6:]}', nombre='Ana', telefono=telefono, cliente=self.cliente, activo=True, **datos,
        )
        progreso = ProgresoEstudiante.objects.create(estudiante=estudiante, curso=self.curso, modulo_actual=self.m1)
        if termino_m1:
            ModuloCompletado.objects.create(progreso=progreso, modulo=self.m1)
        if escribio_hace is not None:
            log = WhatsappLog.objects.create(
                telefono=telefono, mensaje='listo', tipo='INCOMING', canal='meta', estudiante=estudiante,
            )
            WhatsappLog.objects.filter(pk=log.pk).update(fecha=self.ahora - timedelta(days=escribio_hace))
        return estudiante

    def _ejecutar(self, ahora=None):
        from core.avisos.recordatorio_curso import ejecutar

        sender = _sender_ok()
        with patch('core.meta_token.token_invalido', return_value=False), \
                patch('core.lineas.sender.sender_de_linea', return_value=sender):
            resultado = ejecutar(ahora or self.ahora)
        return resultado, sender

    def _enviado_hace(self, estudiante, dias):
        envio = RecordatorioCursoEnviado.objects.create(
            recordatorio=self.recordatorio, estudiante=estudiante,
            dia=timezone.localdate(self.ahora - timedelta(days=dias)), estado='ENVIADO',
        )
        RecordatorioCursoEnviado.objects.filter(pk=envio.pk).update(fecha=self.ahora - timedelta(days=dias))

    def test_recuerda_a_quien_lleva_dias_sin_avanzar(self):
        ana = self._estudiante('573001120001')
        resultado, sender = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)
        args = sender.plantilla.call_args.args
        self.assertEqual(args[0], ana.telefono)
        self.assertEqual(args[1], 'recordatorio_curso')
        self.assertEqual(args[2], {'1': 'Ana', '2': 'Crea y Vende'})
        self.assertEqual(RecordatorioCursoEnviado.objects.get(estudiante=ana).estado, 'ENVIADO')

    def test_no_recuerda_si_escribio_hace_poco(self):
        self._estudiante('573001120002', escribio_hace=1)
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_no_recuerda_a_quien_espera_el_calendario(self):
        self._estudiante('573001120003', termino_m1=True)
        HabilitacionModuloDripCliente.objects.create(
            cliente=self.cliente, curso=self.curso, modulo=self.m2,
            habilitado_desde=self.ahora + timedelta(days=1), activo=True,
        )
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_cuenta_desde_que_abrio_el_modulo(self):
        self._estudiante('573001120004', termino_m1=True, escribio_hace=5)
        HabilitacionModuloDripCliente.objects.create(
            cliente=self.cliente, curso=self.curso, modulo=self.m2,
            habilitado_desde=self.ahora - timedelta(days=1), activo=True,
        )
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_el_aviso_de_modulo_reinicia_la_cuenta(self):
        ana = self._estudiante('573001120005', escribio_hace=5)
        aviso = AvisoModuloDisponible.objects.create(
            cliente=self.cliente, curso=self.curso, plantilla=self.plantilla, phone_number_id=LINEA_2,
        )
        envio = AvisoModuloEnviado.objects.create(aviso=aviso, estudiante=ana, modulo=self.m1, estado='ENVIADO')
        AvisoModuloEnviado.objects.filter(pk=envio.pk).update(fecha=self.ahora - timedelta(hours=3))
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_repite_cada_semana_mientras_no_avance(self):
        ana = self._estudiante('573001120006', escribio_hace=10)
        self._enviado_hace(ana, 3)
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()
        RecordatorioCursoEnviado.objects.filter(estudiante=ana).update(fecha=self.ahora - timedelta(days=8))
        resultado, sender = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)

    def test_si_vuelve_a_escribir_la_cuenta_empieza_otra_vez(self):
        ana = self._estudiante('573001120007', escribio_hace=3)
        self._enviado_hace(ana, 5)
        resultado, sender = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)

    def test_una_vez_por_dia(self):
        self._estudiante('573001120008')
        self._ejecutar()
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_sin_terminos_o_sin_mensajes_no_recuerda(self):
        self._estudiante('573001120009', acepto_terminos=False)
        self._estudiante('573001120010', escribio_hace=None)
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_curso_terminado_o_baja_no_recuerda(self):
        terminado = self._estudiante('573001120011')
        ProgresoEstudiante.objects.filter(estudiante=terminado).update(completado=True)
        self._estudiante('573001120012', wa_optout_fecha=self.ahora)
        resultado, sender = self._ejecutar()
        sender.plantilla.assert_not_called()

    def test_solo_sale_a_su_hora(self):
        self._estudiante('573001120013')
        resultado, sender = self._ejecutar(self.ahora.replace(hour=10))
        sender.plantilla.assert_not_called()

    def test_con_grupo_solo_el_grupo(self):
        dentro = self._estudiante('573001120014')
        self._estudiante('573001120015')
        grupo = GrupoEstudiantes.objects.create(nombre='Cohorte', cliente=self.cliente)
        grupo.estudiantes.add(dentro)
        self.recordatorio.grupo = grupo
        self.recordatorio.save()
        resultado, sender = self._ejecutar()
        self.assertEqual(resultado['enviados'], 1)
        self.assertEqual(sender.plantilla.call_args.args[0], dentro.telefono)

    def test_flag_apagado_no_envia(self):
        self._estudiante('573001120016')
        with self.settings(EKI_RECORDATORIO_CURSO_ENABLED=False):
            resultado, sender = self._ejecutar()
        self.assertFalse(resultado['habilitado'])
        sender.plantilla.assert_not_called()

    def test_plantilla_con_tres_variables_no_sirve(self):
        from core.avisos.recordatorio_curso import motivo_plantilla

        self.plantilla.cuerpo = 'Hola {{1}} {{2}} {{3}}'
        self.plantilla.save()
        self.assertIn('2 variables', motivo_plantilla(self.plantilla, LINEA_2))

    def test_tarea_y_beat(self):
        from django.conf import settings

        from core.avisos.tareas import recordatorio_curso
        from mvp_project.celery import app

        nombre = 'core.avisos.tareas.recordatorio_curso'
        self.assertEqual(app.conf.beat_schedule['recordatorio-curso']['task'], nombre)
        self.assertIn(nombre, app.tasks)
        self.assertEqual(settings.CELERY_TASK_ROUTES[nombre]['queue'], 'masivo')
        with patch('core.avisos.recordatorio_curso.ejecutar', return_value={'enviados': 0}) as ejecutar:
            self.assertEqual(recordatorio_curso(), {'enviados': 0})
        ejecutar.assert_called_once_with()

    def test_admin_y_prueba_solo_al_numero_interno(self):
        from django.contrib.auth.models import User
        from django.urls import reverse

        self._estudiante('573001120017')
        self.client.force_login(User.objects.create_superuser('rec_admin', 'r@test.com', 'x'))
        cambio = reverse('admin:core_recordatoriocurso_change', args=[self.recordatorio.pk])
        self.assertEqual(self.client.get(cambio).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_recordatoriocurso_changelist')).status_code, 200)
        url = reverse('admin:core_recordatoriocurso_enviar_prueba_recordatorio', args=[self.recordatorio.pk])
        sender = _sender_ok()
        with self.settings(EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629']), \
                patch('core.lineas.sender.sender_de_linea', return_value=sender):
            self.client.post(url, {'telefono': '573001120017', '_form_submitted': 'True'})
            sender.plantilla.assert_not_called()
            self.client.post(url, {'telefono': '573026480629', '_form_submitted': 'True'})
        sender.plantilla.assert_called_once()
        self.assertEqual(sender.plantilla.call_args.args[2], {'1': 'Prueba', '2': 'Crea y Vende'})
        self.assertFalse(RecordatorioCursoEnviado.objects.exists())
