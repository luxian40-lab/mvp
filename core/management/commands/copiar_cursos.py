"""CLI: copia Analytics → Analytics (Pruebas). Ver core.copiar_cursos."""
from django.core.management.base import BaseCommand, CommandError

from core.copiar_cursos import (
    CLIENTE_ORIGEN_NOMBRE,
    ClienteOrigenNoEncontrado,
    copiar_cursos_a_pruebas,
)
from core.models import Curso


class Command(BaseCommand):
    help = (
        f'Copia cursos del cliente «{CLIENTE_ORIGEN_NOMBRE}» '
        'a Analytics (Pruebas) — sin estudiantes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Borra cursos previos en Pruebas')
        parser.add_argument('--origen-id', type=int, help='ID cliente origen (default: Analytics)')
        parser.add_argument(
            '--origen-nombre',
            type=str,
            help=f'Nombre parcial origen (default: {CLIENTE_ORIGEN_NOMBRE})',
        )
        parser.add_argument('--solo-curso', type=int, help='Solo un curso por ID')
        parser.add_argument('--prefijo', default='[PRUEBA] ')

    def handle(self, *args, **options):
        try:
            result = copiar_cursos_a_pruebas(
                reset=options['reset'],
                origen_id=options['origen_id'],
                origen_nombre=options['origen_nombre'],
                solo_curso_id=options['solo_curso'],
                prefijo=options['prefijo'] or '',
            )
        except ClienteOrigenNoEncontrado as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(
            f'Origen: {result.origen.nombre} (id={result.origen.pk}) → '
            f'Destino: {result.destino.nombre} (id={result.destino.pk})'
        ))
        if result.reset_borrados:
            self.stdout.write(self.style.WARNING(
                f'Reset destino: {result.reset_borrados} curso(s) borrados'
            ))
        for nombre in result.copiados:
            mods = Curso.objects.get(cliente=result.destino, nombre=nombre).modulos.count()
            self.stdout.write(self.style.SUCCESS(f'  ✓ {nombre} ({mods} módulos)'))
        for nombre in result.omitidos:
            self.stdout.write(f'  · Ya existe: {nombre}')
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {result.total_copiados} curso(s) copiados. Sin estudiantes.'
        ))
