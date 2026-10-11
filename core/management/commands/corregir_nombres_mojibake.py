"""Lista nombres con mojibake. Solo escribe con --apply, y solo en cliente, grupo y curso."""
from django.core.management.base import BaseCommand

from core.models import Cliente, Curso, Estudiante
from core.models_extras import GrupoEstudiantes


def propuesta(texto):
    """Devuelve el texto corregido, o None si no parece mojibake reversible."""
    if not texto or ('Ã' not in texto and 'Â' not in texto):
        return None
    for codec in ('cp1252', 'latin-1'):
        try:
            nuevo = texto.encode(codec).decode('utf-8')
        except UnicodeError:
            continue
        if nuevo != texto:
            return nuevo
    return None


class Command(BaseCommand):
    help = (
        'Lista nombres mal codificados (por ejemplo Usaquén). '
        'Sin --apply no escribe. Con --apply solo corrige Cliente, grupo y curso.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista los cambios y no escribe. Es el modo por defecto.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Escribe los cambios en Cliente, grupo y curso.',
        )

    def handle(self, *args, **options):
        if options['apply'] and options['dry_run']:
            self.stderr.write('Use --apply o --dry-run, no los dos.')
            return
        aplicar = options['apply']
        objetivos = (
            (Cliente, 'nombre', True),
            (GrupoEstudiantes, 'nombre', True),
            (Curso, 'nombre', True),
        )
        solo_reporte = (
            (Cliente, 'contacto_principal'),
            (Cliente, 'notas_internas'),
            (Estudiante, 'nombre'),
            (Estudiante, 'municipio'),
            (Curso, 'descripcion'),
            (GrupoEstudiantes, 'descripcion'),
        )
        self.stdout.write('modo aplicar' if aplicar else 'modo dry-run')
        self._recorrer(objetivos, aplicar)
        self.stdout.write('otros modelos, solo reporte')
        self._recorrer(tuple((modelo, campo, False) for modelo, campo in solo_reporte), False)

    def _recorrer(self, filas, aplicar):
        for modelo, campo, puede in filas:
            for obj in modelo.objects.all().order_by('pk').iterator():
                actual = getattr(obj, campo) or ''
                nuevo = propuesta(actual)
                if not nuevo:
                    continue
                self.stdout.write(
                    f'{modelo._meta.label}.{campo} id={obj.pk} {actual!r} -> {nuevo!r}'
                )
                if aplicar and puede:
                    setattr(obj, campo, nuevo)
                    obj.save(update_fields=[campo])
