"""Copia curso(s) Fedepanela → cliente pruebas1 y activa modo botón (solo pruebas)."""
from django.core.management.base import BaseCommand, CommandError

from core.avance_whatsapp import MODO_AVANCE_BOTON
from core.copiar_cursos import ClienteOrigenNoEncontrado, copiar_cursos_a_pruebas
from core.models import Cliente, Curso


class Command(BaseCommand):
    help = (
        'Copia cursos del cliente Fedepanela al cliente pruebas1 y deja '
        'modo_avance_modulo=boton solo en pruebas1 (producción Fedepanela intacta).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--origen-nombre',
            default='fedepanela',
            help='Nombre parcial del cliente origen (default: fedepanela)',
        )
        parser.add_argument(
            '--destino-nombre',
            default='pruebas1',
            help='Nombre parcial del cliente destino (default: pruebas1)',
        )
        parser.add_argument('--solo-curso', type=int, help='ID de un solo curso a copiar')
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Borra cursos previos del destino antes de copiar',
        )
        parser.add_argument(
            '--sin-boton',
            action='store_true',
            help='No cambiar modo_avance_modulo en el destino',
        )
        parser.add_argument(
            '--content-sid',
            type=str,
            default='',
            help='Content SID HX… de plantilla quick reply Listo (opcional)',
        )

    def handle(self, *args, **options):
        try:
            result = copiar_cursos_a_pruebas(
                reset=options['reset'],
                origen_nombre=options['origen_nombre'],
                destino_nombre=options['destino_nombre'],
                solo_curso_id=options['solo_curso'],
                prefijo='',
            )
        except ClienteOrigenNoEncontrado as e:
            raise CommandError(str(e)) from e
        except LookupError as e:
            raise CommandError(str(e)) from e

        destino = result.destino
        if not options['sin_boton']:
            destino.modo_avance_modulo = MODO_AVANCE_BOTON
            if options['content_sid']:
                destino.content_sid_boton_listo = options['content_sid'].strip()
            destino.save(update_fields=['modo_avance_modulo', 'content_sid_boton_listo'])

        self.stdout.write(self.style.SUCCESS(
            f'Origen: {result.origen.nombre} (id={result.origen.pk}) → '
            f'Destino: {destino.nombre} (id={destino.pk})'
        ))
        for nombre in result.copiados:
            mods = Curso.objects.filter(cliente=destino, nombre=nombre).first()
            n_mod = mods.modulos.count() if mods else 0
            self.stdout.write(self.style.SUCCESS(f'  ✓ {nombre} ({n_mod} módulos)'))
        if not options['sin_boton']:
            self.stdout.write(self.style.WARNING(
                f'Destino «{destino.nombre}»: modo_avance_modulo=boton '
                f'(SID={destino.content_sid_boton_listo or "global continuar_modulo"})'
            ))
        self.stdout.write(self.style.SUCCESS(
            'Fedepanela origen no se modificó. Inscribe 1–2 estudiantes de prueba en pruebas1.'
        ))
