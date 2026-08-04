"""Normaliza departamento/municipio y territory_id DIVIPOLA de estudiantes."""

from django.core.management.base import BaseCommand

from core.models import Estudiante
from portal.geo_catalogo import resolver_ubicacion


class Command(BaseCommand):
    help = (
        'Alinea departamento/municipio al catálogo DANE y escribe territory_id '
        '(código DIVIPOLA) para mapa/cobertura e inteligencia territorial.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Guardar cambios en base de datos (por defecto solo simulación).',
        )
        parser.add_argument(
            '--cliente-id',
            type=int,
            default=None,
            help='Limitar a un cliente (ID).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        cliente_id = options['cliente_id']

        qs = Estudiante.objects.all().order_by('id')
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        total = qs.count()
        actualizados = 0
        mapeados = 0
        sin_municipio = 0
        sin_match = 0
        con_territory = 0

        for est in qs.iterator(chunk_size=500):
            raw_d = (est.departamento or '').strip()
            raw_m = (est.municipio or '').strip()
            if not raw_d and not raw_m:
                continue

            ubic = resolver_ubicacion(raw_m, raw_d)
            if ubic.nivel == 'municipio':
                mapeados += 1
                nuevo_d = ubic.departamento
                nuevo_m = ubic.municipio
                nuevo_tid = ubic.territory_id or ''
                if nuevo_tid:
                    con_territory += 1
            elif ubic.nivel == 'departamento':
                sin_municipio += 1
                nuevo_d = ubic.departamento
                nuevo_m = raw_m
                nuevo_tid = ''
            else:
                sin_match += 1
                continue

            cambio = (
                (est.departamento or '').strip() != nuevo_d
                or (est.municipio or '').strip() != nuevo_m
                or (est.territory_id or '').strip() != nuevo_tid
            )
            if not cambio:
                continue

            actualizados += 1
            self.stdout.write(
                f'  [{est.id}] {(raw_m or "?")}, {(raw_d or "?")} → '
                f'{nuevo_m or "?"}, {nuevo_d} tid={nuevo_tid or "-"} ({ubic.metodo})'
            )
            if apply:
                est.departamento = nuevo_d
                est.municipio = nuevo_m
                est.territory_id = nuevo_tid
                est.save(update_fields=['departamento', 'municipio', 'territory_id'])

        if apply and actualizados:
            try:
                from django.core.cache import cache

                cache.delete('eki_cobertura_global_v2')
            except Exception:
                pass

        modo = 'APLICADO' if apply else 'SIMULACIÓN'
        self.stdout.write(self.style.SUCCESS(f'\n[{modo}] Revisados: {total}'))
        self.stdout.write(f'  Municipio reconocido: {mapeados}')
        self.stdout.write(f'  Con DIVIPOLA (territory_id): {con_territory}')
        self.stdout.write(f'  Solo departamento: {sin_municipio}')
        self.stdout.write(f'  Sin match en catálogo: {sin_match}')
        self.stdout.write(f'  Registros a corregir: {actualizados}')
        if not apply and actualizados:
            self.stdout.write(self.style.WARNING('Ejecute con --apply para guardar.'))
