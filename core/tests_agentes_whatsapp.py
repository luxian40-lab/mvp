"""Sin titular de agente al inicio: el cuerpo va directo (no *Carlos* / Darío)."""
from django.test import TestCase

from core.agentes_whatsapp import (
    cuerpo_sin_titular_agente,
    mensaje_con_titular_agente,
    titular_agente_al_inicio,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import activar_checkpoint_facilitador
from core.tutor_ia_modulo import bloque_reto_whatsapp, generar_presentacion_agentes


class CuerpoSinTitularTests(TestCase):
    def test_quita_titular_y_deja_cuerpo(self):
        msg = cuerpo_sin_titular_agente(
            'Carlos',
            '*Carlos*\n\n¡Hola! Es hora de una pausa para repasar conceptos.',
        )
        self.assertFalse(titular_agente_al_inicio(msg, 'Carlos'))
        self.assertTrue(msg.startswith('¡Hola!'))
        self.assertNotIn('*Carlos*', msg)

    def test_cuerpo_sin_titular_queda_igual(self):
        msg = cuerpo_sin_titular_agente(
            'Carlos',
            '¡Hola! Es hora de una pausa para repasar conceptos.',
        )
        self.assertEqual(msg, '¡Hola! Es hora de una pausa para repasar conceptos.')

    def test_alias_compat_no_agrega_titular(self):
        msg = mensaje_con_titular_agente('Carlos', 'Cuerpo directo.')
        self.assertEqual(msg, 'Cuerpo directo.')
        self.assertFalse(msg.startswith('*Carlos*'))


class CheckpointSinTitularTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Carlos',
            activo=True,
            nombre_agente_asistente='Carlos',
            nombre_agente_tutor='Su asesor',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Carlos',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=True,
            nombre_agente_asistente='Carlos',
            nombre_agente_tutor='Su asesor',
            descripcion='d',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='x',
        )
        self.est = Estudiante.objects.create(
            cedula='88001122',
            nombre='Est',
            telefono='573001112233',
            cliente=self.cliente,
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )

    def test_pausa_no_abre_con_carlos(self):
        msg = activar_checkpoint_facilitador(self.est, self.prog, self.mod)
        self.assertFalse(titular_agente_al_inicio(msg, 'Carlos'))
        self.assertFalse(msg.startswith('*Carlos*'))
        self.assertTrue(msg.startswith('¡Hola!'), msg[:80])
        self.assertIn('pausa para repasar', msg.lower())
        self.assertIn('Su asesor lo va a recibir', msg)


class PresentacionYRetoSinTitularTests(TestCase):
    def test_presentacion_no_abre_solo_con_nombre(self):
        curso = Curso.objects.create(
            nombre='C',
            descripcion='d',
            nombre_agente_tutor='Claudia',
            nombre_agente_asistente='Darío',
        )
        fac, asist = generar_presentacion_agentes(
            curso.nombre, 'Ana', nombre_tutor='Claudia', nombre_asistente='Darío', curso=curso,
        )
        self.assertFalse(titular_agente_al_inicio(fac, 'Claudia'))
        self.assertFalse(titular_agente_al_inicio(asist, 'Darío'))
        self.assertIn('compañero de estudio', asist)
        self.assertIn('Ana', fac)

    def test_reto_no_abre_con_titular(self):
        bloque = bloque_reto_whatsapp('Asesor', 'Revise 10 colmenas.')
        self.assertFalse(titular_agente_al_inicio(bloque, 'Asesor'))
        self.assertTrue(bloque.startswith('Revise 10 colmenas.'))
