# -*- coding: utf-8 -*-
"""Tests comando certificar_modulo_media."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Curso, Modulo
from core.module_builder import agregar_micro, agregar_seccion


class CertificarModuloMediaTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Cert QA')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='c',
        )

    def test_certificar_modulo_ok_sin_media(self):
        sa = agregar_seccion(self.mod, 'Intro')
        agregar_micro(self.mod, sa, contenido='Hola')
        out = StringIO()
        call_command(
            'certificar_modulo_media',
            '--modulo-id',
            str(self.mod.pk),
            '--sin-head',
            stdout=out,
        )
        self.assertIn('QA_PASS', out.getvalue())

    def test_certificar_modulo_fail_media_no_apto(self):
        sa = agregar_seccion(self.mod, 'Intro')
        agregar_micro(
            self.mod,
            sa,
            contenido='Video',
            media_url='https://cdn.example.com/clip.mp4',
            media_wa_apto=False,
        )
        with self.assertRaises(SystemExit) as ctx:
            call_command(
                'certificar_modulo_media',
                '--modulo-id',
                str(self.mod.pk),
                '--sin-head',
            )
        self.assertEqual(ctx.exception.code, 1)

    def test_certificar_modulo_id_invalido(self):
        with self.assertRaises(CommandError):
            call_command('certificar_modulo_media', '--modulo-id', '99999')
