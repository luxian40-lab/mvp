"""Crea o copia los tres cursos generales del menú de Formación."""
from django.core.management.base import BaseCommand

from core.cursos_generales import asegurar_cursos_generales


class Command(BaseCommand):
    help = (
        'Deja listos los cursos sin cliente del menú: copia Riendas e Innovación '
        'si existen en esta base, y crea Gestión de tiempo (5 módulos).'
    )

    def handle(self, *args, **options):
        resultado = asegurar_cursos_generales()
        for clave, fila in resultado.items():
            self.stdout.write(f'{clave}: {fila}')
