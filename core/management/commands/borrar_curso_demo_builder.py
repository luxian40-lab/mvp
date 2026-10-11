# -*- coding: utf-8 -*-
"""Borra solo el curso «ZZ · Demo del constructor» de la organización eki Demo."""
from django.core.management.base import BaseCommand

from core.management.commands.crear_curso_demo_builder import CURSO, EMAIL, ORG
from core.models import Cliente, Curso


class Command(BaseCommand):
    help = 'Borra el curso demo del constructor. No toca otros clientes.'

    def handle(self, *args, **options):
        qs = Curso.objects.filter(nombre=CURSO, cliente__nombre=ORG)
        n = qs.count()
        qs.delete()
        self.stdout.write(f'Cursos borrados: {n}.')
        cliente = Cliente.objects.filter(nombre=ORG, email=EMAIL).first()
        if cliente and not cliente.cursos.exists():
            cliente.delete()
            self.stdout.write('Organización eki Demo borrada porque no le quedaban cursos.')
