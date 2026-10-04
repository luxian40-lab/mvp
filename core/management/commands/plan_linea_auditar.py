"""Clientes y grupos sin plan de la línea, y cuántos estudiantes dependen del default."""
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Cliente, Estudiante
from core.models_extras import GrupoEstudiantes


class Command(BaseCommand):
    help = 'Lista organizaciones y grupos sin plan de línea y cuántos estudiantes quedarían sin plan.'

    def handle(self, *args, **options):
        sin_plan = Q(plan_linea_meta='') | Q(plan_linea_meta__isnull=True)
        clientes = Cliente.objects.filter(activo=True).filter(sin_plan).order_by('id')
        self.stdout.write(f'clientes_sin_plan {clientes.count()}')
        for cliente in clientes:
            n = Estudiante.objects.filter(cliente=cliente).count()
            self.stdout.write(f'cliente {cliente.id} estudiantes {n}')
        grupos = (
            GrupoEstudiantes.objects.filter(activo=True)
            .filter(sin_plan)
            .order_by('id')
        )
        self.stdout.write(f'grupos_sin_plan {grupos.count()}')
        for grupo in grupos:
            self.stdout.write(f'grupo {grupo.id} estudiantes {grupo.estudiantes.count()}')
