"""Tests webhook Google Form → habilitar módulo."""

import json

from django.test import Client, TestCase

from core.drip_schedule import estudiante_autorizado_en_modulo
from core.form_externo_service import buscar_estudiante_enlace, procesar_respuesta_formulario_externo
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    HabilitacionModuloEstudiante,
    Modulo,
)
from core.models_extras import EnlaceFormularioExterno


class FormExternoServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Form',
            contacto_principal='A',
            email='f@test.com',
            telefono='573008888881',
            activo=True,
            drip_modulos_solo_estudiantes_listados=True,
        )
        self.curso = Curso.objects.create(nombre='Curso F', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.m3 = Modulo.objects.create(
            curso=self.curso, numero=3, titulo='M3 final', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='555', nombre='Pablo', telefono='573008888882',
            cliente=self.cliente, activo=True,
        )
        self.enlace = EnlaceFormularioExterno.objects.create(
            nombre='Form GEI',
            cliente=self.cliente,
            curso=self.curso,
            modulo=None,
            campo_identificador='cedula',
        )

    def test_ultimo_modulo_por_defecto(self):
        r = procesar_respuesta_formulario_externo(self.enlace, {'cedula': '555'})
        self.assertTrue(r['ok'])
        self.assertEqual(r['modulo_id'], self.m3.id)
        self.assertTrue(estudiante_autorizado_en_modulo(self.est, self.m3))

    def test_modulo_especifico(self):
        self.enlace.modulo = self.m1
        self.enlace.save()
        r = procesar_respuesta_formulario_externo(self.enlace, {'cedula': '555'})
        self.assertTrue(r['ok'])
        self.assertEqual(r['modulo_id'], self.m1.id)

    def test_estudiante_no_encontrado(self):
        r = procesar_respuesta_formulario_externo(self.enlace, {'cedula': '99999'})
        self.assertFalse(r['ok'])

    def test_cedula_y_telefono_ok(self):
        self.enlace.campo_identificador = 'cedula_y_telefono'
        self.enlace.save()
        r = procesar_respuesta_formulario_externo(
            self.enlace, {'cedula': '555', 'telefono': '573008888882'},
        )
        self.assertTrue(r['ok'])

    def test_cedula_y_telefono_mismatch_rechaza(self):
        otro = Estudiante.objects.create(
            cedula='666', nombre='Otro', telefono='573008888883',
            cliente=self.cliente, activo=True,
        )
        self.enlace.campo_identificador = 'cedula_y_telefono'
        self.enlace.save()
        r = procesar_respuesta_formulario_externo(
            self.enlace, {'cedula': '555', 'telefono': otro.telefono},
        )
        self.assertFalse(r['ok'])
        self.assertIn('distintas', r['mensaje'])

    def test_cedula_y_nombre_ok(self):
        self.enlace.campo_identificador = 'cedula_y_nombre'
        self.enlace.save()
        r = procesar_respuesta_formulario_externo(
            self.enlace, {'cedula': '555', 'nombre': 'Pablo García'},
        )
        self.assertTrue(r['ok'])

    def test_cedula_y_nombre_incorrecto_rechaza(self):
        self.enlace.campo_identificador = 'cedula_y_nombre'
        self.enlace.save()
        est, err = buscar_estudiante_enlace(
            self.enlace, {'cedula': '555', 'nombre': 'María López'},
        )
        self.assertIsNone(est)
        self.assertIn('nombre', err.lower())


class FormExternoWebhookTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org WH', contacto_principal='B', email='w@test.com',
            telefono='573009999991', activo=True,
            drip_modulos_solo_estudiantes_listados=True,
        )
        self.curso = Curso.objects.create(nombre='C', cliente=self.cliente, activo=True)
        self.modulo = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='77', nombre='Eva', telefono='573009999992',
            cliente=self.cliente, activo=True,
        )
        self.enlace = EnlaceFormularioExterno.objects.create(
            nombre='WH', cliente=self.cliente, curso=self.curso, modulo=self.modulo,
            campo_identificador='cedula_y_telefono',
        )
        self.http = Client()

    def test_webhook_post_ok(self):
        url = f'/api/integracion/form-externo/{self.enlace.token}/'
        r = self.http.post(
            url,
            data=json.dumps({'cedula': '77', 'telefono': '573009999992'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertTrue(
            HabilitacionModuloEstudiante.objects.filter(
                estudiante=self.est, modulo=self.modulo, activo=True,
            ).exists()
        )
