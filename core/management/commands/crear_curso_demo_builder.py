# -*- coding: utf-8 -*-
"""Crea, solo en la organización «eki Demo», el curso de muestra del constructor.

Idempotente. No toca otros clientes. La marca queda en la descripción.
"""
import base64
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from core.models import Cliente, Curso, Modulo
from core.module_builder import agregar_micro, agregar_seccion

ORG = 'eki Demo'
CURSO = 'ZZ · Demo del constructor'
MARCA = 'DEMO CONSTRUCTOR. No es un curso de un cliente real.'
EMAIL = 'demo-constructor@eki.invalid'

_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


class Command(BaseCommand):
    help = 'Crea el curso demo del Module Builder en la organización eki Demo.'

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(nombre=ORG).first()
        if cliente is None:
            cliente = Cliente.objects.create(
                nombre=ORG,
                contacto_principal='Demo',
                email=EMAIL,
                telefono='570000000000',
                activo=True,
            )
            self.stdout.write('Organización eki Demo creada.')
        curso = Curso.objects.filter(nombre=CURSO, cliente=cliente).first()
        if curso is None:
            curso = Curso.objects.create(
                nombre=CURSO,
                descripcion=MARCA,
                cliente=cliente,
                activo=True,
                enlace_grupo_whatsapp='',
            )
        else:
            self.stdout.write(f'El curso ya existe (id {curso.pk}). No se duplica.')
            return
        self._armar(curso)
        self.stdout.write(self.style.SUCCESS(f'Curso demo {curso.pk} en {ORG}.'))

    def _armar(self, curso):
        uno = Modulo.objects.create(
            curso=curso, numero=1, titulo='Demo · Primer módulo',
            descripcion=MARCA, contenido='demo',
        )
        dos = Modulo.objects.create(
            curso=curso, numero=2, titulo='Demo · Segundo módulo',
            descripcion=MARCA, contenido='demo',
        )
        s1 = agregar_seccion(uno, 'Bienvenida')
        s2 = agregar_seccion(uno, 'Imagen')
        s3 = agregar_seccion(dos, 'Cierre')
        agregar_micro(uno, s1, titulo='Saludo', contenido='Este mensaje es de demostración.')
        ruta = default_storage.save(
            f'modulos/pasos/demo_builder_{curso.pk}.png',
            ContentFile(_PNG),
        )
        url = default_storage.url(ruta)
        foto = agregar_micro(uno, s2, titulo='Foto demo', contenido='', media_url=url)
        foto.media_wa_apto = True
        foto.save(update_fields=['media_wa_apto'])
        mp4 = Path(__file__).resolve().parents[1] / 'fixtures' / 'demo_builder.mp4'
        if mp4.is_file():
            ruta_v = default_storage.save(
                f'modulos/pasos/demo_builder_{curso.pk}.mp4',
                ContentFile(mp4.read_bytes()),
            )
            url_v = default_storage.url(ruta_v)
            clip = agregar_micro(
                dos, s3, titulo='Video demo', contenido='',
                media_url=url_v, media_wa_apto=True,
            )
            clip.media_wa_apto = True
            clip.save(update_fields=['media_wa_apto'])
        else:
            agregar_micro(
                dos, s3, titulo='Video demo',
                contenido='Falta el archivo de demostración en el servidor.',
            )
