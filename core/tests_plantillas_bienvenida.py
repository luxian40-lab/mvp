"""Las bienvenidas se guardan en borrador y no se publican en Meta."""
from django.core.management import call_command
from django.test import TestCase

from core.management.commands.cargar_plantillas_bienvenida import (
    AVISO_CARRUSEL,
    PLANTILLAS_TEXTO,
    cargar_borradores,
)
from core.meta_waba import armar_componentes_alta
from core.models_campana_meta import PlantillaMeta


class CargarPlantillasBienvenidaTests(TestCase):
    def test_crea_cuatro_textos_y_un_carrusel_bloqueado(self):
        filas = dict(cargar_borradores())
        self.assertEqual(set(filas.values()), {'creada'})
        self.assertEqual(PlantillaMeta.objects.count(), 5)
        for definicion in PLANTILLAS_TEXTO:
            fila = PlantillaMeta.objects.get(meta_name=definicion['meta_name'], idioma='es')
            self.assertEqual(fila.estado, 'BORRADOR')
            self.assertEqual(fila.categoria, 'MARKETING')
            self.assertEqual(fila.tipo, 'TEXTO')
            self.assertEqual(fila.boton_1_tipo, 'QUICK_REPLY')
            self.assertEqual(fila.boton_1_texto, definicion['boton_1_texto'])
            self.assertEqual(fila.boton_2_texto, 'No recibir más')
            self.assertIn(definicion['ejemplos_cuerpo'].split('|')[0], fila.ejemplos_cuerpo)
            self.assertEqual(fila.meta_template_id, '')
            comps = armar_componentes_alta(fila)
            tipos = [c['type'] for c in comps]
            self.assertEqual(tipos, ['BODY', 'FOOTER', 'BUTTONS'])
            self.assertEqual(len(comps[-1]['buttons']), 2)
        carrusel = PlantillaMeta.objects.get(meta_name='eki_bienvenida_carrusel')
        self.assertEqual(carrusel.tipo, 'CARRUSEL')
        self.assertEqual(carrusel.estado, 'BORRADOR')
        self.assertIn('WHATSAPP_APP_ID', carrusel.ultimo_error_mensaje)
        self.assertEqual(carrusel.ultimo_error_mensaje, AVISO_CARRUSEL)
        self.assertEqual(carrusel.tarjetas.count(), 0)

    def test_segunda_corrida_no_duplica_ni_pisa_una_ya_enviada(self):
        cargar_borradores()
        publicada = PlantillaMeta.objects.get(meta_name='eki_bienvenida_texto')
        publicada.estado = 'APPROVED'
        publicada.meta_template_id = '99'
        publicada.cuerpo = 'Texto ya aprobado en Meta.'
        publicada.save()
        filas = dict(cargar_borradores())
        self.assertEqual(PlantillaMeta.objects.count(), 5)
        self.assertEqual(filas['eki_bienvenida_texto'], 'intacta')
        self.assertEqual(filas['eki_bienvenida_generica'], 'actualizada')
        publicada.refresh_from_db()
        self.assertEqual(publicada.estado, 'APPROVED')
        self.assertEqual(publicada.cuerpo, 'Texto ya aprobado en Meta.')
        self.assertEqual(publicada.meta_template_id, '99')

    def test_comando_no_llama_a_meta(self):
        from unittest.mock import patch

        with patch('core.meta_waba.crear_plantilla_en_meta') as alta:
            call_command('cargar_plantillas_bienvenida')
        alta.assert_not_called()
        self.assertEqual(PlantillaMeta.objects.filter(estado='BORRADOR').count(), 5)
